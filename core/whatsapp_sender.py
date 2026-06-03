"""
core/whatsapp_sender.py
-----------------------
Send WhatsApp notifications via AiSensy BSP (official Meta Business Solution Partner).

Why AiSensy?
  - Official Meta partner → no ban risk from unofficial automation
  - Pre-approved template system → works with Meta content policy
  - API simpler than Meta Cloud API direct (no webhook setup needed)
  - ₹999/month platform + ~₹0.50-0.70/message (utility category)

Approved template (must match what is registered on AiSensy dashboard):
  "Dear {{1}}, an important communication regarding your account {{2}} has been
   shared with you. Please review: {{3}}. For queries: {{4}}. — [Firm Name]"

Template variables:
  {{1}} → Recipient name (e.g., "Ramesh Kumar")
  {{2}} → Account number
  {{3}} → Google Drive shareable link (PDF)
  {{4}} → Officer/contact phone number

MOCK MODE: When api_key is empty or mock_mode=True, logs the message
           without making any API call. Used during development.

AiSensy API reference:
  POST https://backend.aisensy.com/campaign/t1/api/v2
"""

import json
import ssl
import urllib.error
import urllib.request

from utils.ssl_compat import create_ssl_context


_AISENSY_API_URL = "https://backend.aisensy.com/campaign/t1/api/v2"
_REQUEST_TIMEOUT_SEC = 15


class WhatsAppSender:
    """
    Send WhatsApp template messages via AiSensy API.

    Usage:
        sender = WhatsAppSender(config["aisensy"], firm_name="GK Associates")
        ok, err = sender.send_notice_notification(
            phone="9876543210",
            name="Ramesh Kumar",
            account_no="ACC123456",
            drive_link="https://drive.google.com/...",
            contact_no="8830575674",
            batch_id="2026-06-01_HDFC",
        )
    """

    def __init__(self, aisensy_config: dict, firm_name: str = ""):
        """
        Args:
            aisensy_config: The "aisensy" section of config.json.
            firm_name:      Firm name shown in campaign label (informational only).
        """
        self._api_key: str = aisensy_config.get("api_key", "")
        self._template_name: str = aisensy_config.get("template_name", "legal_notice_notification")
        self._mock_mode: bool = aisensy_config.get("mock_mode", True) or not self._api_key
        self._firm_name: str = firm_name or "Law Firm"

    # ── Public API ────────────────────────────────────────────────────────────

    def send_notice_notification(
        self,
        phone: str,
        name: str,
        account_no: str,
        drive_link: str,
        contact_no: str,
        batch_id: str,
    ) -> tuple[bool, str]:
        """
        Send the pre-approved AiSensy notice notification template.

        Template (registered on AiSensy):
          "Dear {{1}}, an important communication regarding your account {{2}} has been
           shared with you. Please review: {{3}}. For queries: {{4}}."

        Args:
            phone:       10-digit Indian mobile number (no prefix).
            name:        Recipient name ({{1}}).
            account_no:  Account/case number ({{2}}).
            drive_link:  Google Drive PDF URL ({{3}}).
            contact_no:  Contact phone for queries ({{4}}).
            batch_id:    Used as campaign name for tracking on AiSensy dashboard.

        Returns:
            (True, "")       → message queued successfully
            (False, message) → API error with description
        """
        # Normalize phone: must be E.164 without "+" for AiSensy (91XXXXXXXXXX)
        phone_e164 = self._normalize_phone(phone)

        if self._mock_mode:
            return self._mock_send(phone_e164, name, account_no, drive_link, contact_no, batch_id)

        return self._api_send(
            phone=phone_e164,
            campaign_name=batch_id[:50],        # AiSensy campaign name limit
            template_params=[name, account_no, drive_link, contact_no],
        )

    # ── Internal ─────────────────────────────────────────────────────────────

    def _api_send(
        self,
        phone: str,
        campaign_name: str,
        template_params: list[str],
    ) -> tuple[bool, str]:
        """Make the actual AiSensy API call."""
        payload = {
            "apiKey": self._api_key,
            "campaignName": campaign_name,
            "destination": phone,
            "userName": self._firm_name,
            "templateParams": template_params,
        }
        try:
            req = urllib.request.Request(
                _AISENSY_API_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            ctx = create_ssl_context()
            with urllib.request.urlopen(req, context=ctx, timeout=_REQUEST_TIMEOUT_SEC) as response:
                status_code = getattr(response, "status", 200)
                raw_body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            status_code = exc.code
            raw_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        except TimeoutError:
            return False, "AiSensy API request timed out."
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, ssl.SSLError) or "certificate" in str(reason).lower():
                return False, f"AiSensy SSL error: {reason}"
            return False, f"Cannot reach AiSensy API: {reason}"
        except ssl.SSLError as exc:
            return False, f"AiSensy SSL error: {exc}"
        except Exception as exc:
            if "certificate" in str(exc).lower():
                return False, f"AiSensy SSL error: {exc}"
            return False, f"AiSensy request error: {exc}"

        # Parse response
        if status_code == 200:
            if not raw_body:
                return True, ""
            try:
                data = json.loads(raw_body)
            except Exception:
                return False, f"AiSensy returned HTTP 200 with an unreadable response: {raw_body[:200]}"
            # AiSensy returns {"status": "success"} or similar
            if data.get("status") in ("success", "SUCCESS", "200"):
                return True, ""
            error_msg = data.get("message") or data.get("error") or str(data)
            return False, f"AiSensy error: {error_msg}"

        # Non-200 response
        try:
            err_data = json.loads(raw_body) if raw_body else {}
            error_msg = err_data.get("message") or err_data.get("error") or raw_body[:200]
        except Exception:
            error_msg = raw_body[:200] if raw_body else f"HTTP {status_code}"

        return False, f"AiSensy API returned {status_code}: {error_msg}"

    def _mock_send(
        self,
        phone: str,
        name: str,
        account_no: str,
        drive_link: str,
        contact_no: str,
        batch_id: str,
    ) -> tuple[bool, str]:
        """Simulate a send in mock mode — no real API call."""
        # In mock mode, just validate that all required params are non-empty
        if not phone:
            return False, "Phone number is empty."
        if not name:
            return False, "Recipient name is empty."
        # Log what would have been sent (visible in test output / log tab)
        print(
            f"[MOCK WhatsApp] To: {phone} | Name: {name} | Account: {account_no} "
            f"| Link: {drive_link} | Contact: {contact_no} | Batch: {batch_id}"
        )
        return True, ""

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """
        Convert phone to AiSensy E.164 format: 91XXXXXXXXXX.
        Accepts: 9876543210 | +919876543210 | 919876543210
        """
        p = phone.strip().replace(" ", "").replace("-", "")
        if p.startswith("+91"):
            p = p[3:]
        elif p.startswith("91") and len(p) == 12:
            p = p[2:]
        # Return as 91 + 10-digit number
        return "91" + p if len(p) == 10 else p
