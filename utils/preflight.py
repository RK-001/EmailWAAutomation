"""
utils/preflight.py
------------------
Pre-batch validation checks run before any PDF generation or sending starts.
Identifies problems early so the user doesn't discover failures mid-batch.

Checks:
  1. Gmail SMTP authentication (live connection test)
  2. Row count vs Gmail 500/day limit (warns at > max_emails_per_day)
  3. Google Drive quota (warns if < 500 MB free) — skipped in mock mode
  4. AiSensy API key reachability — skipped in mock mode
  5. Template file exists and is readable
  6. Output and log folders are writable
"""

import os
import smtplib
import ssl
from typing import Callable
import urllib.error
import urllib.request

from utils.ssl_compat import create_ssl_context, get_merged_ca_bundle_path


# ── Gmail preflight ──────────────────────────────────────────────────────────

def check_gmail_auth(sender_email: str, app_password: str) -> tuple[bool, str]:
    """
    Attempt a real SMTP login to verify Gmail credentials.

    Returns:
        (True, "")                        → credentials valid
        (False, human-readable message)   → credentials invalid or network error
    """
    normalized_password = (app_password or "").strip().replace(" ", "")
    if not sender_email or not normalized_password:
        return False, "Gmail email or app password is not configured."
    try:
        context = create_ssl_context()
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(sender_email.strip(), normalized_password)
        return True, ""
    except smtplib.SMTPAuthenticationError:
        return False, (
            "Gmail authentication failed. Check your App Password.\n"
            "Ensure 2-Step Verification is ON and App Password is used (not your Gmail password)."
        )
    except (smtplib.SMTPException, OSError) as exc:
        return False, f"Gmail connection error: {exc}"


def check_email_capacity(row_count: int, max_per_day: int = 450) -> tuple[bool, str]:
    """
    Warn if the batch exceeds Gmail's safe daily send limit.

    Returns:
        (True, "")       → within limit
        (False, warning) → batch too large (still allowed but warned)
    """
    if row_count > max_per_day:
        return False, (
            f"This batch has {row_count} rows but Gmail allows ~500 emails/day.\n"
            f"Safe limit set to {max_per_day}. Consider splitting into two batches.\n"
            "Last rows in excess of limit may be rejected by Gmail."
        )
    return True, ""


# ── Google Drive preflight ───────────────────────────────────────────────────

def check_drive_quota(service_account_path: str, folder_id: str) -> tuple[bool, str]:
    """
    Check Google Drive available storage quota.
    Warns if less than 500 MB is free.

    Returns:
        (True, "")       → sufficient space
        (False, warning) → low space warning
    """
    try:
        import google_auth_httplib2
        import httplib2
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds = service_account.Credentials.from_service_account_file(
            service_account_path,
            scopes=["https://www.googleapis.com/auth/drive"],
        )
        ca_bundle = get_merged_ca_bundle_path()
        http = (
            httplib2.Http(ca_certs=ca_bundle, timeout=30)
            if ca_bundle
            else httplib2.Http(timeout=30)
        )
        authed_http = google_auth_httplib2.AuthorizedHttp(creds, http=http)
        service = build(
            "drive",
            "v3",
            http=authed_http,
            cache_discovery=False,
            static_discovery=False,
        )
        about = service.about().get(fields="storageQuota").execute()
        quota = about.get("storageQuota", {})

        limit = int(quota.get("limit", 0))
        used = int(quota.get("usage", 0))
        free_mb = (limit - used) // (1024 * 1024)

        if limit == 0:
            # Unlimited (Google Workspace)
            return True, ""
        if free_mb < 500:
            return False, (
                f"Google Drive has only {free_mb} MB free. "
                "Consider cleaning up old files before this batch."
            )
        return True, ""
    except Exception as exc:
        text = str(exc)
        lower = text.lower()
        if "zscaler" in lower or "restricted based on" in lower:
            return False, (
                "Google Drive is blocked by your office/network security policy "
                "(Zscaler). Use a network where Drive is allowed, ask IT to whitelist "
                "Google Drive / Drive API, or turn Drive mock mode ON for testing."
            )
        return False, f"Could not check Drive quota: {exc}"


# ── AiSensy preflight ────────────────────────────────────────────────────────

def check_aisensy_reachability(api_key: str) -> tuple[bool, str]:
    """
    Lightweight connectivity check for AiSensy API endpoint.
    Does NOT send a message — just checks the endpoint responds.

    Returns:
        (True, "")       → API endpoint reachable
        (False, message) → connection error
    """
    if not api_key:
        return False, "AiSensy API key is not configured."
    try:
        # HEAD request — no message sent, just checks reachability.
        # We use urllib here because on some Windows machines `requests`
        # may fail SSL verification while the OS trust store works fine.
        req = urllib.request.Request(
            "https://backend.aisensy.com/campaign/t1/api/v2",
            method="HEAD",
        )
        ctx = create_ssl_context()
        with urllib.request.urlopen(req, context=ctx, timeout=8) as resp:
            status_code = getattr(resp, "status", 200)
        if status_code in (200, 401, 403, 404, 405):
            return True, ""
        return False, f"AiSensy endpoint returned unexpected status: {status_code}"
    except urllib.error.HTTPError as exc:
        if exc.code in (200, 401, 403, 404, 405):
            return True, ""
        return False, f"AiSensy endpoint returned unexpected status: {exc.code}"
    except TimeoutError:
        return False, "AiSensy API connection timed out."
    except ssl.SSLError as exc:
        return False, f"AiSensy SSL error: {exc}"
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        return False, f"Cannot reach AiSensy API: {reason}"
    except Exception as exc:
        return False, f"AiSensy connectivity error: {exc}"


# ── File system preflight ────────────────────────────────────────────────────

def check_template_readable(template_path: str) -> tuple[bool, str]:
    """Check if the template .docx file exists and is readable."""
    if not template_path:
        return False, "Template path is not set in the profile."
    if not os.path.exists(template_path):
        return False, f"Template file not found: {template_path}"
    if not os.access(template_path, os.R_OK):
        return False, f"Template file is not readable (permission denied): {template_path}"
    return True, ""


def check_folders_writable(output_folder: str, log_folder: str) -> tuple[bool, str]:
    """
    Ensure output and log directories exist and are writable.
    Creates them if they don't exist.
    """
    for folder in (output_folder, log_folder):
        try:
            os.makedirs(folder, exist_ok=True)
            # Test write by creating and removing a temp file
            test_file = os.path.join(folder, ".write_test")
            with open(test_file, "w") as f:
                f.write("test")
            os.unlink(test_file)
        except OSError as exc:
            return False, f"Cannot write to folder '{folder}': {exc}"
    return True, ""


# ── Full preflight run ───────────────────────────────────────────────────────

def run_preflight(
    config: dict,
    profile: dict,
    row_count: int,
    on_progress: Callable[[str], None] | None = None,
) -> list[dict]:
    """
    Run all preflight checks and return a list of result dicts.

    Args:
        config:       Full config dict (from ConfigManager.get_all()).
        profile:      Active profile dict.
        row_count:    Number of rows in the Excel batch.
        on_progress:  Optional callback(message) for UI status updates.

    Returns:
        List of dicts: [{"check": name, "ok": bool, "message": str}, ...]
    """
    results = []

    def _report(check_name: str, ok: bool, message: str) -> None:
        results.append({"check": check_name, "ok": ok, "message": message})
        if on_progress:
            status = "✅" if ok else "⚠️"
            on_progress(f"{status} {check_name}: {message}" if not ok else f"{status} {check_name}")

    # 1. Gmail auth
    if on_progress:
        on_progress("Checking Gmail credentials...")
    gmail = config.get("gmail", {})
    ok, msg = check_gmail_auth(gmail.get("sender_email", ""), gmail.get("app_password", ""))
    _report("Gmail Auth", ok, msg)

    # 2. Email capacity
    ok, msg = check_email_capacity(row_count, config.get("settings", {}).get("max_emails_per_day", 450))
    _report("Email Capacity", ok, msg)

    # 3. Template readable
    ok, msg = check_template_readable(profile.get("template_path", ""))
    _report("Template File", ok, msg)

    # 4. Folders writable
    settings = config.get("settings", {})
    ok, msg = check_folders_writable(
        settings.get("output_folder", "./output"),
        settings.get("log_folder", "./logs"),
    )
    _report("Output Folders", ok, msg)

    # 5. Google Drive quota (only if not in mock mode)
    drive_cfg = config.get("google_drive", {})
    if not drive_cfg.get("mock_mode", True):
        if on_progress:
            on_progress("Checking Google Drive quota...")
        ok, msg = check_drive_quota(
            drive_cfg.get("service_account_json_path", ""),
            drive_cfg.get("upload_folder_id", ""),
        )
        _report("Drive Quota", ok, msg)
    else:
        _report("Drive Quota", True, "Skipped (mock mode)")

    # 6. AiSensy reachability (only if not in mock mode)
    aisensy_cfg = config.get("aisensy", {})
    if not aisensy_cfg.get("mock_mode", True):
        if on_progress:
            on_progress("Checking AiSensy connectivity...")
        ok, msg = check_aisensy_reachability(aisensy_cfg.get("api_key", ""))
        _report("AiSensy API", ok, msg)
    else:
        _report("AiSensy API", True, "Skipped (mock mode)")

    return results
