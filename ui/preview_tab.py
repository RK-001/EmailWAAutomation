"""
ui/preview_tab.py
-----------------
Preview Tab — review generated notices before sending.

After Stage 1 (Generate) completes, this tab is populated with a table
showing every generated row. The user can:
  - Review each row (name, email, phone, amount, PDF status)
  - Open a PDF directly (os.startfile → system default viewer)
  - Exclude rows by unchecking the checkbox
  - Click "Send All" or "Send Selected" to proceed to Stage 2

Before sending starts, the ApprovalDialog is shown as a compliance gate.
On approval, Stage 2 kicks off via BatchRunner.start_send() and the
app switches to the Logs tab for real-time monitoring.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import customtkinter as ctk

if TYPE_CHECKING:
    from ui.app import BulkNoticeApp

# ── Layout constants ──────────────────────────────────────────────────────────

# Table column definitions: (header_label, row_key, min_width)
_COLUMNS: list[tuple[str, str, int]] = [
    ("#",        "row_index", 40),
    ("Name",     "NAME",     160),
    ("Email",    "EMAILID",  180),
    ("Phone",    "MOBILENO", 110),
    ("Amount",   "AMOUNT",    90),
    ("PDF",      "_pdf_ok",   60),
]

_PAD_X = 12
_PAD_Y = 4


class PreviewTab:
    """Preview Tab widget."""

    def __init__(self, parent: ctk.CTkFrame, app: "BulkNoticeApp"):
        self._app = app
        self._cfg = app.config_manager

        # Batch data
        self._rows: list[dict] = []
        self._batch_id: str = ""
        self._profile_name: str = ""

        # Per-row checkbox state (row_index → BooleanVar)
        self._row_vars: dict[int, ctk.BooleanVar] = {}

        # Root layout
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        self._build_ui(parent)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self, parent: ctk.CTkFrame) -> None:
        # ── Top bar: batch info + select all + send buttons ───────────────────
        top_bar = ctk.CTkFrame(parent, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=_PAD_X, pady=(10, 4))
        top_bar.grid_columnconfigure(2, weight=1)

        self._batch_label = ctk.CTkLabel(
            top_bar,
            text="No batch loaded.  Run a batch in the Workflow tab first.",
            font=ctk.CTkFont(size=12),
            text_color="gray60",
        )
        self._batch_label.grid(row=0, column=0, sticky="w", padx=(0, 20))

        ctk.CTkButton(
            top_bar, text="Select All",  width=90,
            command=self._select_all,
        ).grid(row=0, column=1, padx=(0, 4))

        ctk.CTkButton(
            top_bar, text="Deselect All", width=100,
            fg_color="gray50",
            command=self._deselect_all,
        ).grid(row=0, column=2, padx=(0, 12), sticky="w")

        # ── Stage-2 options ───────────────────────────────────────────────────
        opts_frame = ctk.CTkFrame(parent, fg_color="transparent")
        opts_frame.grid(row=2, column=0, sticky="w", padx=_PAD_X, pady=(4, 4))

        self._send_email_var = ctk.BooleanVar(value=True)
        self._send_wa_var = ctk.BooleanVar(value=True)

        ctk.CTkCheckBox(opts_frame, text="📧  Send Email",    variable=self._send_email_var).pack(side="left", padx=(0, 16))
        ctk.CTkCheckBox(opts_frame, text="💬  Send WhatsApp", variable=self._send_wa_var).pack(side="left")

        # ── Table (scrollable) ────────────────────────────────────────────────
        self._table_frame = ctk.CTkScrollableFrame(parent, label_text="")
        self._table_frame.grid(row=1, column=0, sticky="nsew", padx=_PAD_X, pady=4)

        self._render_empty_table()

        # ── Bottom bar: send buttons + status ─────────────────────────────────
        bottom_bar = ctk.CTkFrame(parent, fg_color="transparent")
        bottom_bar.grid(row=3, column=0, sticky="ew", padx=_PAD_X, pady=(4, 10))

        self._send_all_btn = ctk.CTkButton(
            bottom_bar,
            text="▶▶  Send All",
            width=140,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=lambda: self._start_send(selected_only=False),
            state="disabled",
        )
        self._send_all_btn.pack(side="left", padx=(0, 8))

        self._send_sel_btn = ctk.CTkButton(
            bottom_bar,
            text="▶  Send Selected",
            width=140,
            command=lambda: self._start_send(selected_only=True),
            state="disabled",
        )
        self._send_sel_btn.pack(side="left", padx=(0, 20))

        self._send_status_var = ctk.StringVar(value="")
        ctk.CTkLabel(
            bottom_bar,
            textvariable=self._send_status_var,
            font=ctk.CTkFont(size=12),
        ).pack(side="left")

    # ── Public API ────────────────────────────────────────────────────────────

    def load_batch(
        self,
        generated_rows: list[dict],
        batch_id: str,
        profile_name: str,
    ) -> None:
        """
        Populate the table with Stage 1 results.
        Called by app.go_to_preview() after generation completes.
        """
        self._rows = generated_rows
        self._batch_id = batch_id
        self._profile_name = profile_name
        self._row_vars = {}

        total = len(generated_rows)
        failed = sum(1 for r in generated_rows if not r.get("pdf_path"))

        self._batch_label.configure(
            text=f"Batch: {batch_id}  |  Profile: {profile_name}  "
                 f"|  {total} rows  |  {failed} generation error(s)",
            text_color=("black", "white") if not failed else "orange",
        )

        self._render_table(generated_rows)
        self._send_all_btn.configure(state="normal")
        self._send_sel_btn.configure(state="normal")

    # ── Table rendering ───────────────────────────────────────────────────────

    def _render_empty_table(self) -> None:
        for w in self._table_frame.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self._table_frame,
            text="No batch loaded. Run a batch in the Workflow tab first.",
            text_color="gray60",
            font=ctk.CTkFont(size=12),
        ).grid(row=0, column=0, padx=16, pady=16)

    def _render_table(self, rows: list[dict]) -> None:
        """Build the preview table with one row per generated notice."""
        for w in self._table_frame.winfo_children():
            w.destroy()

        hdr_font = ctk.CTkFont(size=11, weight="bold")
        cell_font = ctk.CTkFont(size=11)

        # ── Header row ────────────────────────────────────────────────────────
        # Column 0 = checkbox placeholder
        ctk.CTkLabel(
            self._table_frame, text="✓", font=hdr_font, width=30,
        ).grid(row=0, column=0, padx=(4, 0), pady=4, sticky="w")

        for col_idx, (hdr, _, min_w) in enumerate(_COLUMNS):
            ctk.CTkLabel(
                self._table_frame, text=hdr, font=hdr_font, width=min_w, anchor="w",
            ).grid(row=0, column=col_idx + 1, padx=(4, 0), pady=4, sticky="w")

        # "Open PDF" header
        ctk.CTkLabel(
            self._table_frame, text="", font=hdr_font, width=80,
        ).grid(row=0, column=len(_COLUMNS) + 1, padx=(4, 0), pady=4, sticky="w")

        # ── Data rows ─────────────────────────────────────────────────────────
        for r_idx, row in enumerate(rows):
            gui_row = r_idx + 1
            row_index = row.get("row_index", r_idx)

            # Checkbox
            var = ctk.BooleanVar(value=True)
            self._row_vars[row_index] = var
            ctk.CTkCheckBox(
                self._table_frame, text="", variable=var, width=30,
            ).grid(row=gui_row, column=0, padx=(4, 0), pady=2, sticky="w")

            # Data cells
            for col_idx, (_, key, min_w) in enumerate(_COLUMNS):
                if key == "row_index":
                    text = str(row_index + 1)
                elif key == "_pdf_ok":
                    text = "✅" if row.get("pdf_path") else "❌"
                else:
                    val = str(row.get(key) or "")
                    text = val[:20] + "…" if len(val) > 20 else val

                label_color = "gray60" if col_idx > 0 else None
                ctk.CTkLabel(
                    self._table_frame,
                    text=text,
                    font=cell_font,
                    width=min_w,
                    anchor="w",
                    text_color=label_color,
                ).grid(row=gui_row, column=col_idx + 1, padx=(4, 0), pady=2, sticky="w")

            # Open PDF button
            pdf_path = row.get("pdf_path", "")
            btn = ctk.CTkButton(
                self._table_frame,
                text="📄 Open",
                width=72,
                height=24,
                font=ctk.CTkFont(size=10),
                state="normal" if pdf_path and os.path.exists(pdf_path) else "disabled",
                command=lambda p=pdf_path: self._open_pdf(p),
            )
            btn.grid(row=gui_row, column=len(_COLUMNS) + 1, padx=(4, 8), pady=2, sticky="w")

    # ── Actions ───────────────────────────────────────────────────────────────

    def _select_all(self) -> None:
        for var in self._row_vars.values():
            var.set(True)

    def _deselect_all(self) -> None:
        for var in self._row_vars.values():
            var.set(False)

    def _open_pdf(self, pdf_path: str) -> None:
        """Open PDF with the system default viewer (no external dependencies)."""
        if not pdf_path or not os.path.exists(pdf_path):
            from tkinter import messagebox
            messagebox.showerror("File Not Found", f"PDF not found:\n{pdf_path}")
            return
        try:
            os.startfile(pdf_path)
        except Exception as exc:
            from tkinter import messagebox
            messagebox.showerror("Cannot Open PDF", str(exc))

    def _start_send(self, selected_only: bool) -> None:
        """
        Validate, show approval dialog, then kick off Stage 2.
        """
        if not self._rows:
            return

        # Determine which rows to send
        if selected_only:
            approved_rows = [
                r for r in self._rows
                if self._row_vars.get(r.get("row_index", -1), ctk.BooleanVar(value=True)).get()
            ]
        else:
            approved_rows = list(self._rows)

        skipped_no_pdf = [r for r in approved_rows if not r.get("pdf_path")]
        approved_rows = [r for r in approved_rows if r.get("pdf_path")]

        if not approved_rows:
            from tkinter import messagebox
            if skipped_no_pdf:
                messagebox.showwarning(
                    "No Generated Notices",
                    "Selected rows do not have generated PDF files. "
                    "Fix generation errors before sending.",
                )
            else:
                messagebox.showinfo("Nothing Selected", "No rows are selected for sending.")
            return

        if skipped_no_pdf:
            from tkinter import messagebox
            if not messagebox.askyesno(
                "Skip Failed Rows",
                f"{len(skipped_no_pdf)} selected row(s) have no generated PDF and will be skipped.\n\n"
                f"Continue with {len(approved_rows)} ready notice(s)?",
                icon="warning",
            ):
                return

        send_email = self._send_email_var.get()
        send_whatsapp = self._send_wa_var.get()

        if not send_email and not send_whatsapp:
            from tkinter import messagebox
            messagebox.showwarning(
                "No Channel",
                "Select at least one send channel (Email or WhatsApp).",
            )
            return

        if send_email and not any(str(r.get("EMAILID") or "").strip() for r in approved_rows):
            from tkinter import messagebox
            messagebox.showwarning(
                "Email Column Missing",
                "Email sending is selected, but EMAILID is not mapped or is blank "
                "for all selected rows.",
            )
            return

        if send_whatsapp and not any(str(r.get("MOBILENO") or "").strip() for r in approved_rows):
            from tkinter import messagebox
            messagebox.showwarning(
                "Mobile Column Missing",
                "WhatsApp sending is selected, but MOBILENO is not mapped or is blank "
                "for all selected rows.",
            )
            return

        # ── Lawyer approval gate ──────────────────────────────────────────────
        profile = self._cfg.get_profile(self._profile_name)
        default_type = (profile or {}).get("notice_type", "EMI_DEFAULT")

        from ui.dialogs import ApprovalDialog
        dlg = ApprovalDialog(self._app, default_notice_type=default_type)
        self._app.wait_window(dlg)

        if not dlg.approved:
            self._send_status_var.set("Send cancelled — approval not given.")
            return

        notice_type = dlg.notice_type

        # Reuse the BatchRunner created by WorkflowTab
        runner = self._app.workflow_tab._runner
        if runner is None:
            from tkinter import messagebox
            messagebox.showerror("No Runner", "Internal error: no batch runner available.")
            return

        # ── Disable send buttons, start send ─────────────────────────────────
        self._send_all_btn.configure(state="disabled")
        self._send_sel_btn.configure(state="disabled")
        self._send_status_var.set(f"Sending {len(approved_rows)} notices…")

        # Switch to Log tab immediately so user can watch
        self._app.log_tab.prepare_for_send(
            total=len(approved_rows),
            batch_id=self._batch_id,
            log_path=self._app.current_log_path,
        )
        self._app.go_to_logs()

        try:
            runner.start_send(
                approved_rows=approved_rows,
                notice_type=notice_type,
                send_email=send_email,
                send_whatsapp=send_whatsapp,
            )
        except Exception as exc:
            from tkinter import messagebox
            messagebox.showerror("Send Error", str(exc))
            self._send_status_var.set(f"❌  {exc}")
            self._send_all_btn.configure(state="normal")
            self._send_sel_btn.configure(state="normal")
            return

        # Hand off polling to LogTab
        self._app.log_tab.start_polling()
