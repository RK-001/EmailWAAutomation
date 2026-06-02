"""
ui/profiles_tab.py
------------------
Profiles Tab — create, edit, and delete client profiles.

A profile stores everything specific to one bank/client:
  - Word template (.docx)
  - Notice type (Section 138, EMI Default, etc.)
  - Email subject + body
  - Column mapping: standard key → Excel column header

Column mapping uses CTkComboBox widgets.
The user loads a sample Excel file to populate the dropdown options
with actual column headers from their file.
If no Excel is loaded, the user may still type the column names manually.

Standard keys that must be mapped (required):
    NAME, EMAILID, MOBILENO

Standard keys that are optional:
    AMOUNT, ACCOUNTNO, OFFICER_NO, CHEQUE_DATE, REASON, BRANCH
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import customtkinter as ctk

from utils.config_manager import VALID_NOTICE_TYPES

if TYPE_CHECKING:
    from ui.app import BulkNoticeApp


# ── Standard column keys ──────────────────────────────────────────────────────

# (key, display_label, required?)
_COLUMN_FIELDS: list[tuple[str, str, bool]] = [
    ("NAME",        "Customer Name",  True),
    ("EMAILID",     "Email Address",  True),
    ("MOBILENO",    "Mobile Number",  True),
    ("ACCOUNTNO",   "Account Number", False),
    ("MASKED_CARD", "Masked Card",    False),
    ("AAN",         "AAN",            False),
    ("AMOUNT",      "Amount / Due",   False),
    ("BOUNCE_AMOUNT", "Bounce Amount", False),
    ("BOUNCE_REASON", "Bounce Reason", False),
    ("BOUNCE_DATE",   "Bounce Date",   False),
    ("OFFICER_NO",  "Officer Phone",  False),
    ("CHEQUE_DATE", "Cheque Date",    False),
    ("REASON",      "Return Reason",  False),
    ("BRANCH",      "Branch Name",    False),
]

_LABEL_W = 160
_ENTRY_W = 300
_BTN_W = 100
_PAD_X = 18
_PAD_Y = 5

_UNMAPPED = "-- not mapped --"


class ProfilesTab:
    """Profiles Tab widget."""

    def __init__(self, parent: ctk.CTkFrame, app: "BulkNoticeApp"):
        self._app = app
        self._cfg = app.config_manager

        # Excel headers loaded via "Load Sample Excel" — used to populate dropdowns
        self._excel_headers: list[str] = []

        # Name of the profile currently being edited (None = new profile)
        self._editing_profile: str | None = None

        # Holds CTkComboBox widgets for each column key
        self._col_combos: dict[str, ctk.CTkComboBox] = {}

        # Holds required-field indicator labels
        self._col_req_labels: dict[str, ctk.CTkLabel] = {}

        # Main layout: left panel (profile list) + right panel (edit form)
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        self._build_left_panel(parent)
        self._build_right_panel(parent)

        self._refresh_profile_list()

    # ── Left panel: profile list ──────────────────────────────────────────────

    def _build_left_panel(self, parent: ctk.CTkFrame) -> None:
        """Left column: profile selector + New/Delete buttons."""
        left = ctk.CTkFrame(parent, width=200)
        left.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
        left.grid_propagate(False)
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            left, text="Client Profiles",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, pady=(10, 6), padx=10, sticky="w")

        # Scrollable list of profile names
        self._profile_listbox = ctk.CTkScrollableFrame(left, label_text="")
        self._profile_listbox.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=8)
        self._profile_listbox.grid_columnconfigure(0, weight=1)

        btn_frame = ctk.CTkFrame(left, fg_color="transparent")
        btn_frame.grid(row=2, column=0, columnspan=2, pady=8, padx=8, sticky="ew")
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            btn_frame, text="+ New", command=self._new_profile,
        ).grid(row=0, column=0, padx=(0, 3), sticky="ew")

        ctk.CTkButton(
            btn_frame, text="🗑 Delete",
            fg_color="#c0392b", hover_color="#922b21",
            command=self._delete_profile,
        ).grid(row=0, column=1, padx=(3, 0), sticky="ew")

    # ── Right panel: edit form ────────────────────────────────────────────────

    def _build_right_panel(self, parent: ctk.CTkFrame) -> None:
        """Right column: the profile edit form in a scrollable frame."""
        self._scroll = ctk.CTkScrollableFrame(parent)
        self._scroll.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)
        self._scroll.grid_columnconfigure(1, weight=1)

        row = 0

        # ── Profile identity ──────────────────────────────────────────────────
        row = self._section_header("PROFILE SETTINGS", row)

        self._profile_name_var = ctk.StringVar()
        row = self._labeled_entry(
            "Profile Key:", self._profile_name_var, row,
            placeholder="e.g. HDFC_LokAdalat  (letters, digits, _ only)",
        )

        self._display_name_var = ctk.StringVar()
        row = self._labeled_entry(
            "Display Name:", self._display_name_var, row,
            placeholder="e.g. HDFC Bank — Lok Adalat",
        )

        # Notice type dropdown
        ctk.CTkLabel(
            self._scroll, text="Notice Type:", anchor="e", width=_LABEL_W,
        ).grid(row=row, column=0, sticky="e", padx=(_PAD_X, 8), pady=_PAD_Y)

        self._notice_type_var = ctk.StringVar(value=VALID_NOTICE_TYPES[0])
        ctk.CTkOptionMenu(
            self._scroll,
            values=VALID_NOTICE_TYPES,
            variable=self._notice_type_var,
            width=_ENTRY_W,
        ).grid(row=row, column=1, sticky="w", pady=_PAD_Y)
        row += 1

        # ── Template ──────────────────────────────────────────────────────────
        row = self._section_header("WORD TEMPLATE", row)

        self._template_var = ctk.StringVar()
        row = self._file_picker_row(
            "Template (.docx):", self._template_var, row,
            filetypes=[("Word Documents", "*.docx"), ("All files", "*.*")],
        )

        # ── Email ─────────────────────────────────────────────────────────────
        row = self._section_header("EMAIL SETTINGS", row)

        self._email_subject_var = ctk.StringVar()
        row = self._labeled_entry(
            "Subject:", self._email_subject_var, row,
            placeholder="Important Communication - {NAME}",
        )

        # Email body — multiline text box
        ctk.CTkLabel(
            self._scroll, text="Body:", anchor="e", width=_LABEL_W,
        ).grid(row=row, column=0, sticky="ne", padx=(_PAD_X, 8), pady=_PAD_Y)

        self._email_body_text = ctk.CTkTextbox(self._scroll, width=_ENTRY_W + 80, height=90)
        self._email_body_text.grid(row=row, column=1, sticky="w", pady=_PAD_Y)
        row += 1

        # ── Column mapping ────────────────────────────────────────────────────
        row = self._section_header("COLUMN MAPPING  (Excel column → Template variable)", row)

        # Load Excel button + status
        load_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        load_frame.grid(row=row, column=0, columnspan=3, sticky="w", padx=_PAD_X, pady=(0, 6))

        ctk.CTkButton(
            load_frame,
            text="📂  Load Sample Excel",
            width=170,
            command=self._load_sample_excel,
        ).pack(side="left")

        self._excel_hint_var = ctk.StringVar(value="Load a sample Excel to fill column dropdowns automatically.")
        ctk.CTkLabel(
            load_frame,
            textvariable=self._excel_hint_var,
            font=ctk.CTkFont(size=11),
            text_color="gray60",
        ).pack(side="left", padx=(10, 0))
        row += 1

        # One ComboBox per standard key
        for key, display_label, required in _COLUMN_FIELDS:
            marker = " *" if required else ""
            ctk.CTkLabel(
                self._scroll,
                text=f"{display_label}{marker}:",
                anchor="e",
                width=_LABEL_W,
            ).grid(row=row, column=0, sticky="e", padx=(_PAD_X, 8), pady=_PAD_Y)

            combo = ctk.CTkComboBox(
                self._scroll,
                values=[_UNMAPPED],
                width=_ENTRY_W,
            )
            combo.set(key if required else _UNMAPPED)
            combo.grid(row=row, column=1, sticky="w", pady=_PAD_Y)
            self._col_combos[key] = combo

            # Required-field indicator (shown only if value is empty)
            req_lbl = ctk.CTkLabel(
                self._scroll,
                text="⚠ required" if required else "",
                font=ctk.CTkFont(size=11),
                text_color="orange",
                width=90,
            )
            req_lbl.grid(row=row, column=2, sticky="w", padx=(6, 0), pady=_PAD_Y)
            self._col_req_labels[key] = req_lbl

            row += 1

        ctk.CTkLabel(
            self._scroll,
            text="* Required fields. Others optional.",
            font=ctk.CTkFont(size=11),
            text_color="gray60",
            anchor="w",
        ).grid(row=row, column=0, columnspan=3, sticky="w", padx=_PAD_X, pady=(2, 10))
        row += 1

        # ── Save button ───────────────────────────────────────────────────────
        save_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        save_frame.grid(row=row, column=0, columnspan=3, pady=(10, 16), padx=_PAD_X, sticky="w")

        ctk.CTkButton(
            save_frame,
            text="💾  Save Profile",
            width=150,
            command=self._save_profile,
        ).pack(side="left", padx=(0, 12))

        self._save_status_var = ctk.StringVar(value="")
        ctk.CTkLabel(
            save_frame,
            textvariable=self._save_status_var,
            font=ctk.CTkFont(size=12),
        ).pack(side="left")

    # ── Composite helpers ─────────────────────────────────────────────────────

    def _section_header(self, title: str, row: int) -> int:
        ctk.CTkLabel(
            self._scroll, text=title,
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).grid(row=row, column=0, columnspan=3, sticky="w", padx=_PAD_X, pady=(14, 4))
        return row + 1

    def _labeled_entry(
        self,
        label: str,
        var: ctk.StringVar,
        row: int,
        placeholder: str = "",
    ) -> int:
        ctk.CTkLabel(
            self._scroll, text=label, anchor="e", width=_LABEL_W,
        ).grid(row=row, column=0, sticky="e", padx=(_PAD_X, 8), pady=_PAD_Y)

        ctk.CTkEntry(
            self._scroll, textvariable=var, width=_ENTRY_W, placeholder_text=placeholder,
        ).grid(row=row, column=1, sticky="w", pady=_PAD_Y)
        return row + 1

    def _file_picker_row(
        self,
        label: str,
        var: ctk.StringVar,
        row: int,
        filetypes: list | None = None,
    ) -> int:
        ctk.CTkLabel(
            self._scroll, text=label, anchor="e", width=_LABEL_W,
        ).grid(row=row, column=0, sticky="e", padx=(_PAD_X, 8), pady=_PAD_Y)

        frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        frame.grid(row=row, column=1, sticky="w", pady=_PAD_Y)

        ctk.CTkEntry(frame, textvariable=var, width=_ENTRY_W - _BTN_W - 10).pack(side="left")

        def browse(v=var, ft=filetypes):
            from tkinter import filedialog
            path = filedialog.askopenfilename(
                filetypes=ft or [("All files", "*.*")]
            )
            if path:
                v.set(path)

        ctk.CTkButton(frame, text="Browse…", width=_BTN_W, command=browse).pack(
            side="left", padx=(6, 0)
        )
        return row + 1

    # ── Profile list management ───────────────────────────────────────────────

    def _refresh_profile_list(self) -> None:
        """Rebuild the left-panel list from current config."""
        # Clear old buttons
        for w in self._profile_listbox.winfo_children():
            w.destroy()

        names = self._cfg.list_profile_names()
        for name in names:
            profile = self._cfg.get_profile(name)
            display = (profile or {}).get("display_name") or name

            btn = ctk.CTkButton(
                self._profile_listbox,
                text=display,
                anchor="w",
                fg_color="transparent",
                text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"],
                hover_color=("gray85", "gray25"),
                command=lambda n=name: self._load_profile_into_form(n),
            )
            btn.grid(sticky="ew", pady=2)
            self._profile_listbox.grid_columnconfigure(0, weight=1)

    # ── Form actions ──────────────────────────────────────────────────────────

    def _new_profile(self) -> None:
        """Clear the form for a fresh profile."""
        self._editing_profile = None
        self._profile_name_var.set("")
        self._display_name_var.set("")
        self._notice_type_var.set(VALID_NOTICE_TYPES[0])
        self._template_var.set("")
        self._email_subject_var.set("Important Communication - {NAME}")
        self._email_body_text.delete("1.0", "end")
        self._email_body_text.insert(
            "1.0",
            "Dear {NAME},\n\nPlease find attached an important communication "
            "regarding your account {ACCOUNTNO}.\n\nRegards,\n{FIRM_NAME}",
        )
        for key, _, required in _COLUMN_FIELDS:
            self._col_combos[key].set(key if required else _UNMAPPED)
        self._save_status_var.set("")
        self._excel_hint_var.set("Load a sample Excel to fill column dropdowns automatically.")

    def _load_profile_into_form(self, profile_name: str) -> None:
        """Populate the right-panel form with data from an existing profile."""
        profile = self._cfg.get_profile(profile_name)
        if profile is None:
            return

        self._editing_profile = profile_name
        self._profile_name_var.set(profile_name)
        self._display_name_var.set(profile.get("display_name") or profile_name)
        self._notice_type_var.set(profile.get("notice_type") or VALID_NOTICE_TYPES[0])
        self._template_var.set(profile.get("template_path") or "")

        self._email_subject_var.set(profile.get("email_subject") or "")
        self._email_body_text.delete("1.0", "end")
        self._email_body_text.insert("1.0", profile.get("email_body") or "")

        col_mapping = profile.get("column_mapping") or {}
        for key, _, required in _COLUMN_FIELDS:
            mapped_col = col_mapping.get(key) or (key if required else _UNMAPPED)
            combo = self._col_combos[key]
            # If we have Excel headers loaded, ensure the saved value is in options
            current_values = list(combo.cget("values") or [])
            if mapped_col and mapped_col != _UNMAPPED and mapped_col not in current_values:
                current_values = [mapped_col] + [v for v in current_values if v]
                combo.configure(values=current_values)
            combo.set(mapped_col)

        self._save_status_var.set("")

    def _load_sample_excel(self) -> None:
        """Open a file picker, read headers, and populate column dropdowns."""
        from tkinter import filedialog, messagebox
        path = filedialog.askopenfilename(
            title="Select a sample Excel file to read column headers",
            filetypes=[("Excel workbooks", "*.xlsx"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            ws = wb.active
            headers = [str(cell.value).strip() for cell in next(ws.iter_rows(max_row=1))
                       if cell.value is not None]
            wb.close()
        except Exception as exc:
            messagebox.showerror("Excel Read Error", f"Could not read Excel file:\n{exc}")
            return

        if not headers:
            messagebox.showwarning("No Headers", "No column headers found in the Excel file.")
            return

        self._excel_headers = headers
        dropdown_values = [_UNMAPPED] + headers
        self._excel_hint_var.set(f"✅  {len(headers)} columns loaded from: {os.path.basename(path)}")

        # Update all combo dropdowns with the new header options
        for key, _, _ in _COLUMN_FIELDS:
            combo = self._col_combos[key]
            current_val = combo.get()
            combo.configure(values=dropdown_values)
            if current_val:
                combo.set(current_val)

    def _delete_profile(self) -> None:
        """Delete the currently loaded profile after confirmation."""
        if not self._editing_profile:
            from tkinter import messagebox
            messagebox.showinfo("No Profile Selected", "Select a profile from the list first.")
            return

        from tkinter import messagebox
        if not messagebox.askyesno(
            "Delete Profile",
            f"Delete profile '{self._editing_profile}'?\nThis cannot be undone.",
            icon="warning",
        ):
            return

        self._cfg.delete_profile(self._editing_profile)
        self._cfg.save()
        self._editing_profile = None
        self._new_profile()
        self._refresh_profile_list()
        self._app.notify_profiles_changed()

    def _save_profile(self) -> None:
        """Validate and persist the current form as a profile."""
        profile_key = self._profile_name_var.get().strip()
        if not profile_key:
            self._save_status_var.set("❌  Profile Key is required.")
            return

        # Validate key format: only letters, digits, underscores
        import re
        if not re.match(r"^[A-Za-z0-9_]+$", profile_key):
            self._save_status_var.set("❌  Key: letters, digits, underscores only.")
            return

        # Validate required column mappings are not empty / "-- not mapped --"
        col_mapping: dict[str, str] = {}
        errors: list[str] = []
        for key, label, required in _COLUMN_FIELDS:
            val = self._col_combos[key].get().strip()
            if val == _UNMAPPED:
                val = ""
            if required and not val:
                errors.append(f"'{label}' column mapping is required.")
            col_mapping[key] = val

        if errors:
            self._save_status_var.set(f"❌  {errors[0]}")
            return

        # Build profile dict
        email_body = self._email_body_text.get("1.0", "end").rstrip("\n")

        profile_data = {
            "display_name": self._display_name_var.get().strip() or profile_key,
            "template_path": self._cfg.make_path_portable(self._template_var.get().strip()),
            "notice_type": self._notice_type_var.get(),
            "email_subject": self._email_subject_var.get().strip(),
            "email_body": email_body,
            "wa_template_params": ["NAME", "ACCOUNTNO", "drive_link", "OFFICER_NO"],
            "column_mapping": {k: v for k, v in col_mapping.items() if v},
        }

        self._cfg.save_profile(profile_key, profile_data)
        self._cfg.save()

        self._editing_profile = profile_key
        self._save_status_var.set(f"✅  Profile '{profile_key}' saved.")
        self._refresh_profile_list()
        self._app.notify_profiles_changed()
