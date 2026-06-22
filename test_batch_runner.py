#!/usr/bin/env python3
"""
test_batch_runner.py
--------------------
Focused integration smoke tests for BatchRunner orchestration.

What it covers:
  1. Public BatchRunner generate -> send flow using start_generate/start_send.
  2. Profile-level WhatsApp template overrides and wa_template_params ordering.
  3. Early validation gate for invalid live Meta WhatsApp config.

Uses lightweight monkeypatches for external boundaries so the test exercises the
threading, queue, config, and orchestration code without depending on Word,
Drive, Gmail, or the real Meta API.
"""

import json
import os
import queue
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import core.batch_runner as batch_runner_module
from core.batch_runner import BatchRunner
from utils.config_manager import ConfigManager


def section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def ok(msg: str) -> None:
    print(f"  PASS {msg}")


def fail(msg: str) -> None:
    print(f"  FAIL {msg}")


def check(label: str, condition: bool, detail: str = "") -> bool:
    if condition:
        ok(f"{label}{' - ' + detail if detail else ''}")
    else:
        fail(f"{label}{' - ' + detail if detail else ''}")
    return condition


def _base_rows() -> list[dict]:
    return [
        {
            "NAME": "Alice Sharma",
            "EMAILID": "alice@example.com",
            "MOBILENO": "9876543210",
            "ACCOUNTNO": "ACC001",
            "AMOUNT": "1500",
            "CHEQUE_DATE": "01/06/2026",
            "REASON": "EMI overdue",
            "BRANCH": "Pune",
            "OFFICER_NO": "9988776655",
        },
        {
            "NAME": "Bharat Mehta",
            "EMAILID": "bharat@example.com",
            "MOBILENO": "9123456789",
            "ACCOUNTNO": "ACC002",
            "AMOUNT": "2750",
            "CHEQUE_DATE": "02/06/2026",
            "REASON": "Cheque bounce",
            "BRANCH": "Mumbai",
            "OFFICER_NO": "8877665544",
        },
    ]


def _create_temp_config(
    temp_dir: str,
    *,
    meta_overrides: dict | None = None,
    profile_overrides: dict | None = None,
) -> tuple[str, str, str, str, list[dict]]:
    template_path = os.path.join(temp_dir, "template.docx")
    excel_path = os.path.join(temp_dir, "sample.xlsx")
    output_dir = os.path.join(temp_dir, "output")
    log_dir = os.path.join(temp_dir, "logs")
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)
    Path(template_path).write_text("placeholder template", encoding="utf-8")
    Path(excel_path).write_text("placeholder excel", encoding="utf-8")

    rows = _base_rows()
    profile = {
        "display_name": "Batch Runner Smoke",
        "template_path": template_path,
        "notice_type": "EMI_DEFAULT",
        "email_subject": "Notice - {NAME}",
        "email_body": "Dear {NAME}",
        "wa_template_params": ["ACCOUNTNO", "NAME", "drive_link", "OFFICER_NO"],
        "column_mapping": {
            "NAME": "NAME",
            "EMAILID": "EMAILID",
            "MOBILENO": "MOBILENO",
            "ACCOUNTNO": "ACCOUNTNO",
            "AMOUNT": "AMOUNT",
            "CHEQUE_DATE": "CHEQUE_DATE",
            "REASON": "REASON",
            "BRANCH": "BRANCH",
            "OFFICER_NO": "OFFICER_NO",
        },
        "required_fields": ["NAME"],
    }
    if profile_overrides:
        profile.update(profile_overrides)

    config = {
        "gmail": {
            "sender_email": "",
            "app_password": "",
        },
        "meta_whatsapp": {
            "phone_number_id": "123456789",
            "access_token": "token",
            "template_name": "global_template",
            "api_version": "v21.0",
            "template_language": "en",
            "mock_mode": True,
        },
        "google_drive": {
            "auth_mode": "oauth_user",
            "oauth_client_json_path": "oauth_credentials.json",
            "oauth_token_json_path": "token.json",
            "service_account_json_path": "drive_credentials.json",
            "upload_folder_id": "folder-id",
            "auto_delete_days": 30,
            "mock_mode": True,
        },
        "profiles": {
            "Smoke_Profile": profile,
        },
        "settings": {
            "output_folder": output_dir,
            "log_folder": log_dir,
            "batch_restart_every": 50,
            "send_delay_min_sec": 0,
            "send_delay_max_sec": 0,
            "max_emails_per_day": 450,
            "drive_cleanup_enabled": False,
            "lawyer_name": "Test Lawyer",
            "firm_name": "Test Firm",
        },
    }
    if meta_overrides:
        config["meta_whatsapp"].update(meta_overrides)

    config_path = os.path.join(temp_dir, "config.json")
    with open(config_path, "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)

    return config_path, excel_path, output_dir, log_dir, rows


def _drain_until(q: queue.Queue, terminal_type: str, timeout_sec: float = 20.0) -> list[dict]:
    deadline = time.time() + timeout_sec
    messages: list[dict] = []
    while time.time() < deadline:
        try:
            while True:
                message = q.get_nowait()
                messages.append(message)
                if message.get("type") in {terminal_type, "error"}:
                    return messages
        except queue.Empty:
            time.sleep(0.05)
    raise TimeoutError(f"Timed out waiting for queue message '{terminal_type}'")


def _patch_batch_runner(rows: list[dict], send_handler):
    originals = {
        "read_excel": batch_runner_module.read_excel,
        "render_document": batch_runner_module.render_document,
        "WordPdfConverter": batch_runner_module.WordPdfConverter,
        "DriveUploader": batch_runner_module.DriveUploader,
        "EmailSender": batch_runner_module.EmailSender,
        "check_email_capacity": batch_runner_module.check_email_capacity,
        "check_template_readable": batch_runner_module.check_template_readable,
        "is_word_installed": batch_runner_module.is_word_installed,
        "send_notice_notification": batch_runner_module.WhatsAppSender.send_notice_notification,
    }

    def fake_read_excel(_excel_path: str, column_mapping=None, required_fields=None):
        return [dict(row) for row in rows]

    def fake_render_document(template_path: str, context: dict, output_dir: str, batch_id: str, row_index: int):
        docx_path = os.path.join(output_dir, f"{batch_id}_{row_index}.docx")
        Path(docx_path).write_text(context.get("NAME", "row"), encoding="utf-8")
        return docx_path

    class FakeWordPdfConverter:
        def __init__(self, restart_every: int = 50):
            self.restart_every = restart_every

        def convert(self, docx_path: str) -> str:
            pdf_path = os.path.splitext(docx_path)[0] + ".pdf"
            Path(pdf_path).write_text(f"PDF for {os.path.basename(docx_path)}", encoding="utf-8")
            return pdf_path

        def quit(self) -> None:
            return None

    class FakeDriveUploader:
        def __init__(self, drive_config: dict):
            self.drive_config = drive_config

        def upload_pdf(self, pdf_path: str) -> str:
            return f"https://drive.test/{os.path.basename(pdf_path)}"

        def delete_old_files(self, older_than_days: int) -> None:
            return None

    class FakeEmailSender:
        def __init__(self, gmail_config: dict):
            self.gmail_config = gmail_config

        def send(self, to: str, subject: str, body: str, pdf_path: str) -> tuple[bool, str]:
            return True, ""

    batch_runner_module.read_excel = fake_read_excel
    batch_runner_module.render_document = fake_render_document
    batch_runner_module.WordPdfConverter = FakeWordPdfConverter
    batch_runner_module.DriveUploader = FakeDriveUploader
    batch_runner_module.EmailSender = FakeEmailSender
    batch_runner_module.check_email_capacity = lambda row_count, max_emails: (True, "")
    batch_runner_module.check_template_readable = lambda template_path: (True, "")
    batch_runner_module.is_word_installed = lambda: True
    batch_runner_module.WhatsAppSender.send_notice_notification = send_handler
    return originals


def _restore_batch_runner(originals: dict) -> None:
    batch_runner_module.read_excel = originals["read_excel"]
    batch_runner_module.render_document = originals["render_document"]
    batch_runner_module.WordPdfConverter = originals["WordPdfConverter"]
    batch_runner_module.DriveUploader = originals["DriveUploader"]
    batch_runner_module.EmailSender = originals["EmailSender"]
    batch_runner_module.check_email_capacity = originals["check_email_capacity"]
    batch_runner_module.check_template_readable = originals["check_template_readable"]
    batch_runner_module.is_word_installed = originals["is_word_installed"]
    batch_runner_module.WhatsAppSender.send_notice_notification = originals["send_notice_notification"]


def test_batch_runner_happy_path() -> bool:
    section("TEST 1: BatchRunner public flow")
    temp_dir = tempfile.mkdtemp(prefix="batch_runner_smoke_")
    captured_calls: list[dict] = []

    def fake_send_notice(self, phone, name, account_no, drive_link, contact_no, batch_id, template_params=None):
        captured_calls.append(
            {
                "template_name": getattr(self, "_template_name", ""),
                "template_language": getattr(self, "_template_language", ""),
                "template_params": list(template_params or []),
            }
        )
        return True, ""

    try:
        config_path, excel_path, output_dir, log_dir, rows = _create_temp_config(
            temp_dir,
            meta_overrides={
                "mock_mode": False,
                "template_name": "",
            },
            profile_overrides={
                "wa_template_name": "profile_specific_tpl",
                "wa_template_language": "en_US",
            },
        )
        originals = _patch_batch_runner(rows, fake_send_notice)
        try:
            progress_queue: queue.Queue = queue.Queue()
            runner = BatchRunner(ConfigManager(config_path), progress_queue)
            runner.start_generate(
                excel_path=excel_path,
                profile_name="Smoke_Profile",
                output_dir=output_dir,
                log_dir=log_dir,
            )
            generate_messages = _drain_until(progress_queue, "stage_complete")
            terminal = generate_messages[-1]
            if terminal.get("type") != "stage_complete":
                detail = terminal.get("message", "unknown generate failure")
                return check("Generation completed", False, detail)

            generated_rows = terminal.get("summary", {}).get("generated", [])
            if not check("Generated rows returned", len(generated_rows) == len(rows), str(len(generated_rows))):
                return False
            if not check(
                "All PDFs generated",
                all(os.path.exists(item.get("pdf_path", "")) for item in generated_rows),
            ):
                return False

            runner.start_send(
                approved_rows=generated_rows,
                notice_type="EMI_DEFAULT",
                send_email=False,
                send_whatsapp=True,
            )
            send_messages = _drain_until(progress_queue, "complete")
            send_terminal = send_messages[-1]
            if send_terminal.get("type") != "complete":
                detail = send_terminal.get("message", "unknown send failure")
                return check("Send completed", False, detail)

            row_done = [m for m in send_messages if m.get("type") == "row_done"]
            if not check("All rows emitted row_done", len(row_done) == len(rows), str(len(row_done))):
                return False
            if not check(
                "All WhatsApp sends marked sent",
                all(m.get("row", {}).get("wa_status") == "sent" for m in row_done),
            ):
                return False
            if not check("Captured WhatsApp calls", len(captured_calls) == len(rows), str(len(captured_calls))):
                return False

            expected = [
                [row["ACCOUNTNO"], row["NAME"], f"https://drive.test/{send_row['row'].get('pdf_path', '').split(os.sep)[-1]}", row["OFFICER_NO"]]
                for row, send_row in zip(rows, row_done)
            ]
            actual = [call["template_params"] for call in captured_calls]
            if not check("Profile param order honored", actual == expected, f"actual={actual}"):
                return False
            if not check(
                "Profile template override honored",
                all(call["template_name"] == "profile_specific_tpl" for call in captured_calls),
            ):
                return False
            if not check(
                "Profile language override honored",
                all(call["template_language"] == "en_US" for call in captured_calls),
            ):
                return False

            return True
        finally:
            _restore_batch_runner(originals)
    except Exception as exc:
        fail(f"Unexpected exception: {exc}")
        traceback.print_exc()
        return False
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_batch_runner_live_meta_validation() -> bool:
    section("TEST 2: Live Meta validation gate")
    temp_dir = tempfile.mkdtemp(prefix="batch_runner_live_gate_")

    def should_not_send(self, phone, name, account_no, drive_link, contact_no, batch_id, template_params=None):
        raise AssertionError("send_notice_notification should not be called for invalid live config")

    try:
        config_path, excel_path, output_dir, log_dir, rows = _create_temp_config(
            temp_dir,
            meta_overrides={
                "mock_mode": False,
                "template_name": "",
            },
            profile_overrides={
                "wa_template_params": ["NAME", "ACCOUNTNO", "drive_link", "OFFICER_NO"],
            },
        )
        originals = _patch_batch_runner(rows, should_not_send)
        try:
            progress_queue: queue.Queue = queue.Queue()
            runner = BatchRunner(ConfigManager(config_path), progress_queue)
            runner.start_generate(
                excel_path=excel_path,
                profile_name="Smoke_Profile",
                output_dir=output_dir,
                log_dir=log_dir,
            )
            generate_messages = _drain_until(progress_queue, "stage_complete")
            terminal = generate_messages[-1]
            if terminal.get("type") != "stage_complete":
                detail = terminal.get("message", "unknown generate failure")
                return check("Generation completed", False, detail)

            generated_rows = terminal.get("summary", {}).get("generated", [])
            runner.start_send(
                approved_rows=generated_rows,
                notice_type="EMI_DEFAULT",
                send_email=False,
                send_whatsapp=True,
            )
            send_messages = _drain_until(progress_queue, "complete")
            send_terminal = send_messages[-1]
            expected_error = "template name is not set"
            return check(
                "Invalid live Meta config blocked before send",
                send_terminal.get("type") == "error"
                and expected_error in send_terminal.get("message", "").lower(),
                send_terminal.get("message", ""),
            )
        finally:
            _restore_batch_runner(originals)
    except Exception as exc:
        fail(f"Unexpected exception: {exc}")
        traceback.print_exc()
        return False
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main() -> int:
    print("\n" + "=" * 60)
    print("  BatchRunner Smoke Test")
    print("=" * 60)

    tests = [
        ("BatchRunner public flow", test_batch_runner_happy_path),
        ("Live Meta validation gate", test_batch_runner_live_meta_validation),
    ]

    failures: list[str] = []
    for name, test_fn in tests:
        try:
            if not test_fn():
                failures.append(name)
        except Exception as exc:
            fail(f"EXCEPTION in {name}: {exc}")
            traceback.print_exc()
            failures.append(name)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    if failures:
        for name in failures:
            fail(name)
        print(f"\nTotal: {len(tests) - len(failures)}/{len(tests)} passed")
        return 1

    for name, _ in tests:
        ok(name)
    print(f"\nTotal: {len(tests)}/{len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())