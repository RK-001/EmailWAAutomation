"""
core/cloud_uploader.py
----------------------
Upload PDF files to Google Drive and return shareable "anyone with link" URLs.

Design:
  - Supports personal Google Drive via OAuth Desktop Client JSON + token.json
  - Keeps legacy service account JSON support for Workspace/shared-drive setups
  - UUID-based filenames prevent enumeration of uploaded files
  - Creates viewer-only "anyone with link" permission on each upload
  - Pre-flight quota check before batch upload
  - MOCK MODE: when no credentials configured, returns a fake URL for testing

Security note:
  "Anyone with link" sharing is acceptable for legal notices since:
  (a) URLs are UUID-based (unguessable), and
  (b) files are auto-deleted after 30 days.
  For higher security (v1.5+), restrict to recipient email only.
"""

import os
import uuid

from utils.ssl_compat import get_merged_ca_bundle_path

_DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
_MOCK_URL_PREFIX = "https://drive.google.com/mock/"
_AUTH_MODE_OAUTH = "oauth_user"
_AUTH_MODE_SERVICE_ACCOUNT = "service_account"


class DriveUploader:
    """
    Handles Google Drive uploads for one batch session.

    Usage:
        uploader = DriveUploader(config["google_drive"])
        link = uploader.upload_pdf(pdf_path, display_name="RameshKumar_Notice.pdf")
    """

    def __init__(self, drive_config: dict, allow_oauth_interactive: bool = False):
        """
        Args:
            drive_config: The "google_drive" section of config.json.
                          Must contain auth_mode, upload_folder_id, mock_mode, and
                          mode-specific credential paths.
            allow_oauth_interactive: True only for Setup's Authorize/Test button.
                                     Batch runs must never open a browser.
        """
        self._mock_mode: bool = drive_config.get("mock_mode", True)
        self._auth_mode: str = drive_config.get("auth_mode") or _AUTH_MODE_OAUTH
        self._folder_id: str = drive_config.get("upload_folder_id", "")
        self._creds_path: str = drive_config.get("service_account_json_path", "")
        self._oauth_client_path: str = drive_config.get("oauth_client_json_path", "")
        self._oauth_token_path: str = drive_config.get("oauth_token_json_path", "token.json")
        self._allow_oauth_interactive = allow_oauth_interactive
        self._service = None

        if not self._mock_mode:
            self._service = self._build_service()

    # ── Public API ────────────────────────────────────────────────────────────

    def upload_pdf(self, pdf_path: str, display_name: str | None = None) -> str:
        """
        Upload a PDF to Google Drive and return a shareable link.

        Args:
            pdf_path:     Absolute path to the PDF file.
            display_name: Optional human-readable filename on Drive.
                          Defaults to a UUID-based name for security.

        Returns:
            Shareable "view" URL string.

        Raises:
            FileNotFoundError: If pdf_path does not exist.
            RuntimeError:      On Drive API errors.
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found for upload: {pdf_path}")

        if self._mock_mode:
            return self._mock_upload(pdf_path)

        return self._real_upload(pdf_path, display_name)

    def check_quota(self) -> tuple[bool, str]:
        """
        Check available Google Drive storage.

        Returns:
            (True, "")       → sufficient space (> 500 MB free)
            (False, message) → low space warning
        """
        if self._mock_mode:
            return True, "Mock mode — quota check skipped."
        try:
            about = self._service.about().get(fields="storageQuota").execute()
            quota = about.get("storageQuota", {})
            limit = int(quota.get("limit", 0))
            used = int(quota.get("usage", 0))
            if limit == 0:
                return True, "Unlimited storage (Google Workspace)."
            free_mb = (limit - used) // (1024 * 1024)
            if free_mb < 500:
                return False, f"Only {free_mb} MB free on Google Drive. Consider cleanup."
            return True, f"{free_mb} MB free."
        except Exception as exc:
            return False, self._friendly_google_error(exc, "Could not check Drive quota")

    def test_folder_access(self) -> tuple[bool, str]:
        """
        Verify the configured folder exists and the signed-in account can add files.
        Does not upload a file.
        """
        if self._mock_mode:
            return True, "Mock mode - Drive folder check skipped."
        if not self._folder_id:
            return False, "Google Drive upload folder ID is not set."
        try:
            folder = self._service.files().get(
                fileId=self._folder_id,
                fields="id,name,mimeType,capabilities(canAddChildren)",
                supportsAllDrives=True,
            ).execute()
            if folder.get("mimeType") != "application/vnd.google-apps.folder":
                return False, "Configured Drive ID is not a folder."
            if not folder.get("capabilities", {}).get("canAddChildren", False):
                return False, (
                    "Signed-in Google account cannot upload to this folder. "
                    "Use a folder owned by this account or grant editor access."
                )
            return True, f"Drive folder ready: {folder.get('name', self._folder_id)}"
        except Exception as exc:
            return False, self._friendly_google_error(exc, "Could not access Drive folder")

    def delete_old_files(self, older_than_days: int = 30) -> int:
        """
        Delete files in the configured Drive folder older than N days.

        Returns:
            Count of files deleted.
        """
        if self._mock_mode:
            return 0
        try:
            from datetime import datetime, timedelta, timezone
            cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
            cutoff_str = cutoff.isoformat()

            query = (
                f"'{self._folder_id}' in parents "
                f"and createdTime < '{cutoff_str}' "
                f"and trashed = false"
            )
            resp = self._service.files().list(q=query, fields="files(id, name)").execute()
            files = resp.get("files", [])
            for file in files:
                self._service.files().delete(fileId=file["id"]).execute()
            return len(files)
        except Exception:
            return 0

    # ── Internal ─────────────────────────────────────────────────────────────

    def _build_service(self):
        """Build authenticated Google Drive service for the selected auth mode."""
        if self._auth_mode == _AUTH_MODE_SERVICE_ACCOUNT:
            return self._build_service_account_service()
        if self._auth_mode == _AUTH_MODE_OAUTH:
            return self._build_oauth_service()
        raise ValueError(f"Unsupported Google Drive auth mode: {self._auth_mode}")

    def _build_service_account_service(self):
        """Build authenticated Google Drive service with a service account JSON."""
        from google.oauth2 import service_account

        if not os.path.exists(self._creds_path):
            raise FileNotFoundError(
                f"Drive credentials not found: {self._creds_path}\n"
                "Please set up a Google Service Account and place the JSON key file at the configured path."
            )
        creds = service_account.Credentials.from_service_account_file(
            self._creds_path,
            scopes=_DRIVE_SCOPES,
        )
        return self._build_service_from_credentials(creds)

    def _build_oauth_service(self):
        """Build authenticated Google Drive service with a saved user OAuth token."""
        from google.auth.exceptions import RefreshError
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        creds = None
        if self._oauth_token_path and os.path.exists(self._oauth_token_path):
            creds = Credentials.from_authorized_user_file(
                self._oauth_token_path,
                _DRIVE_SCOPES,
            )

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self._save_oauth_token(creds)
            except RefreshError as exc:
                creds = None
                if not self._allow_oauth_interactive:
                    raise RuntimeError(
                        "Google Drive OAuth token expired and could not be refreshed. "
                        "Open Setup and run Authorize / Test Drive again."
                    ) from exc

        if not creds or not creds.valid:
            if not self._allow_oauth_interactive:
                raise RuntimeError(
                    "Google Drive OAuth is not authorized on this machine. "
                    "Open Setup and run Authorize / Test Drive once before generating a batch."
                )
            creds = self._run_oauth_authorization()

        return self._build_service_from_credentials(creds)

    def _run_oauth_authorization(self):
        """Open browser OAuth consent and save token.json for future runs."""
        from google_auth_oauthlib.flow import InstalledAppFlow

        if not self._oauth_client_path or not os.path.exists(self._oauth_client_path):
            raise FileNotFoundError(
                f"OAuth client JSON not found: {self._oauth_client_path}\n"
                "Create a Google Cloud OAuth Desktop Client JSON and select it in Setup."
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            self._oauth_client_path,
            _DRIVE_SCOPES,
        )
        creds = flow.run_local_server(port=0)
        self._save_oauth_token(creds)
        return creds

    def _save_oauth_token(self, creds) -> None:
        """Persist OAuth token JSON beside the app/config."""
        token_dir = os.path.dirname(os.path.abspath(self._oauth_token_path))
        if token_dir:
            os.makedirs(token_dir, exist_ok=True)
        with open(self._oauth_token_path, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())

    @staticmethod
    def _build_service_from_credentials(creds):
        """Build Drive API client with project CA bundle compatibility."""
        from googleapiclient.discovery import build
        import google_auth_httplib2
        import httplib2

        ca_bundle = get_merged_ca_bundle_path()
        http = (
            httplib2.Http(ca_certs=ca_bundle, timeout=30)
            if ca_bundle
            else httplib2.Http(timeout=30)
        )
        authed_http = google_auth_httplib2.AuthorizedHttp(creds, http=http)
        return build(
            "drive",
            "v3",
            http=authed_http,
            cache_discovery=False,
            static_discovery=False,
        )

    def _real_upload(self, pdf_path: str, display_name: str | None) -> str:
        """Upload PDF to Drive with UUID filename and create shareable link."""
        from googleapiclient.http import MediaFileUpload

        try:
            # UUID-based filename for unguessability
            drive_filename = f"{uuid.uuid4().hex}.pdf"

            file_metadata = {
                "name": drive_filename,
                "parents": [self._folder_id],
            }
            media = MediaFileUpload(pdf_path, mimetype="application/pdf", resumable=False)

            uploaded = self._service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id",
                supportsAllDrives=True,
            ).execute()

            file_id = uploaded["id"]

            # Create "anyone with link" viewer permission
            self._service.permissions().create(
                fileId=file_id,
                body={"type": "anyone", "role": "reader"},
                supportsAllDrives=True,
            ).execute()

            return f"https://drive.google.com/file/d/{file_id}/view"
        except Exception as exc:
            raise RuntimeError(self._friendly_google_error(exc, "Google Drive upload failed")) from exc

    def _mock_upload(self, pdf_path: str) -> str:
        """Return a fake Drive URL for testing (no actual upload)."""
        mock_id = uuid.uuid4().hex
        filename = os.path.basename(pdf_path)
        return f"{_MOCK_URL_PREFIX}{mock_id}/{filename}"

    @staticmethod
    def _friendly_google_error(exc: Exception, prefix: str) -> str:
        """
        Return a short user-facing message for common Google Drive failures.
        """
        text = str(exc)
        lower = text.lower()

        if (
            "zscaler" in lower
            or "restricted based on" in lower
            or ("google drive" in lower and "not allowed" in lower)
        ):
            return (
                f"{prefix}: Google Drive is blocked by your office/network security policy "
                "(Zscaler). Use a network where Drive is allowed, ask IT to whitelist "
                "Google Drive / Drive API, or turn Drive mock mode ON for testing."
            )

        if "not found" in lower or "404" in lower:
            return f"{prefix}: Drive folder/file was not found. Check the folder ID and signed-in Google account."

        if "forbidden" in lower or "403" in lower:
            return f"{prefix}: Access to Google Drive API was denied. Check network policy, folder sharing, and service-account permissions."

        if "ssl" in lower or "certificate" in lower:
            return f"{prefix}: SSL certificate validation failed while connecting to Google Drive."

        if "timed out" in lower or "winerror 10060" in lower:
            return f"{prefix}: Google Drive API connection timed out. Check internet/proxy/firewall access."

        return f"{prefix}: {text}"
