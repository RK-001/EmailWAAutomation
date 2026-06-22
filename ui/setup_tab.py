"""
ui/setup_tab.py
---------------
Setup Tab — one-time configuration of credentials and service settings.

Sections:
  1. FIRM SETTINGS     — lawyer name, firm name (shown in notices + top bar)
  2. GMAIL SETTINGS    — sender email + App Password + live connection test
  3. META WHATSAPP SETTINGS — Phone Number ID + Access Token + template name
  4. GOOGLE DRIVE      — service account JSON path + folder ID + mock mode
  5. Save Settings button

All credentials are stored in config.json.
The "Test" buttons perform live checks (Gmail SMTP, Meta API token validation).
"""

from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING

import customtkinter as ctk

if TYPE_CHECKING:
    from ui.app import BulkNoticeApp


# ── Layout constants ──────────────────────────────────────────────────────────

_LABEL_W = 160      # Fixed label column width
_ENTRY_W = 340      # Entry widget width
_BTN_W = 120        # Button width
_STATUS_W = 220     # Status indicator width
_PAD_X = 20         # Horizontal section padding
_PAD_Y = 6          # Row vertical padding
_SECTION_PAD = (14, 6)   # (top, bottom) padding for section headers


class SetupTab:
    """
    Setup Tab widget.
    Embedded inside the CTkTabview tab frame passed via ``parent``.
    """

    def __init__(self, parent: ctk.CTkFrame, app: "BulkNoticeApp"):
        """
        Args:
            parent:  The CTkFrame of the "⚙  Setup" tab.
            app:     Reference to the main BulkNoticeApp for shared state.
        """
        self._app = app
        self._cfg = app.config_manager

        # Build a scrollable container so the tab works on small screens
        self._scroll = ctk.CTkScrollableFrame(parent)
        self._scroll.pack(fill="both", expand=True, padx=4, pady=4)
        self._scroll.grid_columnconfigure(1, weight=1)

        self._build_ui()
        self._load_values()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        row = 0

        # ── Section: Firm ─────────────────────────────────────────────────────
        row = self._section_header("FIRM SETTINGS", row)

        self._firm_name_var = ctk.StringVar()
        row = self._labeled_entry(
            "Firm Name:", self._firm_name_var, row,
            placeholder="e.g. GK Associates",
        )
        self._lawyer_name_var = ctk.StringVar()
        row = self._labeled_entry(
            "Lawyer Name:", self._lawyer_name_var, row,
            placeholder="e.g. Adv. Ganesh Kulkarni",
        )

        # ── Section: Gmail ────────────────────────────────────────────────────
        row = self._section_header("GMAIL SETTINGS", row)

        self._gmail_email_var = ctk.StringVar()
        row = self._labeled_entry(
            "Sender Email:", self._gmail_email_var, row,
            placeholder="lawfirm@gmail.com",
        )
        self._gmail_pass_var = ctk.StringVar()
        row = self._labeled_entry(
            "App Password:", self._gmail_pass_var, row,
            placeholder="xxxx xxxx xxxx xxxx",
            show="●",
        )

        # Help link label
        help_lbl = ctk.CTkLabel(
            self._scroll,
            text="ⓘ  How to get an App Password  →  myaccount.google.com  →  Security  →  App Passwords",
            font=ctk.CTkFont(size=11),
            text_color="gray60",
            anchor="w",
        )
        help_lbl.grid(row=row, column=0, columnspan=3, sticky="w", padx=_PAD_X, pady=(0, 4))
        row += 1

        # Test button + status indicator for Gmail
        self._gmail_status_var = ctk.StringVar(value="")
        row = self._test_row(
            "Test Gmail Connection",
            self._gmail_status_var,
            self._test_gmail,
            row,
        )

        # ── Section: Meta WhatsApp ───────────────────────────────────────
        row = self._section_header("META WHATSAPP SETTINGS", row)

        self._meta_phone_id_var = ctk.StringVar()
        row = self._labeled_entry(
            "Phone Number ID:", self._meta_phone_id_var, row,
            placeholder="From Meta Business Manager",
        )
        self._meta_access_token_var = ctk.StringVar()
        row = self._labeled_entry(
            "Access Token:", self._meta_access_token_var, row,
            placeholder="Permanent access token from Meta",
            show="●",
        )
        self._meta_template_var = ctk.StringVar()
        row = self._labeled_entry(
            "Template Name:", self._meta_template_var, row,
            placeholder="Approved Meta template name",
        )
        self._meta_api_version_var = ctk.StringVar()
        row = self._labeled_entry(
            "API Version:", self._meta_api_version_var, row,
            placeholder="v21.0",
        )
        self._meta_template_language_var = ctk.StringVar()
        row = self._labeled_entry(
            "Template Language:", self._meta_template_language_var, row,
            placeholder="en",
        )

        # Mock mode toggle
        self._meta_mock_var = ctk.BooleanVar(value=True)
        row = self._toggle_row(
            "Mock Mode (no real sends):",
            self._meta_mock_var,
            row,
            note="Disable when ready for production.",
        )

        self._meta_status_var = ctk.StringVar(value="")
        row = self._test_row(
            "Test Meta API",
            self._meta_status_var,
            self._test_meta_whatsapp,
            row,
        )

        # ── Section: Google Drive ─────────────────────────────────────────────
        row = self._section_header("GOOGLE DRIVE SETTINGS", row)

        self._drive_auth_mode_var = ctk.StringVar(value="oauth_user")
        row = self._option_row(
            "Auth Mode:",
            self._drive_auth_mode_var,
            ["oauth_user", "service_account"],
            row,
        )

        self._drive_oauth_client_var = ctk.StringVar()
        row = self._file_picker_row(
            "OAuth Client JSON:", self._drive_oauth_client_var, row,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        self._drive_oauth_token_var = ctk.StringVar()
        row = self._labeled_entry(
            "OAuth Token Path:", self._drive_oauth_token_var, row,
            placeholder="token.json",
        )

        self._drive_creds_var = ctk.StringVar()
        row = self._file_picker_row(
            "Service Account JSON:", self._drive_creds_var, row,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        self._drive_folder_id_var = ctk.StringVar()
        row = self._labeled_entry(
            "Upload Folder ID:", self._drive_folder_id_var, row,
            placeholder="Google Drive folder ID (from URL)",
        )

        self._drive_mock_var = ctk.BooleanVar(value=True)
        row = self._toggle_row(
            "Mock Mode (no real upload):",
            self._drive_mock_var,
            row,
            note="Disable when Drive credentials are configured.",
        )

        self._drive_status_var = ctk.StringVar(value="")
        row = self._test_row(
            "Authorize / Test Drive",
            self._drive_status_var,
            self._test_drive,
            row,
        )

        # ── Section: Advanced Settings ────────────────────────────────────────
        row = self._section_header("ADVANCED SETTINGS", row)

        # Output folder for generated PDFs
        self._output_folder_var = ctk.StringVar()
        row = self._folder_picker_row(
            "Output Folder:", self._output_folder_var, row,
        )

        # Log folder for batch logs / checkpoints
        self._log_folder_var = ctk.StringVar()
        row = self._folder_picker_row(
            "Log Folder:", self._log_folder_var, row,
        )

        # Word COM restart batch size (prevents memory leaks)
        self._batch_restart_var = ctk.StringVar(value="50")
        row = self._labeled_entry(
            "Restart Word every:", self._batch_restart_var, row,
            placeholder="50  (number of PDFs before restarting Word)",
        )

        # Email send delay
        self._delay_min_var = ctk.StringVar(value="3")
        row = self._labeled_entry(
            "Send delay min (s):", self._delay_min_var, row,
            placeholder="3",
        )

        self._delay_max_var = ctk.StringVar(value="5")
        row = self._labeled_entry(
            "Send delay max (s):", self._delay_max_var, row,
            placeholder="5",
        )

        # Daily Gmail limit guard
        self._max_emails_var = ctk.StringVar(value="450")
        row = self._labeled_entry(
            "Max emails / day:", self._max_emails_var, row,
            placeholder="450  (Gmail daily safe limit)",
        )

        # ── Save button ───────────────────────────────────────────────────────
        save_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        save_frame.grid(row=row, column=0, columnspan=3, pady=(20, 10), padx=_PAD_X, sticky="w")

        ctk.CTkButton(
            save_frame,
            text="💾  Save Settings",
            width=160,
            command=self._save,
        ).pack(side="left", padx=(0, 10))

        self._save_status_var = ctk.StringVar(value="")
        ctk.CTkLabel(
            save_frame,
            textvariable=self._save_status_var,
            font=ctk.CTkFont(size=12),
        ).pack(side="left")

    # ── Composite widget builders ─────────────────────────────────────────────

    def _section_header(self, title: str, row: int) -> int:
        """Render a bold section header. Returns the next available row."""
        ctk.CTkLabel(
            self._scroll,
            text=title,
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).grid(
            row=row, column=0, columnspan=3, sticky="w",
            padx=_PAD_X, pady=_SECTION_PAD,
        )
        return row + 1

    def _labeled_entry(
        self,
        label: str,
        var: ctk.StringVar,
        row: int,
        placeholder: str = "",
        show: str = "",
    ) -> int:
        """Label + CTkEntry pair. Returns next available row."""
        ctk.CTkLabel(
            self._scroll, text=label, anchor="e", width=_LABEL_W,
        ).grid(row=row, column=0, sticky="e", padx=(_PAD_X, 8), pady=_PAD_Y)

        entry = ctk.CTkEntry(
            self._scroll,
            textvariable=var,
            width=_ENTRY_W,
            placeholder_text=placeholder,
            show=show,
        )
        entry.grid(row=row, column=1, sticky="w", pady=_PAD_Y)
        return row + 1

    def _test_row(
        self,
        btn_label: str,
        status_var: ctk.StringVar,
        command,
        row: int,
    ) -> int:
        """[Test button] + [status indicator] row. Returns next available row."""
        frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        frame.grid(row=row, column=0, columnspan=3, sticky="w", padx=_PAD_X, pady=(4, 8))

        ctk.CTkButton(
            frame, text=btn_label, width=_BTN_W, command=command,
        ).pack(side="left", padx=(0, 14))

        ctk.CTkLabel(
            frame, textvariable=status_var, width=_STATUS_W,
            font=ctk.CTkFont(size=12), anchor="w",
        ).pack(side="left")

        return row + 1

    def _option_row(
        self,
        label: str,
        var: ctk.StringVar,
        values: list[str],
        row: int,
    ) -> int:
        """Label + option menu pair. Returns next available row."""
        ctk.CTkLabel(
            self._scroll, text=label, anchor="e", width=_LABEL_W,
        ).grid(row=row, column=0, sticky="e", padx=(_PAD_X, 8), pady=_PAD_Y)

        ctk.CTkOptionMenu(
            self._scroll,
            values=values,
            variable=var,
            width=_ENTRY_W,
        ).grid(row=row, column=1, sticky="w", pady=_PAD_Y)
        return row + 1

    def _toggle_row(
        self,
        label: str,
        var: ctk.BooleanVar,
        row: int,
        note: str = "",
    ) -> int:
        """Label + CTkSwitch toggle. Returns next available row."""
        ctk.CTkLabel(
            self._scroll, text=label, anchor="e", width=_LABEL_W,
        ).grid(row=row, column=0, sticky="e", padx=(_PAD_X, 8), pady=_PAD_Y)

        frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        frame.grid(row=row, column=1, sticky="w", pady=_PAD_Y)

        ctk.CTkSwitch(frame, text="", variable=var).pack(side="left")
        if note:
            ctk.CTkLabel(
                frame, text=note, font=ctk.CTkFont(size=11), text_color="gray60",
            ).pack(side="left", padx=(8, 0))

        return row + 1

    def _file_picker_row(
        self,
        label: str,
        var: ctk.StringVar,
        row: int,
        filetypes: list | None = None,
    ) -> int:
        """Label + Entry + Browse button for file selection."""
        ctk.CTkLabel(
            self._scroll, text=label, anchor="e", width=_LABEL_W,
        ).grid(row=row, column=0, sticky="e", padx=(_PAD_X, 8), pady=_PAD_Y)

        frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        frame.grid(row=row, column=1, sticky="w", pady=_PAD_Y)

        entry = ctk.CTkEntry(frame, textvariable=var, width=_ENTRY_W - _BTN_W - 10)
        entry.pack(side="left")

        def browse():
            from tkinter import filedialog
            path = filedialog.askopenfilename(
                title=f"Select {label.rstrip(':')}",
                filetypes=filetypes or [("All files", "*.*")],
            )
            if path:
                var.set(path)

        ctk.CTkButton(frame, text="Browse…", width=_BTN_W, command=browse).pack(
            side="left", padx=(6, 0)
        )
        return row + 1

    def _folder_picker_row(
        self,
        label: str,
        var: ctk.StringVar,
        row: int,
    ) -> int:
        """Label + Entry + Browse button for directory selection."""
        ctk.CTkLabel(
            self._scroll, text=label, anchor="e", width=_LABEL_W,
        ).grid(row=row, column=0, sticky="e", padx=(_PAD_X, 8), pady=_PAD_Y)

        frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        frame.grid(row=row, column=1, sticky="w", pady=_PAD_Y)

        entry = ctk.CTkEntry(frame, textvariable=var, width=_ENTRY_W - _BTN_W - 10)
        entry.pack(side="left")

        def browse():
            from tkinter import filedialog
            path = filedialog.askdirectory(title=f"Select {label.rstrip(':')}",)
            if path:
                var.set(path)

        ctk.CTkButton(frame, text="Browse…", width=_BTN_W, command=browse).pack(
            side="left", padx=(6, 0)
        )
        return row + 1

    # ── Load / Save ───────────────────────────────────────────────────────────

    def _load_values(self) -> None:
        """Populate all widgets from the current config."""
        self._firm_name_var.set(self._cfg.get("settings.firm_name") or "")
        self._lawyer_name_var.set(self._cfg.get("settings.lawyer_name") or "")
        self._gmail_email_var.set(self._cfg.get("gmail.sender_email") or "")
        self._gmail_pass_var.set(self._cfg.get("gmail.app_password") or "")
        self._meta_phone_id_var.set(self._cfg.get("meta_whatsapp.phone_number_id") or "")
        self._meta_access_token_var.set(self._cfg.get("meta_whatsapp.access_token") or "")
        self._meta_template_var.set(
            self._cfg.get("meta_whatsapp.template_name") or ""
        )
        self._meta_api_version_var.set(
            self._cfg.get("meta_whatsapp.api_version") or "v21.0"
        )
        self._meta_template_language_var.set(
            self._cfg.get("meta_whatsapp.template_language") or "en"
        )
        self._meta_mock_var.set(bool(self._cfg.get("meta_whatsapp.mock_mode", True)))
        self._drive_auth_mode_var.set(
            self._cfg.get("google_drive.auth_mode") or "oauth_user"
        )
        self._drive_oauth_client_var.set(
            self._cfg.get("google_drive.oauth_client_json_path") or "oauth_credentials.json"
        )
        self._drive_oauth_token_var.set(
            self._cfg.get("google_drive.oauth_token_json_path") or "token.json"
        )
        self._drive_creds_var.set(
            self._cfg.get("google_drive.service_account_json_path") or ""
        )
        self._drive_folder_id_var.set(
            self._cfg.get("google_drive.upload_folder_id") or ""
        )
        self._drive_mock_var.set(bool(self._cfg.get("google_drive.mock_mode", True)))

        # Advanced settings
        self._output_folder_var.set(self._cfg.get("settings.output_folder") or ".\\output")
        self._log_folder_var.set(self._cfg.get("settings.log_folder") or ".\\logs")
        self._batch_restart_var.set(
            str(self._cfg.get("settings.batch_restart_every") or 50)
        )
        self._delay_min_var.set(
            str(self._cfg.get("settings.send_delay_min_sec") or 3)
        )
        self._delay_max_var.set(
            str(self._cfg.get("settings.send_delay_max_sec") or 5)
        )
        self._max_emails_var.set(
            str(self._cfg.get("settings.max_emails_per_day") or 450)
        )

    def _save(self) -> None:
        """Write all field values back to config and persist to disk."""
        self._cfg.set("settings.firm_name", self._firm_name_var.get().strip())
        self._cfg.set("settings.lawyer_name", self._lawyer_name_var.get().strip())
        gmail_email = self._gmail_email_var.get().strip()
        gmail_app_password = self._gmail_pass_var.get().strip().replace(" ", "")

        self._cfg.set("gmail.sender_email", gmail_email)
        self._cfg.set("gmail.app_password", gmail_app_password)
        self._cfg.set("meta_whatsapp.phone_number_id", self._meta_phone_id_var.get().strip())
        self._cfg.set("meta_whatsapp.access_token", self._meta_access_token_var.get().strip())
        self._cfg.set(
            "meta_whatsapp.template_name",
            self._meta_template_var.get().strip(),
        )
        self._cfg.set(
            "meta_whatsapp.api_version",
            self._meta_api_version_var.get().strip() or "v21.0",
        )
        self._cfg.set(
            "meta_whatsapp.template_language",
            self._meta_template_language_var.get().strip() or "en",
        )
        self._cfg.set("meta_whatsapp.mock_mode", self._meta_mock_var.get())
        self._cfg.set("google_drive.auth_mode", self._drive_auth_mode_var.get())
        self._cfg.set(
            "google_drive.oauth_client_json_path",
            self._cfg.make_path_portable(self._drive_oauth_client_var.get().strip()),
        )
        self._cfg.set(
            "google_drive.oauth_token_json_path",
            self._cfg.make_path_portable(self._drive_oauth_token_var.get().strip() or "token.json"),
        )
        self._cfg.set(
            "google_drive.service_account_json_path",
            self._cfg.make_path_portable(self._drive_creds_var.get().strip()),
        )
        self._cfg.set("google_drive.upload_folder_id", self._drive_folder_id_var.get().strip())
        self._cfg.set("google_drive.mock_mode", self._drive_mock_var.get())

        # Advanced settings — validate numerics before saving
        def _int_or(raw: str, fallback: int) -> int:
            try:
                return max(1, int(raw.strip()))
            except (ValueError, AttributeError):
                return fallback

        self._cfg.set("settings.output_folder", self._output_folder_var.get().strip() or ".\\output")
        self._cfg.set("settings.log_folder", self._log_folder_var.get().strip() or ".\\logs")
        self._cfg.set("settings.batch_restart_every", _int_or(self._batch_restart_var.get(), 50))
        self._cfg.set("settings.send_delay_min_sec", _int_or(self._delay_min_var.get(), 3))
        self._cfg.set("settings.send_delay_max_sec", _int_or(self._delay_max_var.get(), 5))
        self._cfg.set("settings.max_emails_per_day", _int_or(self._max_emails_var.get(), 450))

        try:
            self._cfg.save()
            self._save_status_var.set("✅  Saved successfully.")
            # Refresh firm name in top bar
            self._app.refresh_title()
        except Exception as exc:
            self._save_status_var.set(f"❌  Save failed: {exc}")

    # ── Test button handlers ──────────────────────────────────────────────────

    def _test_gmail(self) -> None:
        """Spawn a background thread to test Gmail credentials."""
        self._gmail_status_var.set("⏳  Testing…")
        threading.Thread(target=self._do_test_gmail, daemon=True).start()

    def _do_test_gmail(self) -> None:
        """Background: attempt SMTP login with current field values."""
        from utils.preflight import check_gmail_auth
        email = self._gmail_email_var.get().strip()
        password = self._gmail_pass_var.get().strip().replace(" ", "")
        ok, msg = check_gmail_auth(email, password)
        status = "✅  Gmail: Connected" if ok else f"❌  {msg.split(chr(10))[0]}"
        # GUI update must run on the main thread
        self._app.after(0, lambda: self._gmail_status_var.set(status))

    def _test_meta_whatsapp(self) -> None:
        """Spawn a background thread to check Meta WhatsApp API."""
        self._meta_status_var.set("⏳  Testing…")
        threading.Thread(target=self._do_test_meta_whatsapp, daemon=True).start()

    def _do_test_meta_whatsapp(self) -> None:
        """Background: Validate Meta API credentials."""
        from utils.preflight import check_meta_whatsapp_connection
        # Pass current credentials
        phone_number_id = self._meta_phone_id_var.get().strip()
        access_token = self._meta_access_token_var.get().strip()
        api_version = self._meta_api_version_var.get().strip() or "v21.0"
        ok, msg = check_meta_whatsapp_connection(phone_number_id, access_token, api_version)
        status = "✅  Meta API: Connected" if ok else f"❌  {msg}"
        self._app.after(0, lambda: self._meta_status_var.set(status))

    def _test_drive(self) -> None:
        """Spawn a background thread to authorize and test Google Drive."""
        self._drive_status_var.set("Testing Drive...")
        threading.Thread(target=self._do_test_drive, daemon=True).start()

    def _do_test_drive(self) -> None:
        """Background: OAuth/service-account Drive readiness check."""
        from utils.preflight import check_drive_ready

        def _resolve(raw_path: str) -> str:
            raw_path = raw_path.strip()
            if not raw_path:
                return raw_path
            return self._cfg.resolve_path(raw_path)

        drive_config = {
            "auth_mode": self._drive_auth_mode_var.get() or "oauth_user",
            "oauth_client_json_path": _resolve(self._drive_oauth_client_var.get()),
            "oauth_token_json_path": _resolve(self._drive_oauth_token_var.get() or "token.json"),
            "service_account_json_path": _resolve(self._drive_creds_var.get()),
            "upload_folder_id": self._drive_folder_id_var.get().strip(),
            "auto_delete_days": 30,
            "mock_mode": False,
        }
        ok, msg = check_drive_ready(
            drive_config,
            allow_oauth_interactive=True,
        )
        status = f"Drive: {msg}" if ok else f"Drive failed: {msg}"
        self._app.after(0, lambda: self._drive_status_var.set(status))
