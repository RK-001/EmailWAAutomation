"""
core/email_sender.py
--------------------
Send legal notice PDFs via Gmail SMTP (STARTTLS, App Password auth).

Design:
  - Uses smtplib (stdlib) — no third-party dependencies
  - Connects fresh per send (no persistent SMTP connection — avoids timeout issues)
  - Attaches PDF directly (MIMEMultipart/application)
  - Subject and body formatted using {PLACEHOLDER} syntax from profile
  - Enforces 5-second delay between sends (caller responsibility, but noted)
  - 500/day limit: preflight warns; this module does not enforce it

Gmail limits:
  - Personal Gmail: ~500 emails/day
  - App Password required (not regular password)
  - STARTTLS on port 587
"""

import os
import re
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from utils.ssl_compat import create_ssl_context


class EmailSender:
    """
    Send emails with PDF attachment via Gmail SMTP.

    Usage:
        sender = EmailSender(config["gmail"])
        ok, err = sender.send(
            to="recipient@example.com",
            subject="Notice for Ramesh Kumar",
            body="Dear Ramesh Kumar, ...",
            pdf_path="/path/to/notice.pdf",
        )
    """

    def __init__(self, gmail_config: dict):
        """
        Args:
            gmail_config: The "gmail" section of config.json.
                          Must contain: sender_email, app_password.
        """
        self._sender_email: str = gmail_config.get("sender_email", "")
        self._app_password: str = self._normalize_app_password(
            gmail_config.get("app_password", "")
        )

    def send(
        self,
        to: str,
        subject: str,
        body: str,
        pdf_path: str,
    ) -> tuple[bool, str]:
        """
        Send one email with a PDF attachment.

        Args:
            to:       Recipient email address.
            subject:  Email subject line.
            body:     Plain-text email body.
            pdf_path: Absolute path to the PDF file to attach.

        Returns:
            (True, "")       → sent successfully
            (False, message) → failed with error description
        """
        if not self._sender_email or not self._app_password:
            return False, "Gmail credentials not configured."
        if not to or "@" not in to:
            return False, f"Invalid recipient email: '{to}'"
        if not os.path.exists(pdf_path):
            return False, f"PDF attachment not found: {pdf_path}"

        try:
            msg = self._build_message(to, subject, body, pdf_path)
            self._smtp_send(msg, to)
            return True, ""
        except smtplib.SMTPAuthenticationError:
            return False, (
                "Gmail authentication failed. "
                "Verify your App Password in Setup tab."
            )
        except smtplib.SMTPRecipientsRefused:
            return False, f"Recipient refused by server: {to}"
        except smtplib.SMTPException as exc:
            return False, f"SMTP error: {exc}"
        except OSError as exc:
            return False, f"Network error: {exc}"

    def test_auth(self) -> tuple[bool, str]:
        """
        Test Gmail credentials without sending any email.

        Returns:
            (True, "")       → credentials valid
            (False, message) → invalid credentials or network error
        """
        if not self._sender_email or not self._app_password:
            return False, "Gmail email or app password is not configured."
        try:
            context = create_ssl_context()
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
                server.ehlo()
                server.starttls(context=context)
                server.login(self._sender_email, self._app_password)
            return True, ""
        except smtplib.SMTPAuthenticationError:
            return False, (
                "Authentication failed. Check your Gmail App Password.\n"
                "Make sure 2-Step Verification is enabled on your Google Account."
            )
        except (smtplib.SMTPException, OSError) as exc:
            return False, f"Connection error: {exc}"

    # ── Internal ─────────────────────────────────────────────────────────────

    def _build_message(self, to: str, subject: str, body: str, pdf_path: str) -> MIMEMultipart:
        """Construct the MIME email with PDF attachment."""
        msg = MIMEMultipart()
        msg["From"] = self._sender_email
        msg["To"] = to
        msg["Subject"] = subject

        # Plain text body
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # PDF attachment
        with open(pdf_path, "rb") as f:
            pdf_data = f.read()
        attachment = MIMEApplication(pdf_data, _subtype="pdf")
        attachment.add_header(
            "Content-Disposition",
            "attachment",
            filename=os.path.basename(pdf_path),
        )
        msg.attach(attachment)
        return msg

    def _smtp_send(self, msg: MIMEMultipart, to: str) -> None:
        """Open an SMTP connection and send the message."""
        context = create_ssl_context()
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(self._sender_email, self._app_password)
            server.sendmail(self._sender_email, to, msg.as_string())

    @staticmethod
    def _normalize_app_password(app_password: str) -> str:
        """
        Normalize a Gmail App Password entered by the user.

        Google often displays app passwords in 4 groups separated by spaces.
        SMTP login expects the raw 16-character value, so we remove all spaces.
        """
        return (app_password or "").strip().replace(" ", "")


def format_email_content(template_str: str, row: dict) -> str:
    """
    Format an email subject or body template with row data.
    Uses {FIELDNAME} substitution (safe — does not evaluate code).

    Args:
        template_str: String with {FIELDNAME} placeholders.
        row:          Data row dict with field values.

    Returns:
        Formatted string with placeholders replaced.
        Missing or blank placeholders become "NA".
    """
    field_re = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")

    def replacement(match: re.Match) -> str:
        value = row.get(match.group(1))
        if value is None:
            return "NA"
        value = str(value).strip()
        return value if value else "NA"

    return field_re.sub(replacement, template_str or "")
