"""
utils/logger.py
---------------
Structured per-recipient logging for each batch.
Each batch creates a single JSON log file, flushed atomically after every row.
"""

import csv
import json
import os
from datetime import datetime

from utils.atomic_io import atomic_replace


class BatchLogger:
    """Append-mode structured logger for one batch run."""

    def __init__(self, log_path: str):
        self.log_path = log_path
        self._entries: list[dict] = []

        # Load existing entries if resuming
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    self._entries = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._entries = []

    def log_row(
        self,
        index: int,
        row: dict,
        pdf_path: str,
        drive_link: str,
        email_status: str,
        email_error: str,
        whatsapp_status: str,
        whatsapp_error: str,
        drive_upload_status: str = "",
        drive_upload_error: str = "",
        doc_render_seconds: float = 0.0,
        pdf_convert_seconds: float = 0.0,
        drive_upload_seconds: float = 0.0,
    ) -> None:
        """Append one recipient result and flush to disk."""
        row_data = dict(row)
        self._entries.append({
            "index": index,
            "name": row.get("NAME", ""),
            "email": row.get("EMAILID", ""),
            "phone": row.get("MOBILENO", ""),
            "row_data": row_data,
            "pdf_path": pdf_path,
            "drive_link": drive_link,
            "drive_upload_status": drive_upload_status,
            "drive_upload_error": drive_upload_error,
            "doc_render_seconds": doc_render_seconds,
            "pdf_convert_seconds": pdf_convert_seconds,
            "drive_upload_seconds": drive_upload_seconds,
            "email_status": email_status,
            "email_error": email_error,
            "whatsapp_status": whatsapp_status,
            "whatsapp_error": whatsapp_error,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        self._flush()

    def _flush(self) -> None:
        """Write all entries to disk atomically."""
        tmp_path = self.log_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self._entries, f, indent=2, ensure_ascii=False)
        atomic_replace(tmp_path, self.log_path)

    def get_summary(self) -> dict:
        """Return aggregate counts from all logged entries."""
        s = {"total": len(self._entries),
             "email_sent": 0, "email_failed": 0, "email_skipped": 0,
             "wa_sent": 0, "wa_failed": 0, "wa_skipped": 0}
        for e in self._entries:
            match e.get("email_status", ""):
                case "sent":   s["email_sent"] += 1
                case "failed": s["email_failed"] += 1
                case _:        s["email_skipped"] += 1
            match e.get("whatsapp_status", ""):
                case "sent":   s["wa_sent"] += 1
                case "failed": s["wa_failed"] += 1
                case _:        s["wa_skipped"] += 1
        return s

    def get_failed_entries(self) -> list[dict]:
        """Return entries where email OR WhatsApp failed."""
        return [e for e in self._entries
                if e.get("email_status") == "failed"
                or e.get("whatsapp_status") == "failed"]

    def export_csv(self, csv_path: str) -> None:
        """Export all log entries to CSV for court records."""
        if not self._entries:
            return
        fieldnames = []
        for entry in self._entries:
            for key in entry.keys():
                if key not in fieldnames:
                    fieldnames.append(key)
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self._entries)
