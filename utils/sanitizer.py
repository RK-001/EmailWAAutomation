"""
utils/sanitizer.py
------------------
Sanitizes Excel row data before passing to docxtpl.

Two-step safety:
  1. Convert None/empty → empty string  (prevents "None" appearing in documents)
  2. Escape XML special chars: & < >    (prevents Word XML corruption)

All values are cast to str before escaping so numeric/date cells are safe.
"""


def sanitize_context(row_dict: dict) -> dict:
    """
    Prepare a row dict for safe docxtpl rendering.

    Args:
        row_dict: Raw row from excel_reader (values may be None, int, float, date, str)

    Returns:
        New dict with all values as XML-safe strings.
    """
    sanitized = {}
    for key, value in row_dict.items():
        # Step 1: None → empty string
        if value is None:
            value = ""
        # Step 2: Cast to str
        value = str(value)
        # Step 3: Escape XML-breaking characters
        value = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        sanitized[key] = value
    return sanitized


def unescape_for_display(text: str) -> str:
    """
    Reverse XML escaping for UI display purposes only.
    Do NOT use on data that will be passed back to docxtpl.
    """
    return (
        text.replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
    )
