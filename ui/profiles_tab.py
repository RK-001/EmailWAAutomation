"""
ui/profiles_tab.py
------------------
Profiles tab for creating, editing, and deleting client profiles.

A profile stores:
  - Word template (.docx)
  - Notice type
  - Email subject and body
  - Mapping from template/app fields to Excel column headers

The mapping rows are generated from the selected Word template. Any
{{ VARIABLE }} found in the template is mapped to an Excel column unless the
app fills that value automatically.
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

import customtkinter as ctk

from core.doc_generator import get_template_variables
from core.excel_reader import get_column_headers
from utils.config_manager import VALID_NOTICE_TYPES

if TYPE_CHECKING:
    from ui.app import BulkNoticeApp


_LABEL_W = 170
_ENTRY_W = 340
_BTN_W = 105
_PAD_X = 18
_PAD_Y = 5

_UNMAPPED = "-- not mapped --"

# These placeholders can appear in templates but are supplied by the app.
_AUTO_TEMPLATE_VARIABLES = {"FIRM_NAME", "LAWYER_NAME", "NOTICE_DATE"}

# These are useful for sending and logs even when the Word template does not
# contain them. NAME stays required because it is the main recipient identifier
# used across preview, file naming, email, and WhatsApp flows.
_OPERATIONAL_FIELDS: list[tuple[str, str, str, bool]] = [
    ("NAME", "Customer Name", "Used in preview, file names, email and WhatsApp", True),
    ("EMAILID", "Email Address", "Used when email sending is enabled", False),
    ("MOBILENO", "Mobile Number", "Used when WhatsApp sending is enabled", False),
    ("ACCOUNTNO", "Account Number", "Useful for email/WhatsApp even if not in the Word template", False),
    ("OFFICER_NO", "Officer Phone", "Useful for WhatsApp even if not in the Word template", False),
]

_KNOWN_FIELD_LABELS = {
    "NAME": "Customer Name",
    "EMAILID": "Email Address",
    "MOBILENO": "Mobile Number",
    "ACCOUNTNO": "Account Number",
    "MASKED_CARD": "Masked Card",
    "AAN": "AAN",
    "AMOUNT": "Amount / Due",
    "BOUNCE_AMOUNT": "Bounce Amount",
    "BOUNCE_REASON": "Bounce Reason",
    "BOUNCE_DATE": "Bounce Date",
    "OFFICER_NO": "Officer Phone",
    "CHEQUE_DATE": "Cheque Date",
    "REASON": "Return Reason",
    "BRANCH": "Branch Name",
}


def _friendly_label(key: str) -> str:
    if key in _KNOWN_FIELD_LABELS:
        return _KNOWN_FIELD_LABELS[key]
    return key.replace("_", " ").strip().title() or key


def _normalise_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", value or "").upper()


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        value = (value or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _parse_whatsapp_template_params(raw_value: str) -> tuple[list[str], str]:
    """
    Parse a comma-separated WhatsApp placeholder field list.

    A blank value means the template has no body placeholders.
    Empty items are skipped (no validation error).
    """
    text = (raw_value or "").strip()
    if not text:
        return [], ""

    params: list[str] = []
    for piece in text.split(","):
        field_name = piece.strip()
        if field_name:  # Skip empty items silently
            params.append(field_name)
    return params, ""


class ProfilesTab:
    """Profiles tab widget."""

    def __init__(self, parent: ctk.CTkFrame, app: "BulkNoticeApp"):
        self._app = app
        self._cfg = app.config_manager

        self._excel_headers: list[str] = []
        self._template_variables: list[str] = []
        self._mapping_fields: list[tuple[str, str, str, bool]] = []
        self._editing_profile: str | None = None
        self._col_combos: dict[str, ctk.CTkComboBox] = {}

        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        self._build_left_panel(parent)
        self._build_right_panel(parent)
        self._refresh_profile_list()
        self._new_profile()

    # Left panel

    def _build_left_panel(self, parent: ctk.CTkFrame) -> None:
        left = ctk.CTkFrame(parent, width=210)
        left.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
        left.grid_propagate(False)
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            left,
            text="Client Profiles",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, pady=(10, 6), padx=10, sticky="w")

        self._profile_listbox = ctk.CTkScrollableFrame(left, label_text="")
        self._profile_listbox.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=8)
        self._profile_listbox.grid_columnconfigure(0, weight=1)

        btn_frame = ctk.CTkFrame(left, fg_color="transparent")
        btn_frame.grid(row=2, column=0, columnspan=2, pady=8, padx=8, sticky="ew")
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            btn_frame,
            text="+ New",
            command=self._new_profile,
        ).grid(row=0, column=0, padx=(0, 3), sticky="ew")

        ctk.CTkButton(
            btn_frame,
            text="Delete",
            fg_color="#c0392b",
            hover_color="#922b21",
            command=self._delete_profile,
        ).grid(row=0, column=1, padx=(3, 0), sticky="ew")

    # Right panel

    def _build_right_panel(self, parent: ctk.CTkFrame) -> None:
        self._scroll = ctk.CTkScrollableFrame(parent)
        self._scroll.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)
        self._scroll.grid_columnconfigure(1, weight=1)

        row = 0
        row = self._section_header("PROFILE SETTINGS", row)

        self._profile_name_var = ctk.StringVar()
        row = self._labeled_entry(
            "Profile Key:",
            self._profile_name_var,
            row,
            placeholder="e.g. HDFC_LokAdalat",
        )

        self._display_name_var = ctk.StringVar()
        row = self._labeled_entry(
            "Display Name:",
            self._display_name_var,
            row,
            placeholder="e.g. HDFC Bank - Lok Adalat",
        )

        ctk.CTkLabel(
            self._scroll,
            text="Notice Type:",
            anchor="e",
            width=_LABEL_W,
        ).grid(row=row, column=0, sticky="e", padx=(_PAD_X, 8), pady=_PAD_Y)

        self._notice_type_var = ctk.StringVar(value=VALID_NOTICE_TYPES[0])
        ctk.CTkOptionMenu(
            self._scroll,
            values=VALID_NOTICE_TYPES,
            variable=self._notice_type_var,
            width=_ENTRY_W,
        ).grid(row=row, column=1, sticky="w", pady=_PAD_Y)
        row += 1

        row = self._section_header("WORD TEMPLATE", row)
        self._template_var = ctk.StringVar()
        row = self._template_picker_row(row)

        self._template_hint_var = ctk.StringVar(
            value="Select a .docx template. The app will read {{VARIABLES}} automatically."
        )
        ctk.CTkLabel(
            self._scroll,
            textvariable=self._template_hint_var,
            font=ctk.CTkFont(size=11),
            text_color="gray60",
            anchor="w",
        ).grid(row=row, column=0, columnspan=3, sticky="w", padx=_PAD_X, pady=(0, 8))
        row += 1

        row = self._section_header("EMAIL SETTINGS", row)
        self._email_subject_var = ctk.StringVar()
        row = self._labeled_entry(
            "Subject:",
            self._email_subject_var,
            row,
            placeholder="Important Communication - {NAME}",
        )

        ctk.CTkLabel(
            self._scroll,
            text="Body:",
            anchor="e",
            width=_LABEL_W,
        ).grid(row=row, column=0, sticky="ne", padx=(_PAD_X, 8), pady=_PAD_Y)

        self._email_body_text = ctk.CTkTextbox(self._scroll, width=_ENTRY_W + 80, height=90)
        self._email_body_text.grid(row=row, column=1, sticky="w", pady=_PAD_Y)
        row += 1

        row = self._section_header("WHATSAPP SETTINGS", row)

        self._wa_template_name_var = ctk.StringVar()
        row = self._labeled_entry(
            "Meta Template Name:",
            self._wa_template_name_var,
            row,
            placeholder="your_approved_template_name",
        )
        ctk.CTkLabel(
            self._scroll,
            text="The template name approved in Meta Business Manager. Required for live sends.",
            font=ctk.CTkFont(size=11),
            text_color="gray60",
            anchor="w",
        ).grid(row=row, column=0, columnspan=3, sticky="w", padx=_PAD_X, pady=(0, 8))
        row += 1

        self._wa_template_language_var = ctk.StringVar()
        row = self._labeled_entry(
            "Template Language:",
            self._wa_template_language_var,
            row,
            placeholder="en",
        )
        ctk.CTkLabel(
            self._scroll,
            text="Language code for the template (e.g. 'en', 'en_US'). Defaults to 'en' if blank.",
            font=ctk.CTkFont(size=11),
            text_color="gray60",
            anchor="w",
        ).grid(row=row, column=0, columnspan=3, sticky="w", padx=_PAD_X, pady=(0, 8))
        row += 1

        self._wa_template_params_var = ctk.StringVar()
        row = self._labeled_entry(
            "Template Params:",
            self._wa_template_params_var,
            row,
            placeholder="NAME, ACCOUNTNO, drive_link, OFFICER_NO",
        )
        ctk.CTkLabel(
            self._scroll,
            text="Comma-separated Meta body placeholders in order. Leave blank if the template has no variables.",
            font=ctk.CTkFont(size=11),
            text_color="gray60",
            anchor="w",
        ).grid(row=row, column=0, columnspan=3, sticky="w", padx=_PAD_X, pady=(0, 8))
        row += 1

        row = self._section_header("MAPPING  (Template variable -> Excel column)", row)

        load_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        load_frame.grid(row=row, column=0, columnspan=3, sticky="w", padx=_PAD_X, pady=(0, 6))

        ctk.CTkButton(
            load_frame,
            text="Load Sample Excel",
            width=170,
            command=self._load_sample_excel,
        ).pack(side="left")

        self._excel_hint_var = ctk.StringVar(
            value="Load a sample Excel to fill column dropdowns automatically."
        )
        ctk.CTkLabel(
            load_frame,
            textvariable=self._excel_hint_var,
            font=ctk.CTkFont(size=11),
            text_color="gray60",
        ).pack(side="left", padx=(10, 0))
        row += 1

        self._mapping_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._mapping_frame.grid(row=row, column=0, columnspan=3, sticky="ew", padx=_PAD_X)
        self._mapping_frame.grid_columnconfigure(1, weight=1)
        row += 1

        ctk.CTkLabel(
            self._scroll,
            text="Required fields must be mapped. Optional fields can stay 'not mapped' and render as NA.",
            font=ctk.CTkFont(size=11),
            text_color="gray60",
            anchor="w",
        ).grid(row=row, column=0, columnspan=3, sticky="w", padx=_PAD_X, pady=(2, 10))
        row += 1

        save_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        save_frame.grid(row=row, column=0, columnspan=3, pady=(10, 16), padx=_PAD_X, sticky="w")

        ctk.CTkButton(
            save_frame,
            text="Save Profile",
            width=150,
            command=self._save_profile,
        ).pack(side="left", padx=(0, 12))

        self._save_status_var = ctk.StringVar(value="")
        ctk.CTkLabel(
            save_frame,
            textvariable=self._save_status_var,
            font=ctk.CTkFont(size=12),
        ).pack(side="left")

    # Composite helpers

    def _section_header(self, title: str, row: int) -> int:
        ctk.CTkLabel(
            self._scroll,
            text=title,
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
            self._scroll,
            text=label,
            anchor="e",
            width=_LABEL_W,
        ).grid(row=row, column=0, sticky="e", padx=(_PAD_X, 8), pady=_PAD_Y)

        ctk.CTkEntry(
            self._scroll,
            textvariable=var,
            width=_ENTRY_W,
            placeholder_text=placeholder,
        ).grid(row=row, column=1, sticky="w", pady=_PAD_Y)
        return row + 1

    def _template_picker_row(self, row: int) -> int:
        ctk.CTkLabel(
            self._scroll,
            text="Template (.docx):",
            anchor="e",
            width=_LABEL_W,
        ).grid(row=row, column=0, sticky="e", padx=(_PAD_X, 8), pady=_PAD_Y)

        frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        frame.grid(row=row, column=1, sticky="w", pady=_PAD_Y)

        ctk.CTkEntry(
            frame,
            textvariable=self._template_var,
            width=_ENTRY_W - (_BTN_W * 2) - 16,
        ).pack(side="left")

        ctk.CTkButton(
            frame,
            text="Browse",
            width=_BTN_W,
            command=self._browse_template,
        ).pack(side="left", padx=(6, 0))

        ctk.CTkButton(
            frame,
            text="Scan",
            width=_BTN_W,
            command=lambda: self._scan_template_variables(show_message=True),
        ).pack(side="left", padx=(6, 0))
        return row + 1

    # Profile list management

    def _refresh_profile_list(self) -> None:
        for widget in self._profile_listbox.winfo_children():
            widget.destroy()

        for name in self._cfg.list_profile_names():
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

    # Form actions

    def _new_profile(self) -> None:
        self._editing_profile = None
        self._excel_headers = []
        self._template_variables = []
        self._mapping_fields = self._build_mapping_fields([])

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
        self._wa_template_name_var.set("")
        self._wa_template_language_var.set("")
        self._wa_template_params_var.set("NAME, ACCOUNTNO, drive_link, OFFICER_NO")
        self._template_hint_var.set(
            "Select a .docx template. The app will read {{VARIABLES}} automatically."
        )
        self._excel_hint_var.set("Load a sample Excel to fill column dropdowns automatically.")
        self._save_status_var.set("")
        self._render_mapping_rows()

    def _browse_template(self) -> None:
        from tkinter import filedialog

        path = filedialog.askopenfilename(
            title="Select Word template",
            filetypes=[("Word templates", "*.docx"), ("All files", "*.*")],
        )
        if not path:
            return

        self._template_var.set(path)
        self._scan_template_variables(show_message=True)

    def _load_profile_into_form(self, profile_name: str) -> None:
        profile = self._cfg.get_profile(profile_name)
        if profile is None:
            return

        self._editing_profile = profile_name
        self._excel_headers = []

        self._profile_name_var.set(profile_name)
        self._display_name_var.set(profile.get("display_name") or profile_name)
        self._notice_type_var.set(profile.get("notice_type") or VALID_NOTICE_TYPES[0])
        self._template_var.set(profile.get("template_path") or "")
        self._email_subject_var.set(profile.get("email_subject") or "")
        self._email_body_text.delete("1.0", "end")
        self._email_body_text.insert("1.0", profile.get("email_body") or "")
        self._wa_template_name_var.set(profile.get("wa_template_name") or "")
        self._wa_template_language_var.set(profile.get("wa_template_language") or "")
        if "wa_template_params" not in profile:
            self._wa_template_params_var.set("NAME, ACCOUNTNO, drive_link, OFFICER_NO")
        else:
            saved_params = profile.get("wa_template_params")
            self._wa_template_params_var.set(
                ", ".join(saved_params) if isinstance(saved_params, (list, tuple)) else ""
            )

        col_mapping = profile.get("column_mapping") or {}
        scanned = self._scan_template_variables(
            show_message=False,
            saved_mapping=col_mapping,
        )
        if not scanned:
            fallback_vars = profile.get("template_variables") or list(col_mapping.keys())
            self._template_variables = _ordered_unique(fallback_vars)
            self._mapping_fields = self._build_mapping_fields(self._template_variables)
            self._render_mapping_rows(saved_mapping=col_mapping)
            self._template_hint_var.set(
                "Template could not be scanned now. Saved mapping is loaded."
            )

        self._excel_hint_var.set("Load a sample Excel to refresh column dropdowns.")
        self._save_status_var.set("")

    def _scan_template_variables(
        self,
        show_message: bool,
        saved_mapping: dict | None = None,
    ) -> bool:
        from tkinter import messagebox

        raw_path = self._template_var.get().strip()
        if not raw_path:
            self._template_hint_var.set("Select a .docx template first.")
            return False

        template_path = self._cfg.resolve_path(raw_path)
        if not os.path.exists(template_path):
            message = f"Template file not found: {template_path}"
            self._template_hint_var.set(message)
            if show_message:
                messagebox.showerror("Template Not Found", message)
            return False

        try:
            variables = get_template_variables(template_path)
        except Exception as exc:
            message = f"Could not scan template variables: {exc}"
            self._template_hint_var.set(message)
            if show_message:
                messagebox.showerror("Template Scan Error", message)
            return False

        self._template_variables = _ordered_unique(list(variables))
        self._mapping_fields = self._build_mapping_fields(self._template_variables)
        self._render_mapping_rows(saved_mapping=saved_mapping)

        auto_vars = [v for v in self._template_variables if v in _AUTO_TEMPLATE_VARIABLES]
        mapped_template_vars = [
            v for v in self._template_variables if v not in _AUTO_TEMPLATE_VARIABLES
        ]
        if self._template_variables:
            hint = (
                f"Found {len(mapped_template_vars)} template variable"
                f"{'s' if len(mapped_template_vars) != 1 else ''} to map."
            )
            if auto_vars:
                hint += " Auto-filled: " + ", ".join(auto_vars) + "."
        else:
            hint = "No {{VARIABLE}} placeholders found. Only app-required fields are shown."
        self._template_hint_var.set(hint)
        return True

    def _load_sample_excel(self) -> None:
        from tkinter import filedialog, messagebox

        path = filedialog.askopenfilename(
            title="Select a sample Excel file to read column headers",
            filetypes=[("Excel workbooks", "*.xlsx"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            headers = get_column_headers(path)
        except Exception as exc:
            messagebox.showerror("Excel Read Error", f"Could not read Excel file:\n{exc}")
            return

        if not headers:
            messagebox.showwarning("No Headers", "No column headers found in the Excel file.")
            return

        self._excel_headers = headers
        self._excel_hint_var.set(f"{len(headers)} columns loaded from: {os.path.basename(path)}")

        if not self._mapping_fields and self._template_var.get().strip():
            self._scan_template_variables(show_message=False)
        else:
            self._render_mapping_rows()

    def _delete_profile(self) -> None:
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
        profile_key = self._profile_name_var.get().strip()
        if not profile_key:
            self._save_status_var.set("Profile Key is required.")
            return

        if not re.match(r"^[A-Za-z0-9_]+$", profile_key):
            self._save_status_var.set("Key: letters, digits, underscores only.")
            return

        raw_template_path = self._template_var.get().strip()
        if not raw_template_path:
            self._save_status_var.set("Template path is required.")
            return

        if not self._scan_template_variables(show_message=False):
            self._save_status_var.set("Template must be readable before saving.")
            return

        col_mapping: dict[str, str] = {}
        missing: list[str] = []
        for key, label, _source, required in self._mapping_fields:
            combo = self._col_combos.get(key)
            value = combo.get().strip() if combo else ""
            if value == _UNMAPPED:
                value = ""
            if required and not value:
                missing.append(label)
            if value:
                col_mapping[key] = value

        if missing:
            self._save_status_var.set(f"Map required field: {missing[0]}")
            return

        template_vars = _ordered_unique(self._template_variables)
        auto_template_vars = [v for v in template_vars if v in _AUTO_TEMPLATE_VARIABLES]
        required_fields = [
            key for key, _label, _source, required in self._mapping_fields
            if required
        ]

        email_body = self._email_body_text.get("1.0", "end").rstrip("\n")
        existing_profile = self._cfg.get_profile(profile_key) or {}
        wa_template_params, wa_params_error = _parse_whatsapp_template_params(
            self._wa_template_params_var.get()
        )
        if wa_params_error:
            self._save_status_var.set(wa_params_error)
            return
        profile_data = {
            **existing_profile,
            "display_name": self._display_name_var.get().strip() or profile_key,
            "template_path": self._cfg.make_path_portable(raw_template_path),
            "notice_type": self._notice_type_var.get(),
            "email_subject": self._email_subject_var.get().strip(),
            "email_body": email_body,
            "wa_template_name": self._wa_template_name_var.get().strip(),
            "wa_template_language": self._wa_template_language_var.get().strip(),
            "wa_template_params": wa_template_params,
            "template_variables": template_vars,
            "auto_template_variables": auto_template_vars,
            "required_fields": required_fields,
            "column_mapping": col_mapping,
        }

        self._cfg.save_profile(profile_key, profile_data)
        self._cfg.save()

        self._editing_profile = profile_key
        self._save_status_var.set(f"Profile '{profile_key}' saved.")
        self._refresh_profile_list()
        self._app.notify_profiles_changed()

    # Mapping UI

    def _build_mapping_fields(self, template_variables: list[str]) -> list[tuple[str, str, str, bool]]:
        fields: list[tuple[str, str, str, bool]] = []
        seen: set[str] = set()

        for variable in template_variables:
            if variable in _AUTO_TEMPLATE_VARIABLES or variable in seen:
                continue
            fields.append((variable, _friendly_label(variable), "Template variable", False))
            seen.add(variable)

        for key, label, source, required in _OPERATIONAL_FIELDS:
            if key in seen:
                continue
            fields.append((key, label, source, required))
            seen.add(key)

        return fields

    def _render_mapping_rows(self, saved_mapping: dict | None = None) -> None:
        existing_values = self._current_mapping_values()
        for widget in self._mapping_frame.winfo_children():
            widget.destroy()

        self._col_combos = {}

        if not self._mapping_fields:
            ctk.CTkLabel(
                self._mapping_frame,
                text="Select or scan a Word template to load mapping rows.",
                text_color="gray60",
                anchor="w",
            ).grid(row=0, column=0, sticky="w", pady=(2, 8))
            return

        header_values = [_UNMAPPED] + self._excel_headers

        ctk.CTkLabel(
            self._mapping_frame,
            text="Variable",
            font=ctk.CTkFont(size=11, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))
        ctk.CTkLabel(
            self._mapping_frame,
            text="Excel Column",
            font=ctk.CTkFont(size=11, weight="bold"),
            anchor="w",
        ).grid(row=0, column=1, sticky="w", pady=(0, 4))
        ctk.CTkLabel(
            self._mapping_frame,
            text="Source",
            font=ctk.CTkFont(size=11, weight="bold"),
            anchor="w",
        ).grid(row=0, column=2, sticky="w", pady=(0, 4), padx=(8, 0))
        ctk.CTkLabel(
            self._mapping_frame,
            text="Status",
            font=ctk.CTkFont(size=11, weight="bold"),
            anchor="w",
        ).grid(row=0, column=3, sticky="w", pady=(0, 4), padx=(8, 0))

        for row, (key, label, source, required) in enumerate(self._mapping_fields, start=1):
            ctk.CTkLabel(
                self._mapping_frame,
                text=f"{label} ({key})",
                anchor="w",
                width=_LABEL_W + 90,
            ).grid(row=row, column=0, sticky="w", pady=_PAD_Y)

            selected = self._selected_mapping_value(
                key,
                required=required,
                saved_mapping=saved_mapping,
                existing_values=existing_values,
            )
            values = self._values_with_selected(header_values, selected)

            combo = ctk.CTkComboBox(
                self._mapping_frame,
                values=values,
                width=_ENTRY_W,
            )
            combo.set(selected or _UNMAPPED)
            combo.grid(row=row, column=1, sticky="w", pady=_PAD_Y)
            self._col_combos[key] = combo

            ctk.CTkLabel(
                self._mapping_frame,
                text=source,
                font=ctk.CTkFont(size=11),
                text_color="gray60",
                width=170,
                anchor="w",
            ).grid(row=row, column=2, sticky="w", padx=(8, 0), pady=_PAD_Y)
            ctk.CTkLabel(
                self._mapping_frame,
                text="Required" if required else "Optional",
                font=ctk.CTkFont(size=11),
                text_color=("orange" if required else "gray60"),
                width=80,
                anchor="w",
            ).grid(row=row, column=3, sticky="w", padx=(8, 0), pady=_PAD_Y)

    def _current_mapping_values(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for key, combo in self._col_combos.items():
            value = combo.get().strip()
            if value and value != _UNMAPPED:
                result[key] = value
        return result

    def _selected_mapping_value(
        self,
        key: str,
        required: bool,
        saved_mapping: dict | None,
        existing_values: dict[str, str],
    ) -> str:
        guessed = self._guess_excel_header(key)
        if saved_mapping and saved_mapping.get(key):
            saved = str(saved_mapping[key]).strip()
            saved_looks_like_placeholder = _normalise_name(saved) == _normalise_name(key)
            saved_missing_from_excel = self._excel_headers and saved not in self._excel_headers
            if saved_missing_from_excel and saved_looks_like_placeholder:
                if guessed:
                    return guessed
                return _UNMAPPED
            if saved_missing_from_excel and guessed:
                return guessed
            return saved

        if existing_values.get(key):
            existing = existing_values[key]
            existing_looks_like_default = _normalise_name(existing) == _normalise_name(key)
            existing_missing_from_excel = self._excel_headers and existing not in self._excel_headers
            if guessed and existing_looks_like_default and existing_missing_from_excel:
                return guessed
            return existing

        if guessed:
            return guessed

        return _UNMAPPED

    def _guess_excel_header(self, key: str) -> str:
        if not self._excel_headers:
            return ""

        key_norm = _normalise_name(key)
        for header in self._excel_headers:
            if header == key:
                return header

        for header in self._excel_headers:
            if _normalise_name(header) == key_norm:
                return header

        for header in self._excel_headers:
            header_norm = _normalise_name(header)
            if key_norm and key_norm in header_norm:
                return header

        return ""

    @staticmethod
    def _values_with_selected(values: list[str], selected: str) -> list[str]:
        if selected and selected not in values:
            return [_UNMAPPED, selected] + [v for v in values if v != _UNMAPPED]
        return values
