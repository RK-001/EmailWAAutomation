"""
ui/workflow_tab.py
------------------
Workflow Tab — the daily-use tab for running a notice batch.

Flow:
  1. User selects a Client Profile from dropdown.
  2. User browses for the Excel file.
  3. App reads the Excel and shows a 5-row preview table.
  4. User selects which stages to run (Generate PDF / Email / WhatsApp).
  5. User clicks "Generate All" → Stage 1 starts in background thread.
  6. Progress bar + status label update in real time.
  7. Pause / Resume / Cancel buttons manage the worker thread.
  8. On Stage 1 complete → auto-switch to Preview tab.

Background polling:
  After Stage 1 starts, this tab calls self._poll_queue() every 150 ms
  via after() to drain the progress_queue without blocking the GUI.
"""

from __future__ import annotations

import os
import queue
from typing import TYPE_CHECKING

import customtkinter as ctk

from core.batch_runner import BatchRunner
from core.excel_reader import read_excel

if TYPE_CHECKING:
    from ui.app import BulkNoticeApp

# ── Layout constants ──────────────────────────────────────────────────────────

_PAD_X = 18
_PAD_Y = 6
_ENTRY_W = 360
_BTN_W = 110


class WorkflowTab:
    """Workflow (Generate) Tab widget."""

    def __init__(self, parent: ctk.CTkFrame, app: "BulkNoticeApp"):
        self._app = app
        self._cfg = app.config_manager
        self._runner: BatchRunner | None = None

        # State
        self._excel_path: str = ""
        self._preview_rows: list[dict] = []

        # Root frame fills the tab
        self._root = ctk.CTkFrame(parent, fg_color="transparent")
        self._root.pack(fill="both", expand=True, padx=8, pady=8)
        self._root.grid_columnconfigure(0, weight=1)

        self._build_ui()
        self.refresh_profiles()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        row = 0

        # ── Profile selector ──────────────────────────────────────────────────
        self._section_header("SELECT PROFILE & FILE", row)
        row += 1

        lf = ctk.CTkFrame(self._root, fg_color="transparent")
        lf.grid(row=row, column=0, sticky="w", padx=_PAD_X, pady=_PAD_Y)
        row += 1

        ctk.CTkLabel(lf, text="Client Profile:", width=130, anchor="e").pack(side="left", padx=(0, 8))

        self._profile_var = ctk.StringVar(value="-- select --")
        self._profile_menu = ctk.CTkOptionMenu(
            lf,
            values=["-- select --"],
            variable=self._profile_var,
            width=260,
            command=self._on_profile_selected,
        )
        self._profile_menu.pack(side="left")

        # ── Excel file picker ─────────────────────────────────────────────────
        ef = ctk.CTkFrame(self._root, fg_color="transparent")
        ef.grid(row=row, column=0, sticky="w", padx=_PAD_X, pady=_PAD_Y)
        row += 1

        ctk.CTkLabel(ef, text="Excel File:", width=130, anchor="e").pack(side="left", padx=(0, 8))

        self._excel_var = ctk.StringVar()
        ctk.CTkEntry(ef, textvariable=self._excel_var, width=_ENTRY_W, state="readonly").pack(side="left")
        ctk.CTkButton(ef, text="Browse…", width=_BTN_W, command=self._browse_excel).pack(
            side="left", padx=(6, 0)
        )

        # ── Row count + column validation info ────────────────────────────────
        self._file_info_var = ctk.StringVar(value="")
        ctk.CTkLabel(
            self._root,
            textvariable=self._file_info_var,
            font=ctk.CTkFont(size=11),
            text_color="gray60",
            anchor="w",
        ).grid(row=row, column=0, sticky="w", padx=_PAD_X + 138, pady=(0, 4))
        row += 1

        # ── 5-row preview table ───────────────────────────────────────────────
        self._section_header("EXCEL PREVIEW  (first 5 rows)", row)
        row += 1

        self._preview_frame = ctk.CTkFrame(self._root, height=130)
        self._preview_frame.grid(row=row, column=0, sticky="ew", padx=_PAD_X, pady=(0, 10))
        self._preview_frame.grid_columnconfigure(0, weight=1)
        self._preview_frame.grid_propagate(False)
        row += 1

        ctk.CTkLabel(
            self._preview_frame,
            text="Select a profile and Excel file to see a preview.",
            text_color="gray60",
            font=ctk.CTkFont(size=11),
        ).grid(row=0, column=0, padx=10, pady=10)

        # ── Stage toggles ─────────────────────────────────────────────────────
        self._section_header("STAGES TO RUN", row)
        row += 1

        toggles_frame = ctk.CTkFrame(self._root, fg_color="transparent")
        toggles_frame.grid(row=row, column=0, sticky="w", padx=_PAD_X, pady=(0, 8))
        row += 1

        self._gen_pdf_var = ctk.BooleanVar(value=True)
        self._send_email_var = ctk.BooleanVar(value=True)
        self._send_wa_var = ctk.BooleanVar(value=True)

        for var, label, tip in [
            (self._gen_pdf_var, "✅  Generate PDF", "Excel → Word → PDF (always required)"),
            (self._send_email_var, "📧  Send Email", "Attach PDF and send via Gmail"),
            (self._send_wa_var, "💬  Send WhatsApp", "Send notification via AiSensy"),
        ]:
            frame = ctk.CTkFrame(toggles_frame, fg_color="transparent")
            frame.pack(side="left", padx=(0, 22))
            ctk.CTkCheckBox(frame, text=label, variable=var).pack(side="top", anchor="w")
            ctk.CTkLabel(
                frame, text=tip, font=ctk.CTkFont(size=10), text_color="gray60",
            ).pack(side="top", anchor="w")

        # ── Action buttons ────────────────────────────────────────────────────
        action_frame = ctk.CTkFrame(self._root, fg_color="transparent")
        action_frame.grid(row=row, column=0, sticky="w", padx=_PAD_X, pady=(4, 8))
        row += 1

        self._start_btn = ctk.CTkButton(
            action_frame,
            text="▶  Generate All",
            width=160,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._start_generate,
        )
        self._start_btn.pack(side="left", padx=(0, 10))

        self._pause_btn = ctk.CTkButton(
            action_frame,
            text="⏸  Pause",
            width=90,
            fg_color="gray50",
            command=self._toggle_pause,
            state="disabled",
        )
        self._pause_btn.pack(side="left", padx=(0, 6))

        self._cancel_btn = ctk.CTkButton(
            action_frame,
            text="✖  Cancel",
            width=90,
            fg_color="#c0392b",
            hover_color="#922b21",
            command=self._cancel,
            state="disabled",
        )
        self._cancel_btn.pack(side="left")

        # ── Progress bar ──────────────────────────────────────────────────────
        self._progress = ctk.CTkProgressBar(self._root, width=600)
        self._progress.grid(row=row, column=0, sticky="w", padx=_PAD_X, pady=(6, 2))
        self._progress.set(0)
        row += 1

        self._progress_label_var = ctk.StringVar(value="")
        ctk.CTkLabel(
            self._root,
            textvariable=self._progress_label_var,
            font=ctk.CTkFont(size=11),
            anchor="w",
        ).grid(row=row, column=0, sticky="w", padx=_PAD_X, pady=(0, 6))

    def _section_header(self, title: str, row: int) -> None:
        ctk.CTkLabel(
            self._root, text=title,
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).grid(row=row, column=0, sticky="w", padx=_PAD_X, pady=(12, 2))

    # ── Profile management ────────────────────────────────────────────────────

    def refresh_profiles(self) -> None:
        """Rebuild the profile dropdown from config. Called on profile save/delete."""
        names = self._cfg.list_profile_names()
        options = names if names else ["-- no profiles --"]
        self._profile_menu.configure(values=["-- select --"] + options)
        current = self._profile_var.get()
        if current not in options:
            self._profile_var.set("-- select --")

    def _on_profile_selected(self, _: str) -> None:
        """Re-validate the Excel file against the newly selected profile."""
        if self._excel_path:
            self._validate_and_preview(self._excel_path)

    # ── File browsing ─────────────────────────────────────────────────────────

    def _browse_excel(self) -> None:
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Select Excel file for this batch",
            filetypes=[("Excel workbooks", "*.xlsx"), ("All files", "*.*")],
        )
        if path:
            self._excel_path = path
            self._excel_var.set(os.path.basename(path))
            self._validate_and_preview(path)

    def _validate_and_preview(self, excel_path: str) -> None:
        """Read Excel headers + first 5 rows; update file info + preview table."""
        profile_name = self._profile_var.get()
        if profile_name in ("-- select --", "-- no profiles --"):
            self._file_info_var.set("⚠  Select a profile first.")
            return

        profile = self._cfg.get_profile(profile_name)
        if profile is None:
            return

        col_mapping = profile.get("column_mapping") or {}

        try:
            rows = read_excel(excel_path, column_mapping=col_mapping)
        except Exception as exc:
            self._file_info_var.set(f"❌  {exc}")
            self._clear_preview()
            return

        self._preview_rows = rows
        total = len(rows)

        # Basic validation info
        self._file_info_var.set(
            f"✅  {total} row{'s' if total != 1 else ''} loaded   "
            f"({os.path.basename(excel_path)})"
        )

        self._render_preview(rows[:5], col_mapping)

    # ── Preview table rendering ───────────────────────────────────────────────

    def _clear_preview(self) -> None:
        for w in self._preview_frame.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self._preview_frame,
            text="No data to preview.",
            text_color="gray60",
        ).grid(row=0, column=0, padx=10, pady=10)

    def _render_preview(self, rows: list[dict], col_mapping: dict) -> None:
        """Render a compact table of up to 5 rows inside the preview frame."""
        for w in self._preview_frame.winfo_children():
            w.destroy()

        if not rows:
            self._clear_preview()
            return

        # Determine columns to show (prefer standard keys that are mapped)
        show_keys = [k for k in ("NAME", "EMAILID", "MOBILENO", "AMOUNT", "ACCOUNTNO")
                     if k in (rows[0] or {})]
        if not show_keys:
            show_keys = list(rows[0].keys())[:5]

        header_font = ctk.CTkFont(size=11, weight="bold")
        cell_font = ctk.CTkFont(size=11)

        container = ctk.CTkScrollableFrame(
            self._preview_frame, orientation="horizontal", height=110
        )
        container.pack(fill="both", expand=True, padx=4, pady=4)

        # Header row
        for col_idx, key in enumerate(show_keys):
            ctk.CTkLabel(
                container, text=key, font=header_font, width=120, anchor="w",
            ).grid(row=0, column=col_idx, padx=(6, 0), pady=2, sticky="w")

        # Data rows
        for r_idx, row in enumerate(rows):
            for col_idx, key in enumerate(show_keys):
                val = str(row.get(key) or "")
                val = val[:18] + "…" if len(val) > 18 else val
                ctk.CTkLabel(
                    container, text=val, font=cell_font, width=120, anchor="w",
                    text_color="gray70",
                ).grid(row=r_idx + 1, column=col_idx, padx=(6, 0), pady=1, sticky="w")

    # ── Batch control ─────────────────────────────────────────────────────────

    def is_batch_running(self) -> bool:
        """True if the batch worker thread is alive."""
        return self._runner is not None and self._runner.is_running()

    def _start_generate(self) -> None:
        """Validate inputs then kick off Stage 1 in a background thread."""
        profile_name = self._profile_var.get()
        if profile_name in ("-- select --", "-- no profiles --", ""):
            from tkinter import messagebox
            messagebox.showwarning("No Profile", "Select a client profile before starting.")
            return

        if not self._excel_path or not os.path.exists(self._excel_path):
            from tkinter import messagebox
            messagebox.showwarning("No Excel File", "Browse to an Excel file before starting.")
            return

        if not self._gen_pdf_var.get():
            from tkinter import messagebox
            messagebox.showwarning(
                "PDF Required",
                "PDF generation is mandatory for all workflows.\n"
                "Please keep 'Generate PDF' checked.",
            )
            self._gen_pdf_var.set(True)
            return

        # Validate profile template exists
        profile = self._cfg.get_profile(profile_name)
        template_path = self._cfg.resolve_path((profile or {}).get("template_path", ""))
        if not template_path or not os.path.exists(template_path):
            from tkinter import messagebox
            messagebox.showerror(
                "Missing Template",
                f"Template file not found:\n{template_path}\n\n"
                "Update the profile in the Profiles tab.",
            )
            return

        # Determine output/log folders
        settings = self._cfg.get("settings") or {}
        output_dir = settings.get("output_folder", "./output")
        log_dir = settings.get("log_folder", "./logs")

        # Resolve relative paths from the config.json directory
        base = self._cfg.get_base_dir()
        if not os.path.isabs(output_dir):
            output_dir = os.path.join(base, output_dir)
        if not os.path.isabs(log_dir):
            log_dir = os.path.join(base, log_dir)

        # Build fresh runner + start
        self._runner = BatchRunner(self._cfg, self._app.progress_queue)

        self._set_running_state(True)
        self._progress.set(0)
        self._progress_label_var.set("Preparing generation…")
        self._app.set_status("Preparing generation…")

        # Store for polling closure
        self._output_dir = output_dir
        self._log_dir = log_dir
        self._current_profile = profile_name

        # Let Tk repaint the UI before starting the worker. This avoids the
        # brief "blank window" effect some users see when heavy startup work
        # begins immediately inside the same button-click event.
        self._app.update_idletasks()
        self._app.after(
            10,
            lambda: self._begin_generate(
                profile_name=profile_name,
                output_dir=output_dir,
                log_dir=log_dir,
            ),
        )

    def _begin_generate(self, profile_name: str, output_dir: str, log_dir: str) -> None:
        """Start the background generate worker after the UI has repainted."""
        try:
            if self._runner is None:
                raise RuntimeError("Batch runner is not initialized.")
            self._runner.start_generate(
                excel_path=self._excel_path,
                profile_name=profile_name,
                output_dir=output_dir,
                log_dir=log_dir,
            )
        except Exception as exc:
            from tkinter import messagebox
            messagebox.showerror("Start Error", str(exc))
            self._set_running_state(False)
            return

        self._progress_label_var.set("Starting generation…")
        self._app.set_status("Starting generation…")

        # Begin polling the progress queue
        self._app.after(150, self._poll_queue)

    def _toggle_pause(self) -> None:
        if self._runner is None:
            return
        if self._pause_btn.cget("text").startswith("⏸"):
            self._runner.pause()
            self._pause_btn.configure(text="▶  Resume")
            self._progress_label_var.set("Paused — click Resume to continue.")
        else:
            self._runner.resume()
            self._pause_btn.configure(text="⏸  Pause")

    def _cancel(self) -> None:
        if self._runner:
            self._runner.cancel()

    # ── Progress queue polling ────────────────────────────────────────────────

    def _poll_queue(self) -> None:
        """
        Drain the progress queue and update UI.
        Reschedules itself every 150 ms while the batch is running.
        """
        q = self._app.progress_queue
        try:
            while True:
                msg = q.get_nowait()
                self._handle_progress_msg(msg)
        except queue.Empty:
            pass

        # Reschedule if still running
        if self.is_batch_running():
            self._app.after(150, self._poll_queue)

    def _handle_progress_msg(self, msg: dict) -> None:
        """Process one message from the progress queue."""
        msg_type = msg.get("type", "")
        current = msg.get("current", 0)
        total = msg.get("total", 1) or 1
        stage = msg.get("stage", "")
        message = msg.get("message", "")

        if msg_type == "progress":
            self._progress.set(current / total)
            self._progress_label_var.set(message)
            self._app.set_status(message)

        elif msg_type == "stage_complete":
            # Stage 1 done → hand off to Preview tab
            generated = (msg.get("summary") or {}).get("generated", [])
            self._progress.set(1.0)
            self._progress_label_var.set(f"✅  Generation complete — {len(generated)} rows.")
            self._set_running_state(False)

            # Determine log path
            cp_mgr = self._runner._checkpoint_mgr if self._runner else None
            batch_id = cp_mgr._batch_id if cp_mgr else ""
            log_path = os.path.join(self._log_dir, f"{batch_id}.json") if batch_id else ""

            self._app.go_to_preview(
                generated_rows=generated,
                batch_id=batch_id,
                profile_name=self._current_profile,
                log_path=log_path,
            )

        elif msg_type == "error":
            self._progress_label_var.set(f"❌  {message}")
            self._set_running_state(False)
            from tkinter import messagebox
            messagebox.showerror("Batch Error", message)

        elif msg_type == "complete":
            # Cancelled during generation
            self._progress_label_var.set(message)
            self._set_running_state(False)

    # ── UI state helpers ──────────────────────────────────────────────────────

    def _set_running_state(self, running: bool) -> None:
        """Toggle button states based on whether a batch is running."""
        if running:
            self._start_btn.configure(state="disabled")
            self._pause_btn.configure(state="normal", text="⏸  Pause")
            self._cancel_btn.configure(state="normal")
        else:
            self._start_btn.configure(state="normal")
            self._pause_btn.configure(state="disabled", text="⏸  Pause")
            self._cancel_btn.configure(state="disabled")
