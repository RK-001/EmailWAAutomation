"""
utils/checkpoint.py
-------------------
Crash-safe batch checkpoint system.

Saves state atomically so a crash mid-write never corrupts the checkpoint.
On resume, verifies the Excel file hasn't changed (via SHA-256 hash).

Checkpoint file: logs/<batch_id>_checkpoint.json
"""

import hashlib
import json
import os

from utils.atomic_io import atomic_write_json


def compute_excel_hash(excel_path: str) -> str:
    """Compute SHA-256 of an Excel file for change detection."""
    h = hashlib.sha256()
    with open(excel_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class CheckpointManager:
    """
    Stateful checkpoint manager for a batch run.

    Maintains an in-memory checkpoint dict and persists atomically after
    each update.  Automatically resumes from existing checkpoint if the
    Excel hash matches.

    Usage:
        mgr = CheckpointManager(path, batch_id, excel_path, excel_hash, profile, total)
        mgr.mark_result(0, pdf_path="...", drive_link="...")
        mgr.advance_to_sending()
        mgr.mark_sent(0, "sent", "sent")
        mgr.delete()  # on completion
    """

    def __init__(
        self,
        checkpoint_path: str,
        batch_id: str,
        excel_path: str,
        excel_hash: str,
        profile_name: str,
        total_rows: int,
    ):
        self._path = checkpoint_path
        self._batch_id = batch_id
        self._profile_name = profile_name

        # Resume from existing checkpoint if Excel unchanged
        existing = self._load()
        if existing and existing.get("excel_hash") == excel_hash:
            self._data = existing
        else:
            self._data = {
                "batch_id": batch_id,
                "excel_path": excel_path,
                "excel_hash": excel_hash,
                "profile_name": profile_name,
                "stage": "generate",
                "total_rows": total_rows,
                "last_generated_index": -1,
                "last_sent_index": -1,
                "results": {},
            }
            self._save()

    # -- Properties ---

    @property
    def last_generated_index(self) -> int:
        return self._data.get("last_generated_index", -1)

    @property
    def last_sent_index(self) -> int:
        return self._data.get("last_sent_index", -1)

    # -- Read ---

    def get_result(self, index: int) -> dict | None:
        """Return the saved result dict for a row, or None."""
        return self._data.get("results", {}).get(str(index))

    # -- Write ---

    def mark_result(
        self,
        index: int,
        pdf_path: str,
        drive_link: str,
        drive_upload_status: str = "",
        drive_upload_error: str = "",
        doc_render_seconds: float = 0.0,
        pdf_convert_seconds: float = 0.0,
        drive_upload_seconds: float = 0.0,
    ) -> None:
        """Record a successfully generated PDF + Drive link."""
        self._data["last_generated_index"] = index
        self._data["results"][str(index)] = {
            "pdf_path": pdf_path,
            "drive_link": drive_link,
            "drive_upload_status": drive_upload_status,
            "drive_upload_error": drive_upload_error,
            "doc_render_seconds": doc_render_seconds,
            "pdf_convert_seconds": pdf_convert_seconds,
            "drive_upload_seconds": drive_upload_seconds,
            "included": True,
        }
        self._save()

    def mark_sent(self, index: int, email_status: str, wa_status: str) -> None:
        """Record send result for a row."""
        self._data["last_sent_index"] = index
        row_result = self._data["results"].setdefault(str(index), {})
        row_result["email_status"] = email_status
        row_result["wa_status"] = wa_status
        self._save()

    def mark_excluded(self, index: int) -> None:
        """Mark a row as excluded by the user."""
        if str(index) in self._data["results"]:
            self._data["results"][str(index)]["included"] = False
            self._save()

    def advance_to_sending(self) -> None:
        """Move checkpoint stage from 'generate' to 'sending'."""
        self._data["stage"] = "sending"
        self._save()

    def delete(self) -> None:
        """Remove checkpoint file on successful batch completion."""
        if os.path.exists(self._path):
            os.unlink(self._path)

    # -- Internal ---

    def _save(self) -> None:
        atomic_write_json(self._path, self._data)

    def _load(self) -> dict | None:
        if not os.path.exists(self._path):
            return None
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
