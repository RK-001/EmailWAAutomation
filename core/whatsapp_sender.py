"""
core/whatsapp_sender.py
-----------------------
Send WhatsApp notifications via Meta WhatsApp Business Cloud API.

Meta WhatsApp Business Cloud API:
  - Direct integration with Meta (no third-party dependency)
  - Template-based messaging (templates must be pre-approved in Meta Business Manager)
  - Link sent as text in body (not as document attachment)
  - No monthly platform fees (pay-per-message pricing only)

Approved template (must match what is registered in Meta Business Manager):
  HEADER: TEXT type (e.g., "Legal Communication") - static, no variables
  BODY: "Dear {{1}}, an important communication regarding your account {{2}} has been
         shared with you. Please review: {{3}}. For queries: {{4}}."

Template variables (all in body):
  {{1}} → Recipient name (e.g., "Ramesh Kumar")
  {{2}} → Account number
  {{3}} → Google Drive shareable link (PDF)
  {{4}} → Officer/contact phone number

MOCK MODE: When access_token is empty or mock_mode=True, logs the message
           without making any API call. Used during development.

Meta API reference:
  POST https://graph.facebook.com/{api_version}/{phone_number_id}/messages
  Auth: Bearer {access_token}
"""

import json
import ssl
import urllib.error
import urllib.request

from utils.ssl_compat import create_ssl_context


_REQUEST_TIMEOUT_SEC = 15


class WhatsAppSender:
    """
    Send WhatsApp template messages via Meta WhatsApp Business Cloud API.

    Usage:
        sender = WhatsAppSender(config["meta_whatsapp"], firm_name="GK Associates")
        ok, err = sender.send_notice_notification(
            phone="9876543210",
            name="Ramesh Kumar",
            account_no="ACC123456",
            drive_link="https://drive.google.com/...",
            contact_no="8830575674",
            batch_id="2026-06-01_HDFC",
        )
    """

    def __init__(self, meta_whatsapp_config: dict, firm_name: str = ""):
        """
        Args:
            meta_whatsapp_config: The "meta_whatsapp" section of config.json.
            firm_name:            Firm name (informational only, not used in Meta API).
        """
        self._phone_number_id: str = meta_whatsapp_config.get("phone_number_id", "")
        self._access_token: str = meta_whatsapp_config.get("access_token", "")
        self._template_name: str = meta_whatsapp_config.get("template_name", "")
        self._api_version: str = meta_whatsapp_config.get("api_version", "v21.0")
        self._template_language: str = meta_whatsapp_config.get("template_language", "en")
        self._mock_mode: bool = meta_whatsapp_config.get("mock_mode", True) or not self._access_token
        self._firm_name: str = firm_name or "Law Firm"
        
        # Build API URL
        self._api_url = f"https://graph.facebook.com/{self._api_version}/{self._phone_number_id}/messages"

    # ── Public API ────────────────────────────────────────────────────────────

    def send_notice_notification(
        self,
        phone: str,
        name: str,
        account_no: str,
        drive_link: str,
        contact_no: str,
        batch_id: str,
        template_params: list[str] | None = None,
    ) -> tuple[bool, str]:
        """
        Send the pre-approved Meta WhatsApp template with link in body.

        Template (registered in Meta Business Manager):
          HEADER: TEXT (static, e.g., "Legal Communication")
          BODY: "Dear {{1}}, an important communication regarding your account {{2}} has been
                 shared with you. Please review: {{3}}. For queries: {{4}}."

        Args:
            phone:       10-digit Indian mobile number (no prefix).
            name:        Recipient name ({{1}}).
            account_no:  Account/case number ({{2}}).
            drive_link:  Google Drive PDF URL ({{3}}) - sent as text in body.
            contact_no:  Contact phone for queries ({{4}}).
            batch_id:    Used for logging/tracking (not sent to Meta API).

        Returns:
            (True, "")       → message queued successfully
            (False, message) → API error with description
        """
        # Normalize phone: must be E.164 with "+" for Meta (+91XXXXXXXXXX)
        phone_e164 = self._normalize_phone(phone)
        resolved_template_params = template_params or [name, account_no, drive_link, contact_no]
        if not resolved_template_params:
            return False, "WhatsApp template params are empty."

        if self._mock_mode:
            return self._mock_send(
                phone_e164,
                name,
                account_no,
                drive_link,
                contact_no,
                batch_id,
                template_params=resolved_template_params,
            )

        return self._api_send(
            phone=phone_e164,
            template_params=resolved_template_params,
        )

    # ── Internal ─────────────────────────────────────────────────────────────

    def _api_send(
        self,
        phone: str,
        template_params: list[str],
    ) -> tuple[bool, str]:
        """Make the actual Meta WhatsApp Cloud API call."""
        # Build Meta API payload
        # Template has TEXT header (static, no params) and BODY with {{1}}, {{2}}, {{3}}, {{4}}
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "template",
            "template": {
                "name": self._template_name,
                "language": {"code": self._template_language},
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": str(param)}
                            for param in template_params
                        ]
                    }
                ]
            }
        }
        
        try:
            req = urllib.request.Request(
                self._api_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._access_token}",
                },
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
            return False, "Meta API request timed out."
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, ssl.SSLError) or "certificate" in str(reason).lower():
                return False, f"Meta API SSL error: {reason}"
            return False, f"Cannot reach Meta API: {reason}"
        except ssl.SSLError as exc:
            return False, f"Meta API SSL error: {exc}"
        except Exception as exc:
            if "certificate" in str(exc).lower():
                return False, f"Meta API SSL error: {exc}"
            return False, f"Meta API request error: {exc}"

        # Parse response
        if status_code in (200, 201):
            try:
                data = json.loads(raw_body) if raw_body else {}
                # Meta returns {"messages": [{"id": "wamid.xxx"}]} on success
                if "messages" in data and data["messages"]:
                    msg_id = data["messages"][0].get("id", "")
                    return True, f"Message ID: {msg_id}" if msg_id else ""
                # Success but unexpected format
                return True, ""
            except Exception:
                # Response not JSON but status OK
                return True, ""

        # Error response
        try:
            err_data = json.loads(raw_body) if raw_body else {}
            # Meta error format: {"error": {"message": "...", "type": "...", "code": ...}}
            if "error" in err_data:
                error_obj = err_data["error"]
                error_msg = error_obj.get("message", "")
                error_type = error_obj.get("type", "")
                error_code = error_obj.get("code", "")
                msg = f"Meta error: {error_msg}"
                if error_type:
                    msg += f" (type: {error_type})"
                if error_code:
                    msg += f" (code: {error_code})"
                return False, msg
            # Fallback
            error_msg = err_data.get("message") or raw_body[:200]
        except Exception:
            error_msg = raw_body[:200] if raw_body else f"HTTP {status_code}"

        return False, f"Meta API returned {status_code}: {error_msg}"

    def _mock_send(
        self,
        phone: str,
        name: str,
        account_no: str,
        drive_link: str,
        contact_no: str,
        batch_id: str,
        template_params: list[str] | None = None,
    ) -> tuple[bool, str]:
        """Simulate a send in mock mode — no real API call."""
        # In mock mode, just validate that all required params are non-empty
        if not phone:
            return False, "Phone number is empty."
        if not name:
            return False, "Recipient name is empty."
        resolved_template_params = template_params or [name, account_no, drive_link, contact_no]
        if not resolved_template_params:
            return False, "WhatsApp template params are empty."
        # Log what would have been sent (visible in test output / log tab)
        print(
            f"[MOCK Meta WhatsApp] To: {phone} | Template: {self._template_name or '<unset>'} "
            f"| Params: {resolved_template_params} | Batch: {batch_id}"
        )
        return True, ""

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """
        Convert phone to Meta E.164 format: +91XXXXXXXXXX.
        Accepts: 9876543210 | +919876543210 | 919876543210 | 09876543210
        """
        p = phone.strip().replace(" ", "").replace("-", "")
        # Remove existing prefix if present
        if p.startswith("+91"):
            p = p[3:]
        elif p.startswith("91") and len(p) == 12:
            p = p[2:]
        elif p.startswith("0") and len(p) == 11:
            p = p[1:]  # Remove leading 0 (common in Indian numbers)
        # Return as +91 + 10-digit number (Meta requires + prefix)
        if len(p) == 10:
            return "+91" + p
        # If already formatted or invalid length, return as-is with + prefix
        return "+" + p if not p.startswith("+") else p
