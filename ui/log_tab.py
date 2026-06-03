"""
ui/log_tab.py
-------------
Logs Tab — real-time send monitoring + post-batch analysis.

Features:
  - Live table: one row per recipient, updated as sends complete
  - Per-recipient Email ✅/❌ and WhatsApp ✅/❌ status
  - Filter dropdown: All | Email Failed | WhatsApp Failed | Both Failed
  - Export CSV button (uses BatchLogger.export_csv)
  - Retry Failed button — re-sends only the failed channel(s)
  - Summary footer: total | Email ✅ | Email ❌ | WA ✅ | WA ❌

The tab polls the app's progress_queue for "row_done" and "complete" messages
while Stage 2 (send) is running.
"""

from __future__ import annotations

import os
import queue
from typing import TYPE_CHECKING

import customtkinter as ctk

if TYPE_CHECKING:
    from ui.app import BulkNoticeApp

# ── Table column definitions ──────────────────────────────────────────────────

# (header, result_key, width)
_COLUMNS: list[tuple[str, str, int]] = [
    ("#",           "row_index", 40),
    ("Name",        "NAME",     150),
    ("Email Status","email_status", 110),
    ("WA Status",   "wa_status", 100),
    ("Time",        "timestamp",  90),
    ("Email Error", "email_error",160),
    ("WA Error",    "wa_error",  160),
]

_FILTER_OPTIONS = ["All", "Email Failed", "WA Failed", "Both Failed"]

_STATUS_COLORS = {
    "sent":    ("#1a7a1a", "#2ecc71"),   # (light-mode, dark-mode) green
    "failed":  ("#b22222", "#e74c3c"),   # red
    "skipped": ("#888888", "#aaaaaa"),   # gray
}

_PAD_X = 10
_PAD_Y = 3


class LogTab:
    """Logs Tab widget."""

    def __init__(self, parent: ctk.CTkFrame, app: "BulkNoticeApp"):
        self._app = app
        self._cfg = app.config_manager

        # All result entries accumulated so far
        self._entries: list[dict] = []
        self._batch_id: str = ""
        self._log_path: str = ""
        self._total_expected: int = 0

        # Filtered view (entries currently shown in the table)
        self._filtered: list[dict] = []

        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        self._build_ui(parent)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self, parent: ctk.CTkFrame) -> None:
        # ── Top bar ───────────────────────────────────────────────────────────
        top_bar = ctk.CTkFrame(parent, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=_PAD_X, pady=(8, 4))

        self._batch_label = ctk.CTkLabel(
            top_bar,
            text="No batch results yet.",
            font=ctk.CTkFont(size=12),
            text_color="gray60",
        )
        self._batch_label.pack(side="left", padx=(0, 20))

        # Filter dropdown
        ctk.CTkLabel(top_bar, text="Filter:", font=ctk.CTkFont(size=12)).pack(side="left")

        self._filter_var = ctk.StringVar(value="All")
        ctk.CTkOptionMenu(
            top_bar,
            values=_FILTER_OPTIONS,
            variable=self._filter_var,
            width=160,
            command=self._apply_filter,
        ).pack(side="left", padx=(4, 14))

        # Action buttons
        ctk.CTkButton(
            top_bar, text="📥  Export CSV", width=120,
            command=self._export_csv,
        ).pack(side="left", padx=(0, 8))

        self._retry_btn = ctk.CTkButton(
            top_bar, text="🔄  Retry Failed", width=130,
            fg_color="gray50",
            command=self._retry_failed,
            state="disabled",
        )
        self._retry_btn.pack(side="left")

        # ── Progress bar (visible during send) ───────────────────────────────
        self._send_progress = ctk.CTkProgressBar(parent, width=500)
        self._send_progress.grid(row=2, column=0, sticky="w", padx=_PAD_X, pady=(2, 2))
        self._send_progress.set(0)
        self._send_progress.grid_remove()   # Hidden until send starts

        self._send_progress_var = ctk.StringVar(value="")
        self._send_progress_label = ctk.CTkLabel(
            parent, textvariable=self._send_progress_var,
            font=ctk.CTkFont(size=11), anchor="w",
        )
        self._send_progress_label.grid(row=3, column=0, sticky="w", padx=_PAD_X)
        self._send_progress_label.grid_remove()

        # ── Table (scrollable) ────────────────────────────────────────────────
        self._table_frame = ctk.CTkScrollableFrame(parent, label_text="")
        self._table_frame.grid(row=1, column=0, sticky="nsew", padx=_PAD_X, pady=4)

        self._render_empty_table()

        # ── Summary footer ────────────────────────────────────────────────────
        footer = ctk.CTkFrame(parent, height=34, corner_radius=0)
        footer.grid(row=4, column=0, sticky="ew")
        footer.grid_columnconfigure(0, weight=1)

        self._summary_var = ctk.StringVar(value="")
        ctk.CTkLabel(
            footer,
            textvariable=self._summary_var,
            font=ctk.CTkFont(size=11),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=14)

    # ── Public API ────────────────────────────────────────────────────────────

    def prepare_for_send(self, total: int, batch_id: str, log_path: str) -> None:
        """
        Called by PreviewTab before Stage 2 starts.
        Resets the table and shows the progress bar.
        """
        self._entries = []
        self._batch_id = batch_id
        self._log_path = log_path
        self._total_expected = total

        self._batch_label.configure(
            text=f"Batch: {batch_id}  |  Sending {total} notice(s)…",
            text_color=("black", "white"),
        )
        self._render_empty_table()
        self._summary_var.set("")

        self._send_progress.set(0)
        self._send_progress.grid()
        self._send_progress_var.set("Initializing send…")
        self._send_progress_label.grid()

    def load_batch_log(self, batch_id: str, log_path: str) -> None:
        """
        Load a completed batch log from disk (for viewing past batches).
        """
        if not log_path or not os.path.exists(log_path):
            return
        try:
            import json
            with open(log_path, "r", encoding="utf-8") as f:
                self._entries = [self._normalize_entry(e) for e in json.load(f)]
        except Exception:
            return

        self._batch_id = batch_id
        self._log_path = log_path
        self._apply_filter("All")
        self._update_summary()

    def start_polling(self) -> None:
        """Begin draining the progress queue for Stage 2 messages."""
        self._app.after(150, self._poll_queue)

    # ── Queue polling ─────────────────────────────────────────────────────────

    def _poll_queue(self) -> None:
        q = self._app.progress_queue
        try:
            while True:
                msg = q.get_nowait()
                self._handle_message(msg)
        except queue.Empty:
            pass

        # Reschedule while runner is alive
        runner = self._app.workflow_tab._runner
        if runner and runner.is_running():
            self._app.after(150, self._poll_queue)

    def _handle_message(self, msg: dict) -> None:
        msg_type = msg.get("type", "")
        current = msg.get("current", 0)
        total = (msg.get("total", 1) or 1)
        message = msg.get("message", "")

        if msg_type == "row_done":
            row_data = self._normalize_entry(msg.get("row") or {})
            self._entries.append(row_data)
            # Append to table (incremental — faster than full rebuild)
            self._append_table_row(row_data, len(self._entries))
            self._send_progress.set(current / total)
            self._send_progress_var.set(message)
            self._app.set_status(message)
            self._update_summary()

        elif msg_type == "progress":
            # Non-row progress (e.g., cleanup)
            self._send_progress_var.set(message)
            self._app.set_status(message)

        elif msg_type == "complete":
            self._send_progress.set(1.0)
            self._send_progress_var.set(f"✅  {message}")
            self._batch_label.configure(
                text=f"Batch: {self._batch_id}  |  Complete.",
            )
            # Hide progress bar after a moment
            self._app.after(3000, self._hide_progress)
            self._retry_btn.configure(state="normal")
            self._update_summary()

        elif msg_type == "error":
            self._send_progress_var.set(f"❌  {message}")
            self._retry_btn.configure(state="normal")

    def _hide_progress(self) -> None:
        self._send_progress.grid_remove()
        self._send_progress_label.grid_remove()

    # ── Table rendering ───────────────────────────────────────────────────────

    def _render_empty_table(self) -> None:
        for w in self._table_frame.winfo_children():
            w.destroy()

        hdr_font = ctk.CTkFont(size=11, weight="bold")
        for col_idx, (hdr, _, w) in enumerate(_COLUMNS):
            ctk.CTkLabel(
                self._table_frame, text=hdr, font=hdr_font, width=w, anchor="w",
            ).grid(row=0, column=col_idx, padx=(4, 0), pady=4, sticky="w")

        ctk.CTkLabel(
            self._table_frame,
            text="Waiting for send to start…",
            text_color="gray60",
            font=ctk.CTkFont(size=11),
        ).grid(row=1, column=0, columnspan=len(_COLUMNS), padx=8, pady=8)

    def _append_table_row(self, entry: dict, gui_row: int) -> None:
        """Append a single result row to the table (incremental update)."""
        # Remove the "waiting" placeholder on first row
        if gui_row == 1:
            for w in self._table_frame.winfo_children():
                info = w.grid_info()
                if info.get("row") == 1 and info.get("column") == 0:
                    # Only destroy if it's the placeholder label
                    if isinstance(w, ctk.CTkLabel) and "Waiting" in (w.cget("text") or ""):
                        w.destroy()
                        break

        cell_font = ctk.CTkFont(size=11)

        for col_idx, (_, key, width) in enumerate(_COLUMNS):
            if key == "row_index":
                text = str((entry.get("index") or 0) + 1)
                color = None
            elif key in ("email_status", "wa_status"):
                val = entry.get(key, "skipped")
                text = {"sent": "✅ Sent", "failed": "❌ Failed", "skipped": "— Skip"}.get(val, val)
                colors = _STATUS_COLORS.get(val, _STATUS_COLORS["skipped"])
                color = colors  # tuple (light, dark)
            elif key == "timestamp":
                text = self._format_time(entry.get("timestamp") or "")
                color = ("gray60", "gray60")
            else:
                raw = str(entry.get(key) or "")
                text = raw[:22] + "…" if len(raw) > 22 else raw
                color = ("gray60", "gray60")

            kwargs = {"text": text, "font": cell_font, "width": width, "anchor": "w"}
            if color:
                kwargs["text_color"] = color

            ctk.CTkLabel(self._table_frame, **kwargs).grid(
                row=gui_row, column=col_idx, padx=(4, 0), pady=_PAD_Y, sticky="w"
            )

    def _rebuild_table(self, entries: list[dict]) -> None:
        """Full table rebuild (used after filtering)."""
        for w in self._table_frame.winfo_children():
            w.destroy()

        hdr_font = ctk.CTkFont(size=11, weight="bold")
        for col_idx, (hdr, _, w) in enumerate(_COLUMNS):
            ctk.CTkLabel(
                self._table_frame, text=hdr, font=hdr_font, width=w, anchor="w",
            ).grid(row=0, column=col_idx, padx=(4, 0), pady=4, sticky="w")

        if not entries:
            ctk.CTkLabel(
                self._table_frame,
                text="No entries match the current filter.",
                text_color="gray60",
            ).grid(row=1, column=0, columnspan=len(_COLUMNS), padx=8, pady=8)
            return

        for r_idx, entry in enumerate(entries):
            self._append_table_row(entry, r_idx + 1)

    # ── Filter ────────────────────────────────────────────────────────────────

    def _apply_filter(self, filter_val: str | None = None) -> None:
        f = filter_val or self._filter_var.get()
        if f == "All":
            self._filtered = list(self._entries)
        elif f == "Email Failed":
            self._filtered = [e for e in self._entries if e.get("email_status") == "failed"]
        elif f == "WA Failed":
            self._filtered = [e for e in self._entries if e.get("wa_status") == "failed"]
        elif f == "Both Failed":
            self._filtered = [
                e for e in self._entries
                if e.get("email_status") == "failed" and e.get("wa_status") == "failed"
            ]
        else:
            self._filtered = list(self._entries)

        self._rebuild_table(self._filtered)

    # ── Summary ───────────────────────────────────────────────────────────────

    def _update_summary(self) -> None:
        if not self._entries:
            self._summary_var.set("")
            return
        total = len(self._entries)
        email_ok  = sum(1 for e in self._entries if e.get("email_status") == "sent")
        email_err = sum(1 for e in self._entries if e.get("email_status") == "failed")
        wa_ok     = sum(1 for e in self._entries if e.get("wa_status") == "sent")
        wa_err    = sum(1 for e in self._entries if e.get("wa_status") == "failed")

        self._summary_var.set(
            f"Total: {total}  |  "
            f"Email: {email_ok} ✅  {email_err} ❌  |  "
            f"WhatsApp: {wa_ok} ✅  {wa_err} ❌"
        )

    # ── Actions ───────────────────────────────────────────────────────────────

    def _export_csv(self) -> None:
        """Export current batch log to CSV using BatchLogger."""
        if not self._entries:
            from tkinter import messagebox
            messagebox.showinfo("No Data", "No log entries to export.")
            return

        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"{self._batch_id}_log.csv",
            title="Export Log as CSV",
        )
        if not path:
            return

        try:
            from utils.logger import BatchLogger
            logger = BatchLogger(self._log_path)
            logger.export_csv(path)
            from tkinter import messagebox
            messagebox.showinfo("Exported", f"Log saved to:\n{path}")
        except Exception as exc:
            from tkinter import messagebox
            messagebox.showerror("Export Error", str(exc))

    def _retry_failed(self) -> None:
        """Retry only failed channels for failed rows."""
        failed_rows: list[dict] = []
        for entry in self._entries:
            email_failed = entry.get("email_status") == "failed"
            wa_failed = entry.get("wa_status") == "failed"
            if email_failed or wa_failed:
                # Tag which channels need retrying
                row_data = entry.get("row_data") if isinstance(entry.get("row_data"), dict) else {}
                row_copy = {**row_data, **entry}
                row_copy.pop("row_data", None)
                row_copy["_retry_email"] = email_failed
                row_copy["_retry_wa"] = wa_failed
                # Reconstruct to match row format expected by BatchRunner
                row_copy["pdf_path"] = entry.get("pdf_path", "")
                row_copy["drive_link"] = entry.get("drive_link", "")
                failed_rows.append(row_copy)

        if not failed_rows:
            from tkinter import messagebox
            messagebox.showinfo("Nothing to Retry", "No failed rows found in this batch.")
            return

        email_failed_count = sum(1 for r in failed_rows if r.get("_retry_email"))
        wa_failed_count    = sum(1 for r in failed_rows if r.get("_retry_wa"))

        from tkinter import messagebox
        if not messagebox.askyesno(
            "Retry Failed",
            f"Retry {len(failed_rows)} rows:\n"
            f"  • {email_failed_count} Email failures\n"
            f"  • {wa_failed_count} WhatsApp failures\n\n"
            "Only failed channels will be retried.",
        ):
            return

        # For retry: send_email = True only if ANY row has email failure
        retry_email = email_failed_count > 0
        retry_wa    = wa_failed_count > 0

        runner = self._app.workflow_tab._runner
        if runner is None or runner.is_running():
            from tkinter import messagebox
            messagebox.showwarning(
                "Runner Busy",
                "Cannot retry while a batch is running."
            )
            return

        # Use the profile's notice type for approval
        profile = self._cfg.get_profile(self._app.current_profile_name)
        notice_type = (profile or {}).get("notice_type", "EMI_DEFAULT")

        from ui.dialogs import ApprovalDialog
        dlg = ApprovalDialog(self._app, default_notice_type=notice_type)
        self._app.wait_window(dlg)
        if not dlg.approved:
            return

        self.prepare_for_send(
            total=len(failed_rows),
            batch_id=self._batch_id,
            log_path=self._log_path,
        )

        try:
            runner.start_send(
                approved_rows=failed_rows,
                notice_type=dlg.notice_type,
                send_email=retry_email,
                send_whatsapp=retry_wa,
            )
        except Exception as exc:
            from tkinter import messagebox
            messagebox.showerror("Retry Error", str(exc))
            return

        self.start_polling()

    @staticmethod
    def _normalize_entry(entry: dict) -> dict:
        """Map persisted log fields and live row fields into one UI shape."""
        row_data = entry.get("row_data") if isinstance(entry.get("row_data"), dict) else {}
        normalized = {**row_data, **entry}
        normalized.setdefault("row_index", normalized.get("index", 0))
        normalized.setdefault("NAME", normalized.get("name", ""))
        normalized.setdefault("EMAILID", normalized.get("email", ""))
        normalized.setdefault("MOBILENO", normalized.get("phone", ""))
        normalized.setdefault("wa_status", normalized.get("whatsapp_status", "skipped"))
        normalized.setdefault("wa_error", normalized.get("whatsapp_error", ""))
        return normalized

    @staticmethod
    def _format_time(timestamp: str) -> str:
        """Show HH:MM:SS for ISO timestamps, otherwise keep short raw text."""
        if "T" in timestamp:
            return timestamp.split("T", 1)[1][:8]
        if " " in timestamp:
            return timestamp.rsplit(" ", 1)[-1][:8]
        return timestamp[:8]
