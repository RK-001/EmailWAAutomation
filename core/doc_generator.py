"""
core/doc_generator.py
---------------------
Render a Word (.docx) template with row data using docxtpl.

Safety pipeline before every render:
  1. Pre-check: all {{variables}} in template must be present in context
  2. Sanitize: None → "", escape XML chars (& < >)
  3. Render: docxtpl fills placeholders
  4. Save: unique filename per recipient in output subdirectory

Output filename: <output_dir>/<batch_id>/<ACCOUNTNO>_<NAME>.docx
"""

import os
import re

from docxtpl import DocxTemplate

from utils.sanitizer import sanitize_context
from utils.validators import validate_template_variables


def _safe_filename(text: str, max_len: int = 40) -> str:
    """
    Convert arbitrary text to a safe filename component.
    Strips chars not allowed in Windows filenames.
    """
    # Remove characters not allowed in Windows filenames
    safe = re.sub(r'[\\/*?:"<>|]', "", str(text))
    # Replace spaces with underscores
    safe = safe.replace(" ", "_")
    # Limit length
    return safe[:max_len]


def render_document(
    template_path: str,
    context: dict,
    output_dir: str,
    batch_id: str,
    row_index: int,
) -> str:
    """
    Render a .docx template with the given context and save to disk.

    Args:
        template_path:  Path to the .docx Jinja2 template.
        context:        Row data dict (raw — will be sanitized here).
        output_dir:     Root output directory (e.g., "./output").
        batch_id:       Unique batch identifier string (becomes subdirectory name).
        row_index:      0-based row index (used in filename for uniqueness).

    Returns:
        Absolute path to the generated .docx file.

    Raises:
        FileNotFoundError: If template_path does not exist.
        ValueError:        If template has undefined variables not in context.
        OSError:           If output directory cannot be created or file cannot be saved.
    """
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template not found: {template_path}")

    # ── Step 1: Pre-check template variables ─────────────────────────────────
    ok, missing = validate_template_variables(template_path, list(context.keys()))
    if not ok:
        raise ValueError(
            f"Template has undefined variables not present in data:\n"
            + "\n".join(f"  - {{{{{v}}}}}" for v in missing)
        )

    # ── Step 2: Sanitize context (None → "", escape XML) ─────────────────────
    safe_context = sanitize_context(context)

    # ── Step 3: Render ────────────────────────────────────────────────────────
    tpl = DocxTemplate(template_path)
    tpl.render(safe_context)

    # ── Step 4: Build output path ─────────────────────────────────────────────
    batch_output_dir = os.path.join(output_dir, _safe_filename(batch_id))
    os.makedirs(batch_output_dir, exist_ok=True)

    # Build filename: index_ACCOUNTNO_NAME.docx
    account = _safe_filename(context.get("ACCOUNTNO") or f"row{row_index}")
    name = _safe_filename(context.get("NAME") or "unknown")
    filename = f"{row_index:04d}_{account}_{name}.docx"
    output_path = os.path.join(batch_output_dir, filename)

    tpl.save(output_path)
    return os.path.abspath(output_path)


def get_template_variables(template_path: str) -> list[str]:
    """
    Return all Jinja2 variable names declared in a .docx template.
    Used by the Profiles tab to suggest column mappings.

    Args:
        template_path: Path to the .docx template file.

    Returns:
        Sorted list of variable name strings.

    Raises:
        FileNotFoundError: If template does not exist.
    """
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template not found: {template_path}")
    tpl = DocxTemplate(template_path)
    return sorted(tpl.get_undeclared_template_variables())
