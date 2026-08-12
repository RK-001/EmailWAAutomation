"""
utils/preflight.py
------------------
Pre-batch validation checks run before any PDF generation or sending starts.
Identifies problems early so the user doesn't discover failures mid-batch.

Checks:
  1. Gmail SMTP authentication (live connection test)
  2. Row count vs Gmail 500/day limit (warns at > max_emails_per_day)
  3. Google Drive quota (warns if < 500 MB free) — skipped in mock mode
  4. Meta WhatsApp API credentials validation — skipped in mock mode
  5. Template file exists and is readable
  6. Output and log folders are writable
"""

import json
import os
import smtplib
import ssl
import tempfile
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


def check_drive_ready(
    drive_config: dict,
    allow_oauth_interactive: bool = False,
) -> tuple[bool, str]:
    """
    Build the configured Drive uploader and verify quota + folder access.

    OAuth browser authorization is allowed only when explicitly requested from
    Setup. Batch/preflight calls should pass the default False.
    """
    try:
        from core.cloud_uploader import DriveUploader

        uploader = DriveUploader(
            drive_config,
            allow_oauth_interactive=allow_oauth_interactive,
        )
        quota_ok, quota_msg = uploader.check_quota()
        folder_ok, folder_msg = uploader.test_folder_access()
        if not quota_ok:
            return False, quota_msg
        if not folder_ok:
            return False, folder_msg
        return True, folder_msg or quota_msg or "Google Drive ready."
    except Exception as exc:
        return False, str(exc)


def check_s3_ready(s3_config: dict) -> tuple[bool, str]:
    """Build S3 uploader and verify configured bucket access."""
    try:
        from core.cloud_uploader import S3Uploader

        uploader = S3Uploader(s3_config)
        ok, msg = uploader.test_bucket_access()
        if not ok:
            return False, msg
        return True, msg or "Amazon S3 ready."
    except Exception as exc:
        return False, str(exc)


# ── Meta WhatsApp preflight ──────────────────────────────────────────────────

def check_meta_whatsapp_connection(
    phone_number_id: str,
    access_token: str,
    api_version: str = "v21.0",
    disable_ssl_verify: bool = False
) -> tuple[bool, str]:
    """
    Validate Meta WhatsApp Business API credentials.
    Tests connectivity and token validity by querying the phone number info.

    Args:
        phone_number_id:   Meta WhatsApp Business Phone Number ID
        access_token:      Meta WhatsApp Business API access token
        api_version:       Meta Graph API version (default: v21.0)
        disable_ssl_verify: Disable SSL verification for corporate proxies

    Returns:
        (True, "")       → API credentials valid
        (False, message) → connection error or invalid credentials
    """
    if not phone_number_id:
        return False, "Meta Phone Number ID is not configured."
    if not access_token:
        return False, "Meta Access Token is not configured."
    
    try:
        # Query phone number info endpoint to validate credentials
        # This is a lightweight GET request that doesn't send messages
        api_url = (
            f"https://graph.facebook.com/{api_version}/{phone_number_id}"
            "?fields=id,verified_name,display_phone_number"
        )
        
        req = urllib.request.Request(
            api_url,
            method="GET",
        )
        req.add_header("Authorization", f"Bearer {access_token}")
        
        ctx = create_ssl_context(disable_verify=disable_ssl_verify)
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            status_code = getattr(resp, "status", 200)
            raw_body = resp.read().decode("utf-8", errors="replace")
        
        if status_code == 200:
            # Parse response to verify it's valid
            try:
                data = json.loads(raw_body) if raw_body else {}
                if "id" in data or "verified_name" in data:
                    return True, ""
                return False, "Meta API returned unexpected response format."
            except Exception:
                return False, "Meta API returned unreadable response."
        
        return False, f"Meta API returned status {status_code}"
        
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        try:
            raw_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            err_data = json.loads(raw_body) if raw_body else {}
            error_msg = err_data.get("error", {}).get("message", "") or str(exc)
        except Exception:
            error_msg = str(exc)
        
        if status_code == 401:
            return False, "Invalid Meta Access Token. Please check your token."
        elif status_code == 403:
            return False, (
                "Meta token does not have permission to access this phone number. "
                "Check that the system user is assigned to the WhatsApp account and "
                "has whatsapp_business_management / whatsapp_business_messaging."
            )
        elif status_code == 404:
            return False, "Invalid Phone Number ID or WhatsApp Business account not found."
        return False, f"Meta API error ({status_code}): {error_msg}"
    
    except TimeoutError:
        return False, "Meta API connection timed out."
    except ssl.SSLError as exc:
        return False, f"Meta API SSL error: {exc}"
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        return False, f"Cannot reach Meta API: {reason}"
    except Exception as exc:
        return False, f"Meta API connectivity error: {exc}"


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
        test_file = ""
        try:
            os.makedirs(folder, exist_ok=True)
            fd, test_file = tempfile.mkstemp(prefix=".write_test_", dir=folder)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write("test")
        except OSError as exc:
            return False, f"Cannot write to folder '{folder}': {exc}"
        finally:
            if test_file and os.path.exists(test_file):
                try:
                    os.unlink(test_file)
                except OSError:
                    pass
    return True, ""
