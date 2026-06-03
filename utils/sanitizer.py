"""
utils/sanitizer.py
------------------
Sanitizes Excel row data before passing it to docxtpl.

Two-step safety:
  1. Convert None/empty values to "NA"
  2. Escape XML special chars: & < >

All values are cast to str before escaping so numeric/date cells are safe.
"""


def sanitize_context(row_dict: dict, blank_value: str = "NA") -> dict:
    """
    Prepare a row dict for safe docxtpl rendering.

    Args:
        row_dict: Raw row from excel_reader.
        blank_value: Value used when a mapped Excel cell is blank.

    Returns:
        New dict with all values as XML-safe strings.
    """
    sanitized = {}
    for key, value in row_dict.items():
        if value is None:
            value = blank_value
        else:
            value = str(value)
            if not value.strip():
                value = blank_value

        value = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        sanitized[key] = value
    return sanitized


def unescape_for_display(text: str) -> str:
    """
    Reverse XML escaping for UI display purposes only.
    Do not use on data that will be passed back to docxtpl.
    """
    return (
        text.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
    )
