"""
core/excel_reader.py
--------------------
Read an Excel (.xlsx) file and return a list of row dicts.

Features:
  - First row is treated as headers (column names become dict keys)
  - Empty cells → None (caller should use sanitizer.sanitize_context)
  - datetime cells → formatted string "DD/MM/YYYY"
  - Numeric cells → str (trailing .0 removed for integers)
  - Applies column mapping from profile to rename columns
  - Validates that required columns are present
"""

from datetime import datetime, date

import openpyxl


def _format_cell_value(value) -> str | None:
    """
    Convert an openpyxl cell value to a clean string.

    - datetime/date  → "DD/MM/YYYY"
    - int/float      → str without trailing ".0"
    - str            → stripped
    - None           → None
    """
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, float):
        # Remove ".0" for whole numbers (e.g., 9876543210.0 → "9876543210")
        if value.is_integer():
            return str(int(value))
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value.strip() or None   # Empty strings → None
    return str(value)


def read_excel(
    excel_path: str,
    column_mapping: dict | None = None,
    sheet_name: str | None = None,
) -> list[dict]:
    """
    Read an Excel file and return rows as a list of dicts.

    Args:
        excel_path:     Full path to the .xlsx file.
        column_mapping: Optional dict {standard_key: excel_column_header}.
                        e.g. {"NAME": "Customer Name", "MOBILENO": "Mobile"}
                        If provided, output dicts use the standard keys.
                        If None, output dicts use the raw header row values.
        sheet_name:     Sheet to read. If None, reads the active (first) sheet.

    Returns:
        List of row dicts. Keys are either mapped (if column_mapping provided)
        or raw header names. Values are strings (or None for empty cells).

    Raises:
        FileNotFoundError: If the Excel file does not exist.
        ValueError:        If the file has no header row or required columns missing.
    """
    if not excel_path:
        raise ValueError("Excel path cannot be empty.")

    wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
    ws = wb[sheet_name] if sheet_name else wb.active

    rows_iter = ws.iter_rows(values_only=True)

    # Read header row
    try:
        raw_headers = next(rows_iter)
    except StopIteration:
        raise ValueError("Excel file is empty — no header row found.")

    # Clean headers: strip whitespace, remove None entries
    headers = [str(h).strip() if h is not None else f"_col_{i}" for i, h in enumerate(raw_headers)]

    if not any(h for h in headers if not h.startswith("_col_")):
        raise ValueError("Excel file header row appears empty.")

    # Validate column_mapping: check all mapped columns exist
    if column_mapping:
        missing_cols = []
        for std_key, excel_col in column_mapping.items():
            if excel_col not in headers:
                missing_cols.append(f"'{excel_col}' (needed for '{std_key}')")
        if missing_cols:
            raise ValueError(
                f"Excel file is missing required columns:\n" +
                "\n".join(f"  - {c}" for c in missing_cols) +
                f"\n\nAvailable columns: {headers}"
            )

    # Build reverse map: excel_header → standard_key (for fast lookup)
    reverse_map: dict[str, str] = {}
    if column_mapping:
        for std_key, excel_col in column_mapping.items():
            reverse_map[excel_col] = std_key

    # Read data rows
    result: list[dict] = []
    for raw_row in rows_iter:
        row_dict: dict = {}
        for header, cell_value in zip(headers, raw_row):
            cleaned = _format_cell_value(cell_value)
            output_key = reverse_map.get(header, header) if column_mapping else header
            row_dict[output_key] = cleaned

        # Skip entirely blank rows
        if all(v is None for v in row_dict.values()):
            continue

        result.append(row_dict)

    wb.close()
    return result


def get_column_headers(excel_path: str, sheet_name: str | None = None) -> list[str]:
    """
    Return only the column headers from an Excel file.
    Used by the Profiles tab to populate column mapping dropdowns.

    Args:
        excel_path: Full path to the .xlsx file.
        sheet_name: Sheet to read. None = active sheet.

    Returns:
        List of header strings.
    """
    wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
    ws = wb[sheet_name] if sheet_name else wb.active
    header_row = next(ws.iter_rows(values_only=True), None)
    wb.close()

    if header_row is None:
        return []
    return [str(h).strip() for h in header_row if h is not None]
