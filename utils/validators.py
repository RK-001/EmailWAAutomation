"""
utils/validators.py
-------------------
Input validation for phone numbers, email addresses, and docxtpl template variables.
All validators return (is_valid: bool, error_message: str).
"""

import re
from docxtpl import DocxTemplate


# ---------------------------------------------------------------------------
# Phone validation
# ---------------------------------------------------------------------------

# Accepts: 10-digit Indian mobile (with optional +91 / 91 prefix)
_PHONE_RE = re.compile(r"^(?:\+91|91)?([6-9]\d{9})$")


def validate_phone(phone: str) -> tuple[bool, str]:
    """
    Validate an Indian mobile number.
    Accepts formats: 9876543210 | +919876543210 | 919876543210

    Returns:
        (True, "")        → valid
        (False, message)  → invalid with reason
    """
    if not phone:
        return False, "Phone number is empty."
    phone_stripped = phone.strip().replace(" ", "").replace("-", "")
    match = _PHONE_RE.match(phone_stripped)
    if not match:
        return False, f"Invalid phone: '{phone}'. Must be 10-digit Indian mobile (6-9 start)."
    return True, ""


def normalize_phone(phone: str) -> str:
    """
    Normalize to 10-digit format (strip +91/91 prefix).
    Assumes validate_phone() already passed.
    """
    phone_stripped = phone.strip().replace(" ", "").replace("-", "")
    match = _PHONE_RE.match(phone_stripped)
    return match.group(1) if match else phone_stripped


# ---------------------------------------------------------------------------
# Email validation
# ---------------------------------------------------------------------------

# RFC-5321 simplified pattern; no consecutive dots, valid TLD
_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)


def validate_email(email: str) -> tuple[bool, str]:
    """
    Validate an email address (basic format check).

    Returns:
        (True, "")        → valid
        (False, message)  → invalid with reason
    """
    if not email:
        return False, "Email address is empty."
    email = email.strip()
    if ".." in email:
        return False, f"Invalid email: consecutive dots in '{email}'."
    if not _EMAIL_RE.match(email):
        return False, f"Invalid email format: '{email}'."
    return True, ""


# ---------------------------------------------------------------------------
# Template variable validation
# ---------------------------------------------------------------------------

def validate_template_variables(template_path: str, context_keys: list[str]) -> tuple[bool, list[str]]:
    """
    Check that all Jinja2 placeholders in a .docx template are present in context.

    Args:
        template_path:  Path to the .docx template file.
        context_keys:   List of available keys in the context dict.

    Returns:
        (True, [])              → all variables satisfied
        (False, [missing, ...]) → list of missing variable names
    """
    try:
        tpl = DocxTemplate(template_path)
        required_vars = tpl.get_undeclared_template_variables()
        context_set = set(context_keys)
        missing = [v for v in required_vars if v not in context_set]
        if missing:
            return False, missing
        return True, []
    except Exception as exc:
        # Return as a single-item missing list so the caller can display the error
        return False, [f"Template load error: {exc}"]


def validate_row_required_fields(row: dict, required_fields: list[str]) -> tuple[bool, list[str]]:
    """
    Check that a data row has non-empty values for all required fields.

    Args:
        row:              Row dict from excel_reader.
        required_fields:  List of field names that must not be empty.

    Returns:
        (True, [])              → all fields present
        (False, [missing, ...]) → names of empty/missing fields
    """
    missing = [f for f in required_fields if not str(row.get(f, "") or "").strip()]
    if missing:
        return False, missing
    return True, []
