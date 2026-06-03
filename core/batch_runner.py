"""
core/batch_runner.py
--------------------
Orchestrates the two-stage batch pipeline in a background thread.

Stage 1 — GENERATE:
    For each row in Excel:
        Excel row → Word doc (docxtpl) → PDF (pywin32 COM) → Drive upload
        Save checkpoint after each row.

Stage 2 — SEND:
    For each approved row:
        Send Email + WhatsApp (with 3–5 sec delay)
        Save checkpoint + log after each row.

Threading model:
    - Runs in a daemon background thread (never blocks the GUI).
    - pythoncom.CoInitialize() called at thread start for Word COM (STA mode).
    - GUI communicates via queue.Queue (thread-safe).
    - Pause/Cancel handled via threading.Event flags.

Progress messages posted to ``progress_queue`` (dict):
    {
        "type":    "progress" | "row_done" | "stage_complete" | "error" | "complete",
        "current": int,          # rows processed so far in this stage
        "total":   int,          # total rows in this stage
        "stage":   "generate" | "send",
        "message": str,          # human-readable status line
        "row":     dict | None,  # only for "row_done"
        "summary": dict | None,  # only for "complete"
    }
"""

import os
import json
import queue
import random
import threading
import time
from datetime import datetime

from core.cloud_uploader import DriveUploader
from core.doc_generator import render_document
from core.email_sender import EmailSender, format_email_content
from core.excel_reader import read_excel
from core.pdf_converter import WordPdfConverter, is_word_installed
from core.whatsapp_sender import WhatsAppSender
from utils.checkpoint import CheckpointManager, compute_excel_hash
from utils.config_manager import ConfigManager
from utils.logger import BatchLogger
from utils.preflight import (
    check_email_capacity,
    check_template_readable,
)
from utils.validators import normalize_phone, validate_email, validate_phone


# ── Constants ────────────────────────────────────────────────────────────────

_EMAIL_DELAY_SEC = 5          # Gmail guidelines: ~5 sec between sends
_WA_DELAY_MIN_SEC = 3         # Min WhatsApp inter-message delay
_WA_DELAY_MAX_SEC = 5         # Max WhatsApp inter-message delay

class BatchRunner:
    """
    Runs a full notice batch (Generate → Preview → Send) in a background thread.

    Usage:
        runner = BatchRunner(config_manager, progress_queue)
        runner.start_generate(excel_path, profile_name, output_dir, log_dir)
        # ... user reviews in Preview tab ...
        runner.start_send(approved_rows, notice_type, send_email, send_whatsapp)

    Pause/Cancel:
        runner.pause()   # pauses after the current row
        runner.resume()
        runner.cancel()  # stops cleanly; partial results are preserved
    """

    def __init__(
        self,
        config_manager: ConfigManager,
        progress_queue: queue.Queue,
    ):
        """
        Args:
            config_manager:  Loaded ConfigManager instance.
            progress_queue:  Thread-safe queue the GUI reads for progress updates.
        """
        self._cfg = config_manager
        self._q = progress_queue

        # Control events
        self._pause_event = threading.Event()
        self._pause_event.set()   # Not paused by default (set = "go")
        self._cancel_event = threading.Event()

        # Worker thread reference
        self._thread: threading.Thread | None = None

        # State set after Stage 1 completes (used by Stage 2)
        self._checkpoint_mgr: CheckpointManager | None = None
        self._logger: BatchLogger | None = None
        self._batch_id: str = ""

    # ── Public control API ────────────────────────────────────────────────────

    def is_running(self) -> bool:
        """True if the worker thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    def pause(self) -> None:
        """Request pause after the current row completes."""
        self._pause_event.clear()

    def resume(self) -> None:
        """Resume a paused batch."""
        self._pause_event.set()

    def cancel(self) -> None:
        """
        Request cancellation. Also resumes if paused so the thread can exit.
        The thread cleans up Word COM and posts a final 'complete' message.
        """
        self._cancel_event.set()
        self._pause_event.set()   # Unblock paused thread so it can exit

    # ── Stage 1: Generate ─────────────────────────────────────────────────────

    def start_generate(
        self,
        excel_path: str,
        profile_name: str,
        output_dir: str,
        log_dir: str,
    ) -> None:
        """
        Start Stage 1 in a background thread.

        Args:
            excel_path:    Full path to the .xlsx file.
            profile_name:  Profile name (must exist in config).
            output_dir:    Root folder for generated docs/PDFs.
            log_dir:       Folder for checkpoint + log files.
        """
        if self.is_running():
            raise RuntimeError("A batch is already running.")

        # Reset control state for a fresh run
        self._cancel_event.clear()
        self._pause_event.set()

        self._thread = threading.Thread(
            target=self._generate_worker,
            args=(excel_path, profile_name, output_dir, log_dir),
            daemon=True,
            name="BatchGenerate",
        )
        self._thread.start()

    def start_send(
        self,
        approved_rows: list[dict],
        notice_type: str,
        send_email: bool,
        send_whatsapp: bool,
    ) -> None:
        """
        Start Stage 2 in a background thread.
        Must only be called after start_generate completes successfully.

        Args:
            approved_rows:   Rows from PreviewTab after user review/exclusion.
            notice_type:     One of VALID_NOTICE_TYPES (for logging / compliance gate).
            send_email:      Whether to send email for each row.
            send_whatsapp:   Whether to send WhatsApp for each row.
        """
        if self.is_running():
            raise RuntimeError("A batch is already running.")
        if self._checkpoint_mgr is None or self._logger is None:
            raise RuntimeError("Must complete Stage 1 before starting Stage 2.")

        self._cancel_event.clear()
        self._pause_event.set()

        self._thread = threading.Thread(
            target=self._send_worker,
            args=(approved_rows, notice_type, send_email, send_whatsapp),
            daemon=True,
            name="BatchSend",
        )
        self._thread.start()

    # ── Stage 1 worker (runs in background thread) ────────────────────────────

    def _generate_worker(
        self,
        excel_path: str,
        profile_name: str,
        output_dir: str,
        log_dir: str,
    ) -> None:
        """
        Background thread: Excel → Word → PDF → Drive for every row.
        Posts progress messages to self._q.
        """
        # COM must be initialized in EVERY thread that uses Word COM
        word_com_initialized = False
        try:
            import pythoncom
            pythoncom.CoInitialize()
            word_com_initialized = True
        except ImportError:
            # pywin32 not available (e.g., running tests on non-Windows)
            pass

        converter: WordPdfConverter | None = None

        try:
            # ── Load config ───────────────────────────────────────────────────
            profile = self._cfg.get_profile(profile_name)
            if profile is None:
                self._post_error(f"Profile '{profile_name}' not found in config.")
                return
            profile_errors = self._cfg.validate_profile(profile_name)
            if profile_errors:
                self._post_error("Profile error: " + profile_errors[0])
                return

            settings = self._cfg.get("settings") or {}
            batch_restart_every: int = settings.get("batch_restart_every", 50)
            firm_name: str = settings.get("firm_name", "Law Firm")
            lawyer_name: str = settings.get("lawyer_name", "")
            notice_date: str = datetime.now().strftime("%d/%m/%Y")
            template_path = self._cfg.resolve_path(profile.get("template_path", ""))

            # ── Preflight checks ──────────────────────────────────────────────
            self._post_progress(0, 1, "generate", "Running pre-flight checks…")

            ok, msg = check_template_readable(template_path)
            if not ok:
                self._post_error(f"Template error: {msg}")
                return

            self._post_progress(0, 1, "generate", "Checking Microsoft Word...")
            if not is_word_installed():
                self._post_error(
                    "Microsoft Word is required for PDF generation. "
                    "Install the desktop Microsoft Word app on this system, then run again."
                )
                return

            # ── Read Excel ────────────────────────────────────────────────────
            self._post_progress(0, 1, "generate", "Reading Excel file…")
            col_mapping = profile.get("column_mapping", {})
            required_fields = self._cfg.get_profile_required_fields(profile)
            rows = read_excel(
                excel_path,
                column_mapping=col_mapping,
                required_fields=required_fields,
            )
            total = len(rows)

            if total == 0:
                self._post_error("Excel file has no data rows.")
                return

            # Gmail capacity warning (non-blocking)
            max_emails = settings.get("max_emails_per_day", 450)
            ok, warning = check_email_capacity(total, max_emails)
            if not ok:
                self._post_progress(0, total, "generate", f"⚠ WARNING: {warning}")

            # ── Create paths + resume-aware batch ID ─────────────────────────
            os.makedirs(output_dir, exist_ok=True)
            os.makedirs(log_dir, exist_ok=True)

            excel_hash = compute_excel_hash(excel_path)
            resume = self._find_resume_checkpoint(log_dir, profile_name, excel_hash, total)
            self._batch_id = (
                resume["batch_id"]
                if resume
                else datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{profile_name}"
            )
            checkpoint_path = os.path.join(log_dir, f"{self._batch_id}_checkpoint.json")
            log_path = os.path.join(log_dir, f"{self._batch_id}.json")

            # ── Checkpoint: resume if same Excel ─────────────────────────────
            self._checkpoint_mgr = CheckpointManager(
                checkpoint_path=checkpoint_path,
                batch_id=self._batch_id,
                excel_path=excel_path,
                excel_hash=excel_hash,
                profile_name=profile_name,
                total_rows=total,
            )
            self._logger = BatchLogger(log_path)

            start_index = self._checkpoint_mgr.last_generated_index + 1

            # ── Drive uploader ────────────────────────────────────────────────
            drive_cfg = self._cfg.get("google_drive") or {}
            drive_cfg = {
                **drive_cfg,
                "service_account_json_path": self._cfg.resolve_path(
                    drive_cfg.get("service_account_json_path", "")
                ),
                "oauth_client_json_path": self._cfg.resolve_path(
                    drive_cfg.get("oauth_client_json_path", "")
                ),
                "oauth_token_json_path": self._cfg.resolve_path(
                    drive_cfg.get("oauth_token_json_path", "token.json")
                ),
            }
            drive_uploader: DriveUploader | None = None
            drive_init_error = ""
            try:
                drive_uploader = DriveUploader(drive_cfg)
            except Exception as exc:
                drive_init_error = str(exc)
                self._post_progress(
                    start_index,
                    total,
                    "generate",
                    f"⚠ Drive disabled for this batch: {exc}",
                )

            # Check Drive readiness (non-blocking warning)
            if drive_uploader is not None and not drive_cfg.get("mock_mode", True):
                quota_ok, quota_msg = drive_uploader.check_quota()
                folder_ok, folder_msg = drive_uploader.test_folder_access()
                if not quota_ok:
                    self._post_progress(start_index, total, "generate", f"Drive: {quota_msg}")
                if not folder_ok:
                    self._post_progress(start_index, total, "generate", f"Drive: {folder_msg}")

            # ── Init Word COM converter ───────────────────────────────────────
            converter = WordPdfConverter(restart_every=batch_restart_every)

            # ── Generate loop ─────────────────────────────────────────────────
            generated: list[dict] = []

            for i, row in enumerate(rows):
                row_with_statics = {
                    **row,
                    "FIRM_NAME": firm_name,
                    "LAWYER_NAME": lawyer_name,
                    "NOTICE_DATE": notice_date,
                }

                # Restore already-generated rows from checkpoint
                if i < start_index:
                    cp_result = self._checkpoint_mgr.get_result(i)
                    if cp_result and cp_result.get("pdf_path"):
                        generated.append({
                            **row_with_statics,
                            "pdf_path": cp_result.get("pdf_path", ""),
                            "drive_link": cp_result.get("drive_link", ""),
                            "drive_upload_status": cp_result.get("drive_upload_status", ""),
                            "drive_upload_error": cp_result.get("drive_upload_error", ""),
                            "doc_render_seconds": cp_result.get("doc_render_seconds", 0.0),
                            "pdf_convert_seconds": cp_result.get("pdf_convert_seconds", 0.0),
                            "drive_upload_seconds": cp_result.get("drive_upload_seconds", 0.0),
                            "row_index": i,
                        })
                        continue

                # Check cancel
                if self._cancel_event.is_set():
                    self._post_progress(i, total, "generate", "Cancelled by user.")
                    self._post_complete(generated, cancelled=True)
                    return

                # Wait if paused
                self._pause_event.wait()

                self._post_progress(
                    i, total, "generate",
                    f"Generating {i+1}/{total}: {row.get('NAME', 'Row ' + str(i+1))}…"
                )

                # ── Generate Word doc + PDF ───────────────────────────────────
                doc_render_seconds = 0.0
                pdf_convert_seconds = 0.0
                try:
                    phase_start = time.perf_counter()
                    docx_path = render_document(
                        template_path=template_path,
                        context=row_with_statics,
                        output_dir=output_dir,
                        batch_id=self._batch_id,
                        row_index=i,
                    )
                    doc_render_seconds = round(time.perf_counter() - phase_start, 3)
                    phase_start = time.perf_counter()
                    pdf_path = converter.convert(docx_path)
                    pdf_convert_seconds = round(time.perf_counter() - phase_start, 3)
                except Exception as exc:
                    # Log the error but continue with next row
                    self._post_progress(
                        i, total, "generate",
                        f"⚠ Row {i+1} generation failed: {exc}"
                    )
                    generated.append({
                        **row_with_statics,
                        "pdf_path": "",
                        "drive_link": "",
                        "drive_upload_status": "skipped",
                        "drive_upload_error": "PDF generation failed before Drive upload.",
                        "doc_render_seconds": doc_render_seconds,
                        "pdf_convert_seconds": pdf_convert_seconds,
                        "drive_upload_seconds": 0.0,
                        "row_index": i,
                        "_generate_error": str(exc),
                    })
                    self._checkpoint_mgr.mark_result(
                        i,
                        pdf_path="",
                        drive_link="",
                        drive_upload_status="skipped",
                        drive_upload_error="PDF generation failed before Drive upload.",
                        doc_render_seconds=doc_render_seconds,
                        pdf_convert_seconds=pdf_convert_seconds,
                        drive_upload_seconds=0.0,
                    )
                    continue

                # ── Upload to Drive ───────────────────────────────────────────
                drive_link = ""
                drive_upload_status = "skipped"
                drive_upload_error = ""
                drive_upload_seconds = 0.0
                if drive_uploader is not None:
                    try:
                        phase_start = time.perf_counter()
                        drive_link = drive_uploader.upload_pdf(
                            pdf_path=pdf_path,
                        )
                        drive_upload_seconds = round(time.perf_counter() - phase_start, 3)
                        drive_upload_status = (
                            "mock" if drive_cfg.get("mock_mode", True) else "uploaded"
                        )
                    except Exception as exc:
                        drive_upload_seconds = round(time.perf_counter() - phase_start, 3)
                        drive_upload_status = "failed"
                        drive_upload_error = str(exc)
                        self._post_progress(
                            i, total, "generate",
                            f"⚠ Row {i+1} Drive upload failed: {exc}"
                        )

                # ── Save result ───────────────────────────────────────────────
                if drive_uploader is None and drive_init_error:
                    drive_upload_status = "disabled"
                    drive_upload_error = drive_init_error

                self._checkpoint_mgr.mark_result(
                    i,
                    pdf_path=pdf_path,
                    drive_link=drive_link,
                    drive_upload_status=drive_upload_status,
                    drive_upload_error=drive_upload_error,
                    doc_render_seconds=doc_render_seconds,
                    pdf_convert_seconds=pdf_convert_seconds,
                    drive_upload_seconds=drive_upload_seconds,
                )

                generated.append({
                    **row_with_statics,
                    "pdf_path": pdf_path,
                    "drive_link": drive_link,
                    "drive_upload_status": drive_upload_status,
                    "drive_upload_error": drive_upload_error,
                    "doc_render_seconds": doc_render_seconds,
                    "pdf_convert_seconds": pdf_convert_seconds,
                    "drive_upload_seconds": drive_upload_seconds,
                    "row_index": i,
                })

                self._post_progress(i + 1, total, "generate", f"Generated {i+1}/{total}")

            # Stage 1 done
            self._post_stage_complete("generate", generated)

        except Exception as exc:
            self._post_error(f"Generation failed: {exc}")

        finally:
            # Always quit Word COM cleanly
            if converter is not None:
                try:
                    converter.quit()
                except Exception:
                    pass
            if word_com_initialized:
                try:
                    import pythoncom
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    # ── Stage 2 worker (runs in background thread) ────────────────────────────

    def _send_worker(
        self,
        approved_rows: list[dict],
        notice_type: str,
        send_email: bool,
        send_whatsapp: bool,
    ) -> None:
        """
        Background thread: Send Email + WhatsApp for each approved row.
        """
        try:
            total = len(approved_rows)
            settings = self._cfg.get("settings") or {}
            firm_name: str = settings.get("firm_name", "Law Firm")
            delay_min: float = settings.get("send_delay_min_sec", 3)
            delay_max: float = settings.get("send_delay_max_sec", 5)

            # ── Init senders ──────────────────────────────────────────────────
            gmail_cfg = self._cfg.get("gmail") or {}
            email_sender = EmailSender(gmail_cfg)

            aisensy_cfg = self._cfg.get("aisensy") or {}
            wa_sender = WhatsAppSender(aisensy_cfg, firm_name=firm_name)

            profile = self._cfg.get_profile(self._checkpoint_mgr._profile_name) or {}
            self._checkpoint_mgr.advance_to_sending()
            last_sent_index = self._checkpoint_mgr.last_sent_index
            is_retry_batch = any(
                "_retry_email" in row or "_retry_wa" in row
                for row in approved_rows
            )
            cancelled = False

            # ── Send loop ─────────────────────────────────────────────────────
            for i, row in enumerate(approved_rows):
                if self._cancel_event.is_set():
                    self._post_progress(i, total, "send", "Cancelled by user.")
                    cancelled = True
                    break

                # Wait if paused
                self._pause_event.wait()

                row_index = row.get("row_index", row.get("index", i))
                if not is_retry_batch and row_index <= last_sent_index:
                    continue

                recipient_name = _value_or_na(row.get("NAME"))
                display_name = recipient_name if recipient_name != "NA" else f"Row {i+1}"

                self._post_progress(
                    i, total, "send",
                    f"Sending {i+1}/{total}: {display_name}..."
                )

                email_status = "skipped"
                email_error = ""
                wa_status = "skipped"
                wa_error = ""
                pdf_path = row.get("pdf_path", "")
                drive_link = row.get("drive_link", "")
                drive_upload_status = row.get("drive_upload_status", "")
                drive_upload_error = row.get("drive_upload_error", "")
                doc_render_seconds = row.get("doc_render_seconds", 0.0)
                pdf_convert_seconds = row.get("pdf_convert_seconds", 0.0)
                drive_upload_seconds = row.get("drive_upload_seconds", 0.0)
                row_send_email = send_email and row.get("_retry_email", True)
                row_send_whatsapp = send_whatsapp and row.get("_retry_wa", True)

                # ── Send Email ────────────────────────────────────────────────
                if row_send_email:
                    email_addr = row.get("EMAILID", "")
                    email_ok, email_msg = validate_email(email_addr)
                    if not email_ok:
                        email_status = "failed"
                        email_error = email_msg
                    elif not pdf_path or not os.path.exists(pdf_path):
                        email_status = "failed"
                        email_error = "PDF file not found — generation may have failed."
                    else:
                        # Build subject + body from profile template
                        subject = format_email_content(
                            profile.get("email_subject", "Important Communication"),
                            row,
                        )
                        body = format_email_content(
                            profile.get("email_body", "Please find the attached notice."),
                            row,
                        )
                        ok, err = email_sender.send(
                            to=email_addr,
                            subject=subject,
                            body=body,
                            pdf_path=pdf_path,
                        )
                        email_status = "sent" if ok else "failed"
                        email_error = err
                        # Delay after email (Gmail rate-limit courtesy)
                        if ok:
                            time.sleep(_EMAIL_DELAY_SEC)

                # ── Send WhatsApp ─────────────────────────────────────────────
                if row_send_whatsapp:
                    phone = row.get("MOBILENO", "")
                    phone_ok, phone_msg = validate_phone(phone)
                    if not phone_ok:
                        wa_status = "failed"
                        wa_error = phone_msg
                    elif not drive_link:
                        wa_status = "failed"
                        wa_error = "Drive link is missing — Google Drive upload may have failed."
                    else:
                        account_no = _value_or_na(row.get("ACCOUNTNO"))
                        contact_no = _value_or_na(row.get("OFFICER_NO"))
                        ok, err = wa_sender.send_notice_notification(
                            phone=normalize_phone(phone),
                            name=recipient_name,
                            account_no=account_no,
                            drive_link=drive_link,
                            contact_no=contact_no,
                            batch_id=self._batch_id,
                        )
                        wa_status = "sent" if ok else "failed"
                        wa_error = err
                        # Random inter-message delay (Meta rate-limit safety)
                        time.sleep(random.uniform(delay_min, delay_max))

                # ── Log + checkpoint ──────────────────────────────────────────
                self._logger.log_row(
                    index=row_index,
                    row=row,
                    pdf_path=pdf_path,
                    drive_link=drive_link,
                    email_status=email_status,
                    email_error=email_error,
                    whatsapp_status=wa_status,
                    whatsapp_error=wa_error,
                    drive_upload_status=drive_upload_status,
                    drive_upload_error=drive_upload_error,
                    doc_render_seconds=doc_render_seconds,
                    pdf_convert_seconds=pdf_convert_seconds,
                    drive_upload_seconds=drive_upload_seconds,
                )
                self._checkpoint_mgr.mark_sent(
                    index=row_index,
                    email_status=email_status,
                    wa_status=wa_status,
                )

                # Post per-row result for live Log Tab update
                self._q.put({
                    "type": "row_done",
                    "current": i + 1,
                    "total": total,
                    "stage": "send",
                    "message": f"Sent {i+1}/{total}",
                    "row": {
                        **row,
                        "email_status": email_status,
                        "email_error": email_error,
                        "wa_status": wa_status,
                        "wa_error": wa_error,
                        "drive_upload_status": drive_upload_status,
                        "drive_upload_error": drive_upload_error,
                        "doc_render_seconds": doc_render_seconds,
                        "pdf_convert_seconds": pdf_convert_seconds,
                        "drive_upload_seconds": drive_upload_seconds,
                    },
                    "summary": None,
                })

            # ── Drive cleanup (optional) ──────────────────────────────────────
            if settings.get("drive_cleanup_enabled", True):
                drive_cfg = self._cfg.get("google_drive") or {}
                drive_cfg = {
                    **drive_cfg,
                    "service_account_json_path": self._cfg.resolve_path(
                        drive_cfg.get("service_account_json_path", "")
                    ),
                    "oauth_client_json_path": self._cfg.resolve_path(
                        drive_cfg.get("oauth_client_json_path", "")
                    ),
                    "oauth_token_json_path": self._cfg.resolve_path(
                        drive_cfg.get("oauth_token_json_path", "token.json")
                    ),
                }
                try:
                    uploader = DriveUploader(drive_cfg)
                    auto_delete_days = drive_cfg.get("auto_delete_days", 30)
                    uploader.delete_old_files(older_than_days=auto_delete_days)
                except Exception:
                    pass  # Cleanup failure must not affect the main flow

            summary = self._logger.get_summary()
            if not cancelled and self._checkpoint_mgr is not None:
                self._checkpoint_mgr.delete()
            self._post_complete(approved_rows, cancelled=cancelled, summary=summary)

        except Exception as exc:
            self._post_error(f"Send stage failed: {exc}")

    # ── Queue helpers ─────────────────────────────────────────────────────────

    def _post_progress(self, current: int, total: int, stage: str, message: str) -> None:
        self._q.put({
            "type": "progress",
            "current": current,
            "total": total,
            "stage": stage,
            "message": message,
            "row": None,
            "summary": None,
        })

    def _post_stage_complete(self, stage: str, generated: list[dict]) -> None:
        self._q.put({
            "type": "stage_complete",
            "current": len(generated),
            "total": len(generated),
            "stage": stage,
            "message": f"Stage '{stage}' complete. {len(generated)} rows processed.",
            "row": None,
            "summary": {"generated": generated},
        })

    def _post_error(self, message: str) -> None:
        self._q.put({
            "type": "error",
            "current": 0,
            "total": 0,
            "stage": "",
            "message": message,
            "row": None,
            "summary": None,
        })

    def _post_complete(
        self,
        rows: list[dict],
        cancelled: bool,
        summary: dict | None = None,
    ) -> None:
        self._q.put({
            "type": "complete",
            "current": len(rows),
            "total": len(rows),
            "stage": "send" if summary else "generate",
            "message": "Batch cancelled." if cancelled else "Batch complete.",
            "row": None,
            "summary": summary or {},
        })

    @staticmethod
    def _find_resume_checkpoint(
        log_dir: str,
        profile_name: str,
        excel_hash: str,
        total_rows: int,
    ) -> dict | None:
        """
        Return the newest matching checkpoint for the same profile and Excel file.
        Batch IDs are timestamped, so resume must discover the previous checkpoint
        before a fresh batch ID is generated.
        """
        matches: list[dict] = []
        suffix = "_checkpoint.json"

        for filename in os.listdir(log_dir):
            if not filename.endswith(suffix):
                continue
            path = os.path.join(log_dir, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            if (
                data.get("profile_name") == profile_name
                and data.get("excel_hash") == excel_hash
                and data.get("total_rows") == total_rows
            ):
                matches.append(data)

        if not matches:
            return None
        return max(matches, key=lambda item: item.get("batch_id", ""))


def _value_or_na(value) -> str:
    """Return a user-facing value, using NA for missing mapped data."""
    if value is None:
        return "NA"
    text = str(value).strip()
    return text if text else "NA"



