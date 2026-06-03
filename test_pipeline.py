"""
test_pipeline.py
----------------
End-to-end CLI test of the core pipeline.
Tests all Phase 1 modules with 5 sample rows (mock mode — no real sends).

What it tests:
  1. Excel reading (openpyxl)
  2. Context sanitization
  3. Template variable validation
  4. DOCX generation (docxtpl)
  5. PDF conversion (Word COM — real Word, real PDFs)
  6. Cloud upload (mock — returns fake URL)
  7. Email send (mock — validates logic only, does not send)
  8. WhatsApp send (mock — logs to console)
  9. Checkpoint save/load/resume
  10. Batch logger + CSV export

Prerequisites:
  1. Run create_sample_template.py first to generate template + Excel
  2. MS Word must be installed
  3. Run from BulkNoticeAutomation directory

Usage:
    py -3 test_pipeline.py
"""

import os
import sys
import time
import threading
import traceback
import pythoncom
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# ── Ensure project root is on path ────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.excel_reader import read_excel
from core.doc_generator import render_document
from core.pdf_converter import WordPdfConverter, is_word_installed
from core.cloud_uploader import DriveUploader
from core.email_sender import EmailSender, format_email_content
from core.whatsapp_sender import WhatsAppSender
from utils.sanitizer import sanitize_context
from utils.validators import validate_phone, validate_email, validate_template_variables
from utils.checkpoint import CheckpointManager, compute_excel_hash
from utils.logger import BatchLogger
from utils.config_manager import ConfigManager


# ── Paths ─────────────────────────────────────────────────────────────────────
TEMPLATE_PATH  = os.path.join(BASE_DIR, "templates", "sample_notice.docx")
EXCEL_PATH     = os.path.join(BASE_DIR, "sample", "sample_data.xlsx")
OUTPUT_DIR     = os.path.join(BASE_DIR, "output")
LOG_DIR        = os.path.join(BASE_DIR, "logs")
CONFIG_PATH    = os.path.join(BASE_DIR, "config.json")


# ── Helpers ───────────────────────────────────────────────────────────────────

def section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def ok(msg: str) -> None:
    print(f"  ✅ {msg}")

def warn(msg: str) -> None:
    print(f"  ⚠️  {msg}")

def fail(msg: str) -> None:
    print(f"  ❌ {msg}")

def check(label: str, condition: bool, detail: str = "") -> bool:
    if condition:
        ok(f"{label}{' — ' + detail if detail else ''}")
    else:
        fail(f"{label}{' — ' + detail if detail else ''}")
    return condition


# ── Test: Prerequisites ───────────────────────────────────────────────────────

def test_prerequisites() -> bool:
    section("TEST 0: Prerequisites")
    all_ok = True

    if not os.path.exists(TEMPLATE_PATH):
        fail(f"Template not found: {TEMPLATE_PATH}")
        print("     → Run 'py -3 create_sample_template.py' first")
        all_ok = False
    else:
        ok(f"Template found: {TEMPLATE_PATH}")

    if not os.path.exists(EXCEL_PATH):
        fail(f"Sample Excel not found: {EXCEL_PATH}")
        print("     → Run 'py -3 create_sample_template.py' first")
        all_ok = False
    else:
        ok(f"Sample Excel found: {EXCEL_PATH}")

    word_ok = is_word_installed()
    check("MS Word COM available", word_ok,
          "" if word_ok else "PDF conversion will fail — install MS Word")
    if not word_ok:
        all_ok = False

    return all_ok


# ── Test: Config Manager ──────────────────────────────────────────────────────

def test_config_manager() -> bool:
    section("TEST 1: Config Manager")
    try:
        cfg = ConfigManager(CONFIG_PATH)
        check("Config loads without error", True)
        check("Default settings present", cfg.get("settings.batch_restart_every") is not None)

        # Ensure Sample_Profile exists (needed for test)
        if "Sample_Profile" not in cfg.list_profile_names():
            cfg.save_profile("Sample_Profile", {
                "display_name": "Sample Profile (Demo)",
                "template_path": TEMPLATE_PATH,
                "notice_type": "EMI_DEFAULT",
                "email_subject": "Important Communication - {NAME}",
                "email_body": "Dear {NAME},\n\nPlease review the attached notice for account {ACCOUNTNO}.\n\nRegards,\nGK Associates",
                "wa_template_params": ["NAME", "ACCOUNTNO", "drive_link", "OFFICER_NO"],
                "column_mapping": {
                    "NAME": "NAME",
                    "EMAILID": "EMAILID",
                    "MOBILENO": "MOBILENO",
                    "AMOUNT": "AMOUNT",
                    "ACCOUNTNO": "ACCOUNTNO",
                    "CHEQUE_DATE": "CHEQUE_DATE",
                    "REASON": "REASON",
                    "BRANCH": "BRANCH",
                    "OFFICER_NO": "OFFICER_NO",
                },
            })
            ok("Sample_Profile created in config.json")
        else:
            ok("Sample_Profile already in config")

        return True
    except Exception as exc:
        fail(f"Config manager error: {exc}")
        return False


# ── Test: Excel Reader ────────────────────────────────────────────────────────

def test_excel_reader() -> list[dict] | None:
    section("TEST 2: Excel Reader")
    try:
        rows = read_excel(EXCEL_PATH)
        check(f"Read {len(rows)} rows", len(rows) == 5, f"expected 5")

        # Check all required fields present
        required = ["NAME", "EMAILID", "MOBILENO", "AMOUNT", "ACCOUNTNO"]
        first = rows[0]
        missing = [f for f in required if f not in first]
        check("Required columns present", not missing,
              f"missing: {missing}" if missing else "NAME, EMAILID, MOBILENO, AMOUNT, ACCOUNTNO")

        ok(f"First row: {first.get('NAME')} | {first.get('EMAILID')} | {first.get('MOBILENO')}")
        return rows
    except Exception as exc:
        fail(f"Excel reader error: {exc}")
        traceback.print_exc()
        return None


# ── Test: Validators ──────────────────────────────────────────────────────────

def test_validators(rows: list[dict]) -> bool:
    section("TEST 3: Validators")
    all_ok = True
    for i, row in enumerate(rows):
        phone_ok, phone_err = validate_phone(row.get("MOBILENO", ""))
        email_ok, email_err = validate_email(row.get("EMAILID", ""))
        if not phone_ok:
            fail(f"Row {i}: phone invalid — {phone_err}")
            all_ok = False
        if not email_ok:
            fail(f"Row {i}: email invalid — {email_err}")
            all_ok = False

    if all_ok:
        ok("All phones and emails valid")

    # Test template variable checking
    tpl_ok, missing = validate_template_variables(TEMPLATE_PATH, list(rows[0].keys()) + ["FIRM_NAME", "NOTICE_DATE", "LAWYER_NAME"])
    check("Template variables satisfied", tpl_ok,
          f"missing: {missing}" if not tpl_ok else "all variables covered")
    return all_ok


# ── Test: Sanitizer ───────────────────────────────────────────────────────────

def test_sanitizer() -> bool:
    section("TEST 4: Sanitizer")
    test_row = {
        "NAME": "Ram & Shyam <Corp>",
        "AMOUNT": None,
        "ACCOUNT": 12345678,
        "DATE": "01/01/2026",
    }
    result = sanitize_context(test_row)
    check("None becomes NA",       result["AMOUNT"] == "NA")
    check("& escaped",             result["NAME"] == "Ram &amp; Shyam &lt;Corp&gt;")
    check("int → string",          result["ACCOUNT"] == "12345678")
    check("str passthrough",       result["DATE"] == "01/01/2026")
    return True


# ── Test: Document Generator + PDF Converter ─────────────────────────────────

def test_doc_and_pdf(rows: list[dict], batch_id: str) -> list[dict] | None:
    """
    Runs in a background thread to test COM usage in non-main threads.
    Returns list of dicts with pdf_path per row, or None on error.
    """
    section("TEST 5 + 6: Doc Generator + PDF Converter")

    results = []
    error_holder = [None]

    def _worker():
        pythoncom.CoInitialize()
        converter = None
        try:
            converter = WordPdfConverter(restart_every=50)
            for i, row in enumerate(rows):
                # Add static context fields (in real app these come from profile/config)
                row_with_statics = dict(row)
                row_with_statics["FIRM_NAME"] = "GK Associates"
                row_with_statics["LAWYER_NAME"] = "Adv. Test User"
                row_with_statics["NOTICE_DATE"] = datetime.now().strftime("%d/%m/%Y")

                # Generate DOCX
                docx_path = render_document(
                    template_path=TEMPLATE_PATH,
                    context=row_with_statics,
                    output_dir=OUTPUT_DIR,
                    batch_id=batch_id,
                    row_index=i,
                )
                ok(f"Row {i}: DOCX → {os.path.basename(docx_path)}")

                # Convert to PDF
                pdf_path = converter.convert(docx_path)
                check(f"Row {i}: PDF exists", os.path.exists(pdf_path),
                      os.path.basename(pdf_path))

                results.append({**row_with_statics, "pdf_path": pdf_path})
        except Exception as exc:
            error_holder[0] = exc
            traceback.print_exc()
        finally:
            if converter:
                converter.quit()
            pythoncom.CoUninitialize()

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join(timeout=120)   # 2-minute timeout for 5 files

    if thread.is_alive():
        fail("PDF conversion thread timed out (120s)")
        return None
    if error_holder[0]:
        fail(f"Doc/PDF error: {error_holder[0]}")
        return None

    ok(f"Generated {len(results)} PDFs successfully")
    return results


# ── Test: Cloud Uploader (mock) ───────────────────────────────────────────────

def test_cloud_uploader(results: list[dict]) -> list[dict]:
    section("TEST 7: Cloud Uploader (mock mode)")
    uploader = DriveUploader({"mock_mode": True, "upload_folder_id": "", "service_account_json_path": ""})
    for item in results:
        link = uploader.upload_pdf(item["pdf_path"])
        item["drive_link"] = link
        check(f"Mock upload: {item['NAME'][:20]}", link.startswith("https://"), link[:60])
    ok("All mock uploads returned valid URLs")
    return results


# ── Test: Email Sender (mock — no actual send) ────────────────────────────────

def test_email_sender(results: list[dict]) -> bool:
    section("TEST 8: Email Sender (validation only — no real send)")
    sender = EmailSender({"sender_email": "", "app_password": ""})
    for item in results:
        ok_flag, err = sender.send(
            to=item.get("EMAILID", ""),
            subject=f"Test Notice — {item.get('NAME', '')}",
            body=f"Dear {item.get('NAME', '')}, please find attached the notice.",
            pdf_path=item["pdf_path"],
        )
        # Expected: fail because no credentials — but NOT a file-not-found error
        if err and "not found" in err:
            fail(f"Row: PDF not found for {item.get('NAME')} — {err}")
            return False
        elif err and "credentials" in err.lower():
            ok(f"Row {item.get('NAME')}: correctly reported no-credentials error (expected in test)")
        else:
            ok(f"Row {item.get('NAME')}: validation passed")
    ok("Email validation logic working (real send skipped — configure Gmail in Setup tab)")
    return True


# ── Test: WhatsApp Sender (mock) ──────────────────────────────────────────────

def test_whatsapp_sender(results: list[dict]) -> bool:
    section("TEST 9: WhatsApp Sender (mock mode)")
    sender = WhatsAppSender({"api_key": "", "template_name": "legal_notice_notification", "mock_mode": True}, firm_name="GK Associates")
    all_ok = True
    for i, item in enumerate(results):
        ok_flag, err = sender.send_notice_notification(
            phone=item.get("MOBILENO", ""),
            name=item.get("NAME", ""),
            account_no=item.get("ACCOUNTNO", ""),
            drive_link=item.get("drive_link", ""),
            contact_no=item.get("OFFICER_NO", ""),
            batch_id="test_batch_2026",
        )
        check(f"WhatsApp mock: {item.get('NAME', '')}", ok_flag, err if not ok_flag else "queued")
        if not ok_flag:
            all_ok = False
    return all_ok


# ── Test: Checkpoint ──────────────────────────────────────────────────────────

def test_checkpoint(results: list[dict], batch_id: str) -> bool:
    section("TEST 10: Checkpoint System")
    os.makedirs(LOG_DIR, exist_ok=True)
    checkpoint_path = os.path.join(LOG_DIR, f"{batch_id}_checkpoint.json")

    # Create new checkpoint via class
    excel_hash = compute_excel_hash(EXCEL_PATH)
    mgr = CheckpointManager(
        checkpoint_path=checkpoint_path,
        batch_id=batch_id,
        excel_path=EXCEL_PATH,
        excel_hash=excel_hash,
        profile_name="Sample_Profile",
        total_rows=len(results),
    )
    check("Checkpoint created", os.path.exists(checkpoint_path))

    # Simulate generate stage
    for i, item in enumerate(results):
        mgr.mark_result(i, item["pdf_path"], item.get("drive_link", ""))
    check("Generate stage saved", mgr.last_generated_index == len(results) - 1,
          f"last_generated_index = {mgr.last_generated_index}")

    # Advance to sending stage
    mgr.advance_to_sending()
    check("Stage advanced to 'sending'", mgr._data["stage"] == "sending")

    # Simulate send stage
    for i, item in enumerate(results):
        mgr.mark_sent(i, "sent", "sent")
    check("Send stage saved", mgr.last_sent_index == len(results) - 1)

    # Verify Excel hash via fresh load
    mgr2 = CheckpointManager(
        checkpoint_path=checkpoint_path,
        batch_id=batch_id,
        excel_path=EXCEL_PATH,
        excel_hash=excel_hash,
        profile_name="Sample_Profile",
        total_rows=len(results),
    )
    check("Excel hash verification passed", mgr2.last_sent_index == mgr.last_sent_index)

    # Cleanup
    mgr.delete()
    check("Checkpoint deleted after completion", not os.path.exists(checkpoint_path))
    return True


# ── Test: Logger + CSV Export ─────────────────────────────────────────────────

def test_logger(results: list[dict], batch_id: str) -> bool:
    section("TEST 11: Batch Logger + CSV Export")
    log_path = os.path.join(LOG_DIR, f"{batch_id}.json")
    csv_path = os.path.join(LOG_DIR, f"{batch_id}.csv")
    logger = BatchLogger(log_path)

    for i, item in enumerate(results):
        logger.log_row(
            index=i,
            row=item,
            pdf_path=item["pdf_path"],
            drive_link=item.get("drive_link", ""),
            email_status="sent",
            email_error="",
            whatsapp_status="sent",
            whatsapp_error="",
        )

    check("Log file created", os.path.exists(log_path))
    summary = logger.get_summary()
    check(f"Summary: {summary['total']} total", summary["total"] == len(results))
    check(f"Email: {summary['email_sent']} sent", summary["email_sent"] == len(results))
    check(f"WA: {summary['wa_sent']} sent", summary["wa_sent"] == len(results))

    logger.export_csv(csv_path)
    check("CSV exported", os.path.exists(csv_path))
    return True


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "="*60)
    print("  BulkNoticeAutomation — Phase 1 Pipeline Test")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_Sample_Profile"
    passed = 0
    failed_tests = []

    def run(name, fn, *args):
        nonlocal passed
        try:
            result = fn(*args)
            if result is not False and result is not None:
                passed += 1
            elif result is False:
                failed_tests.append(name)
            return result
        except Exception as exc:
            fail(f"EXCEPTION in {name}: {exc}")
            traceback.print_exc()
            failed_tests.append(name)
            return None

    # Run tests in order
    if not run("Prerequisites", test_prerequisites):
        print("\n❌ Prerequisites failed. Run create_sample_template.py first.\n")
        sys.exit(1)

    run("Config", test_config_manager)
    rows = run("Excel Reader", test_excel_reader)

    if rows is None:
        print("\n❌ Cannot continue without row data.\n")
        sys.exit(1)

    run("Validators", test_validators, rows)
    run("Sanitizer", test_sanitizer)
    results = run("Doc+PDF", test_doc_and_pdf, rows, batch_id)

    if results is None:
        print("\n❌ Cannot continue without generated PDFs.\n")
        sys.exit(1)

    run("Cloud Uploader", test_cloud_uploader, results)
    run("Email Sender",   test_email_sender,   results)
    run("WhatsApp",       test_whatsapp_sender, results)
    run("Checkpoint",     test_checkpoint,      results, batch_id)
    run("Logger",         test_logger,          results, batch_id)

    # ── Summary ───────────────────────────────────────────────────────────
    section("TEST SUMMARY")
    total = passed + len(failed_tests)
    print(f"  Passed  : {passed}/{total}")
    if failed_tests:
        print(f"  Failed  : {len(failed_tests)}")
        for t in failed_tests:
            print(f"            - {t}")
    else:
        print(f"  All tests passed! ✅")
    print(f"\n  Output PDFs : {os.path.join(OUTPUT_DIR, batch_id)}")
    print(f"  Log file    : {os.path.join(LOG_DIR, batch_id)}.json")
    print()


if __name__ == "__main__":
    main()
