"""
utils/atomic_io.py
------------------
Shared atomic file-write utilities.

OneDrive and Windows antivirus scanners briefly lock files during sync/scan,
causing os.replace() to fail with PermissionError (WinError 5).
These helpers retry the rename a few times to handle transient locks.
"""

import json
import os
import tempfile
import time


def atomic_replace(tmp_path: str, dest_path: str, retries: int = 5, delay: float = 0.1) -> None:
    """
    Rename tmp_path → dest_path with retries for transient file locks.

    Raises:
        PermissionError: If all retries exhausted.
    """
    last_exc: Exception | None = None
    for _ in range(retries):
        try:
            os.replace(tmp_path, dest_path)
            return
        except PermissionError as exc:
            last_exc = exc
            time.sleep(delay)
    raise last_exc  # type: ignore[misc]


def atomic_write_json(dest_path: str, data: dict) -> None:
    """
    Write a dict as JSON atomically (write-to-tmp → rename).
    Creates parent directory if needed.
    """
    dir_name = os.path.dirname(dest_path) or "."
    os.makedirs(dir_name, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        atomic_replace(tmp_path, dest_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
