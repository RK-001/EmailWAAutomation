"""
utils/config_manager.py
-----------------------
Load, validate, save, and repair config.json.

Design:
- Loads config from disk on startup; provides defaults for missing keys.
- Saves atomically (write-to-tmp → os.replace).
- Validates required fields before returning to caller.
- On JSON corruption: renames broken file to config.json.bak and creates fresh.
"""

import json
import os
import shutil
import tempfile
from copy import deepcopy
from pathlib import Path


# ── Default config template ─────────────────────────────────────────────────

_DEFAULT_CONFIG: dict = {
    "gmail": {
        "sender_email": "",
        "app_password": "",
    },
    "aisensy": {
        "api_key": "",
        "template_name": "legal_notice_notification",
        "mock_mode": True,
    },
    "google_drive": {
        "service_account_json_path": "drive_credentials.json",
        "upload_folder_id": "",
        "auto_delete_days": 30,
        "mock_mode": True,
    },
    "profiles": {},
    "settings": {
        "output_folder": "./output",
        "log_folder": "./logs",
        "batch_restart_every": 50,
        "send_delay_min_sec": 3,
        "send_delay_max_sec": 5,
        "max_emails_per_day": 450,
        "drive_cleanup_enabled": True,
        "lawyer_name": "",
        "firm_name": "",
    },
}

# Valid notice types for compliance gate
VALID_NOTICE_TYPES = [
    "EMI_DEFAULT",
    "PRE_LITIGATION",
    "SECTION_138",
    "SARFAESI",
    "OTHER",
]


class ConfigManager:
    """
    Manages the application configuration file.

    Usage:
        cfg = ConfigManager("config.json")
        cfg.get("gmail.sender_email")   → str
        cfg.set("gmail.sender_email", "x@y.com")
        cfg.save()
    """

    def __init__(self, config_path: str):
        self.config_path = config_path
        self._data: dict = {}
        self.load()

    # ── Public API ────────────────────────────────────────────────────────────

    def load(self) -> None:
        """
        Load config from disk. On corruption, backs up broken file and
        restores defaults. On missing file, creates default config.
        """
        if not os.path.exists(self.config_path):
            self._data = deepcopy(_DEFAULT_CONFIG)
            self.save()
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            # Merge loaded data over defaults (preserves any added keys)
            self._data = self._merge_defaults(loaded, deepcopy(_DEFAULT_CONFIG))
        except (json.JSONDecodeError, OSError):
            # Backup corrupted file and start fresh
            bak_path = self.config_path + ".bak"
            shutil.copy2(self.config_path, bak_path)
            self._data = deepcopy(_DEFAULT_CONFIG)
            self.save()

    def save(self) -> None:
        """Atomically save current config to disk."""
        dir_name = str(Path(self.config_path).parent)
        os.makedirs(dir_name, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.config_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def get(self, dot_path: str, default=None):
        """
        Retrieve a nested config value using dot notation.

        Example:
            cfg.get("gmail.sender_email")
            cfg.get("settings.batch_restart_every")
        """
        keys = dot_path.split(".")
        node = self._data
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    def set(self, dot_path: str, value) -> None:
        """
        Set a nested config value using dot notation.
        Creates intermediate dicts as needed.
        Does NOT save — call save() explicitly.
        """
        keys = dot_path.split(".")
        node = self._data
        for key in keys[:-1]:
            node = node.setdefault(key, {})
        node[keys[-1]] = value

    def get_all(self) -> dict:
        """Return a deep copy of the full config dict."""
        return deepcopy(self._data)

    def get_base_dir(self) -> str:
        """Return the directory that owns config.json."""
        return str(Path(self.config_path).parent)

    def resolve_path(self, maybe_relative_path: str) -> str:
        """
        Resolve a configured path relative to config.json when needed.

        Empty strings are returned unchanged. Absolute paths are preserved.
        """
        if not maybe_relative_path:
            return maybe_relative_path
        if os.path.isabs(maybe_relative_path):
            return maybe_relative_path
        return os.path.abspath(os.path.join(self.get_base_dir(), maybe_relative_path))

    def make_path_portable(self, raw_path: str) -> str:
        """
        Store a path relative to config.json when it points inside the project.

        Absolute paths outside the project are preserved.
        """
        if not raw_path:
            return raw_path
        abs_path = os.path.abspath(raw_path)
        base_dir = os.path.abspath(self.get_base_dir())
        try:
            rel_path = os.path.relpath(abs_path, base_dir)
        except ValueError:
            return abs_path
        if rel_path.startswith(".."):
            return abs_path
        return rel_path.replace("\\", "/")

    # ── Profile helpers ───────────────────────────────────────────────────────

    def get_profiles(self) -> dict:
        """Return all profiles as a dict."""
        return deepcopy(self._data.get("profiles", {}))

    def get_profile(self, name: str) -> dict | None:
        """Return a single profile by name, or None."""
        return deepcopy(self._data.get("profiles", {}).get(name))

    def save_profile(self, name: str, profile: dict) -> None:
        """Add or update a profile and save config."""
        self._data.setdefault("profiles", {})[name] = profile
        self.save()

    def delete_profile(self, name: str) -> bool:
        """
        Delete a profile by name.

        Returns:
            True if deleted, False if not found.
        """
        profiles = self._data.get("profiles", {})
        if name in profiles:
            del profiles[name]
            self.save()
            return True
        return False

    def list_profile_names(self) -> list[str]:
        """Return sorted list of profile names."""
        return sorted(self._data.get("profiles", {}).keys())

    # ── Validation ────────────────────────────────────────────────────────────

    def validate_gmail(self) -> list[str]:
        """
        Validate Gmail settings.

        Returns:
            List of error strings (empty = valid).
        """
        errors = []
        email = self.get("gmail.sender_email", "")
        password = self.get("gmail.app_password", "")
        if not email:
            errors.append("Gmail sender email is not set.")
        if not password:
            errors.append("Gmail app password is not set.")
        return errors

    def validate_aisensy(self) -> list[str]:
        """Validate AiSensy settings (skipped in mock mode)."""
        if self.get("aisensy.mock_mode", True):
            return []
        errors = []
        if not self.get("aisensy.api_key", ""):
            errors.append("AiSensy API key is not set.")
        if not self.get("aisensy.template_name", ""):
            errors.append("AiSensy template name is not set.")
        return errors

    def validate_google_drive(self) -> list[str]:
        """Validate Google Drive settings (skipped in mock mode)."""
        if self.get("google_drive.mock_mode", True):
            return []
        errors = []
        creds_path = self.resolve_path(self.get("google_drive.service_account_json_path", ""))
        if not creds_path:
            errors.append("Google Drive service account JSON path is not set.")
        elif not os.path.exists(creds_path):
            errors.append(f"Drive credentials file not found: {creds_path}")
        if not self.get("google_drive.upload_folder_id", ""):
            errors.append("Google Drive upload folder ID is not set.")
        return errors

    def validate_profile(self, profile_name: str) -> list[str]:
        """
        Validate a profile configuration.

        Returns:
            List of error strings (empty = valid).
        """
        profile = self.get_profile(profile_name)
        errors = []
        if profile is None:
            return [f"Profile '{profile_name}' not found."]

        template_path = self.resolve_path(profile.get("template_path", ""))
        if not template_path:
            errors.append("Template path is not set.")
        elif not os.path.exists(template_path):
            errors.append(f"Template file not found: {template_path}")

        notice_type = profile.get("notice_type", "")
        if notice_type not in VALID_NOTICE_TYPES:
            errors.append(
                f"Invalid notice type '{notice_type}'. Must be one of: {VALID_NOTICE_TYPES}"
            )

        required_mapping = ["NAME", "EMAILID", "MOBILENO"]
        col_map = profile.get("column_mapping", {})
        for field in required_mapping:
            if field not in col_map:
                errors.append(f"Column mapping missing required field: '{field}'")

        return errors

    # ── Internal ─────────────────────────────────────────────────────────────

    @staticmethod
    def _merge_defaults(loaded: dict, defaults: dict) -> dict:
        """
        Recursively merge loaded dict over defaults.
        Loaded values win; missing keys are filled from defaults.
        """
        result = deepcopy(defaults)
        for key, value in loaded.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigManager._merge_defaults(value, result[key])
            else:
                result[key] = value
        return result
