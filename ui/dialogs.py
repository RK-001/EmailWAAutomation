"""
ui/dialogs.py
-------------
Shared modal dialogs for BulkNoticeAutomation.

Dialogs:
  - ApprovalDialog: Lawyer approval gate before sending notices.
    Requires selecting notice type + ticking "I confirm" checkbox.
    Returns (approved: bool, notice_type: str).
"""

from __future__ import annotations

import customtkinter as ctk
from utils.config_manager import VALID_NOTICE_TYPES

# ── Notice type human-readable labels ────────────────────────────────────────

_NOTICE_LABELS: dict[str, str] = {
    "EMI_DEFAULT":    "EMI Default Reminder",
    "PRE_LITIGATION": "Pre-litigation Notice",
    "SECTION_138":    "Section 138 — Cheque Bounce",
    "SARFAESI":       "SARFAESI Demand Notice",
    "OTHER":          "Other / Custom",
}

# Warnings shown for notice types that require physical dispatch too
_SECTION_138_WARNING = (
    "⚠  Section 138 notices require PHYSICAL dispatch (Registered Post / RPAD)\n"
    "   in addition to Email + WhatsApp.\n\n"
    "   Use this tool as SUPPLEMENTARY notification only.\n"
    "   Send the physical notice separately."
)
_SARFAESI_WARNING = (
    "⚠  SARFAESI Demand Notices require PHYSICAL dispatch (Registered Post)\n"
    "   in addition to Email + WhatsApp.\n\n"
    "   Use this tool as SUPPLEMENTARY notification only."
)


class ApprovalDialog(ctk.CTkToplevel):
    """
    Modal dialog: Lawyer approval gate before sending notices.

    Usage:
        dlg = ApprovalDialog(parent, default_notice_type="EMI_DEFAULT")
        parent.wait_window(dlg)
        if dlg.approved:
            notice_type = dlg.notice_type
    """

    def __init__(self, parent, default_notice_type: str = "EMI_DEFAULT"):
        super().__init__(parent)

        self.approved: bool = False
        self.notice_type: str = default_notice_type

        self.title("Lawyer Approval Required")
        self.resizable(False, False)
        self.grab_set()       # Modal — blocks the parent window
        self.focus_force()

        # Center on parent
        self.update_idletasks()
        pw = parent.winfo_rootx()
        py = parent.winfo_rooty()
        self.geometry(f"520x420+{pw + 80}+{py + 80}")

        self._confirmed_var = ctk.BooleanVar(value=False)
        self._notice_type_var = ctk.StringVar(value=default_notice_type)
        self._warning_var = ctk.StringVar(value="")

        self._build_ui()
        self._update_warning()

    def _build_ui(self) -> None:
        frame = ctk.CTkFrame(self, corner_radius=12)
        frame.pack(fill="both", expand=True, padx=16, pady=16)
        frame.grid_columnconfigure(0, weight=1)

        # ── Header ────────────────────────────────────────────────────────────
        ctk.CTkLabel(
            frame,
            text="⚖  LAWYER APPROVAL REQUIRED",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, pady=(16, 4), padx=20, sticky="w")

        ctk.CTkLabel(
            frame,
            text="Please select the notice type and confirm before sending.",
            font=ctk.CTkFont(size=12),
            text_color="gray60",
        ).grid(row=1, column=0, padx=20, sticky="w")

        # ── Notice type ───────────────────────────────────────────────────────
        ctk.CTkLabel(
            frame,
            text="Notice Type:",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).grid(row=2, column=0, padx=20, pady=(18, 4), sticky="w")

        ctk.CTkOptionMenu(
            frame,
            values=[_NOTICE_LABELS.get(k, k) for k in VALID_NOTICE_TYPES],
            variable=self._notice_type_var,
            width=320,
            command=self._on_type_changed,
        ).grid(row=3, column=0, padx=20, sticky="w")

        # ── Warning box ───────────────────────────────────────────────────────
        self._warning_label = ctk.CTkLabel(
            frame,
            textvariable=self._warning_var,
            font=ctk.CTkFont(size=11),
            text_color="orange",
            anchor="w",
            justify="left",
            wraplength=460,
        )
        self._warning_label.grid(row=4, column=0, padx=20, pady=(10, 0), sticky="w")

        # ── Confirmation checkbox ──────────────────────────────────────────────
        ctk.CTkCheckBox(
            frame,
            text=(
                "I have personally reviewed all the notices in this batch\n"
                "and approve them for sending."
            ),
            variable=self._confirmed_var,
            font=ctk.CTkFont(size=12),
            command=self._update_send_btn,
        ).grid(row=5, column=0, padx=20, pady=(20, 10), sticky="w")

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.grid(row=6, column=0, padx=20, pady=(10, 20), sticky="e")

        self._send_btn = ctk.CTkButton(
            btn_frame,
            text="✔  Approve & Send",
            width=160,
            state="disabled",
            command=self._confirm,
        )
        self._send_btn.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            width=90,
            fg_color="gray50",
            command=self.destroy,
        ).pack(side="left")

    def _on_type_changed(self, label: str) -> None:
        """Map the human-readable label back to the internal key."""
        for key, display in _NOTICE_LABELS.items():
            if display == label:
                self.notice_type = key
                break
        self._update_warning()

    def _update_warning(self) -> None:
        """Show type-specific legal warning."""
        if self.notice_type == "SECTION_138":
            self._warning_var.set(_SECTION_138_WARNING)
        elif self.notice_type == "SARFAESI":
            self._warning_var.set(_SARFAESI_WARNING)
        else:
            self._warning_var.set("")

    def _update_send_btn(self) -> None:
        """Enable/disable the Approve button based on checkbox state."""
        state = "normal" if self._confirmed_var.get() else "disabled"
        self._send_btn.configure(state=state)

    def _confirm(self) -> None:
        self.approved = True
        self.destroy()
