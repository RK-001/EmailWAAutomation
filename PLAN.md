# Law Firm Bulk Notice Automation — Project Plan

**Version:** 2.0 (Post Pre-Mortem Review)  
**Date:** 2026-05-31  
**Status:** Approved for Development — With Mitigations  
**Business Model:** Open-source + Paid Services

---
curl -X GET "https://graph.facebook.com/v21.0/wamid.HBgMOTE5ODIzODAzMzgxFQIAERgSOEVFNUE2RkMwQ0FCRDZGREFCAA==" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
  
## 1. Problem Statement

A law firm handles multiple bank/financial clients. For each case batch:
1. Client sends an Excel file (customer details, bounce amounts, reasons, branch info, email, phone)
2. Firm fills a Word notice template manually (mail merge)
3. Firm emails the notice PDF to each customer
4. Firm sends WhatsApp notification with PDF access link to each customer

This is done repeatedly across multiple clients, each with different templates.  
**Goal:** Automate steps 1–4 entirely. Single `.exe` app the lawyer runs — no Python or technical knowledge required. **Two-stage workflow:** Generate all PDFs → Preview/Verify → Send one-by-one with delivery proof.

---

## 2. Solution Overview

A desktop Python application packaged as a **single `.exe` file** with:
- Modern GUI (CustomTkinter, DPI-aware, dark/light modes)
- **Multiple client profiles** (one per bank/client, each with its own template & settings)
- **Two-stage workflow:** Generate all (Excel → Word → PDF → Google Drive upload) → Preview/Verify → Send (Email + WhatsApp, one-by-one with 3-5 sec delay)
- **Pause/Resume support:** Checkpoint-based state preservation (Excel hash + per-channel status)
- **Proof of delivery:** Logs all email/WhatsApp statuses per recipient
- Real-time progress, batch analytics, selective retry for failed channels

**Monthly cost to law firm:** ~₹1,100-4,500 (AiSensy ₹999 platform + ~₹0.50-0.70/message WhatsApp; Email + Drive storage free)

---

## 3. Tech Stack (v2.0 — Mitigated)

| Component | Library/Tool | Version | Notes |
|-----------|-------------|---------|-------|
| **GUI** | `customtkinter` | 5.2.2 | Modern UI, dark/light mode, DPI-aware (SetProcessDpiAwareness) |
| **Excel** | `openpyxl` | 3.1+ | Pure Python, handles dates, None values |
| **Template** | `docxtpl` | 0.20.2 | Jinja2 in Word, with XML sanitization (escape `<>&`) |
| **PDF** | **`pywin32` (win32com)** | 306+ | **Direct Word COM (not docx2pdf)** — batch-restart every 50 files; prevents hang |
| **PDF preview** | **`os.startfile()`** | stdlib | System default viewer (no AGPL licensing risk) |
| **Cloud upload** | `google-api-python-client` | 2.x | Drive API; check storage quota; shareable links |
| **Email** | `smtplib` + `email.mime` | stdlib | Gmail SMTP, pre-flight auth check, 500/day limit warning |
| **WhatsApp** | `requests` → AiSensy API | — | **BSP (official Meta partner)** — 2,400 msgs/min, template pre-approved |
| **Logging** | JSON (atomic writes) | — | Checkpoint + per-recipient status; Excel hash verification |
| **Package** | `PyInstaller` | 6.x | Single .exe; requires hidden imports + data collection |

---

## 4. WhatsApp Template Strategy (CRITICAL)

**Key Insight:** Meta blocks "legal notice", "court", "demand", "seize" language. Solution: **neutral notification template**.

❌ **REJECTED by Meta:**
```
"Legal notice for account {{1}}, amount Rs.{{2}}. Pay immediately or face legal action."
```

✅ **APPROVED by Meta (Utility category):**
```
"Dear {{1}}, an important communication regarding your account {{2}} has been shared with you. 
Please review: {{3}}. For queries: {{4}}. — GK Associates, Pune"
```

**How it works:**
- WhatsApp message is NEUTRAL (notification only)
- Actual legal notice content is in PDF (Google Drive link in message)
- Passes Meta review + avoids spam complaints
- Template must be pre-approved on AiSensy dashboard (typically 24-48 hrs)

---

## 5. Multiple Client Profiles & Config

Each client (bank) has its own profile stored in `config.json`:

```json
{
  "gmail": {
    "sender_email": "lawfirm@gmail.com",
    "app_password": "xxxx xxxx xxxx xxxx"
  },
  "aisensy": {
    "api_key": "YOUR_AISENSY_API_KEY",
    "template_name": "legal_notice_notification"
  },
  "google_drive": {
    "service_account_json_path": "drive_credentials.json",
    "upload_folder_id": "1ABC...xyz",
    "auto_delete_days": 30
  },
  "profiles": {
    "HDFC_LokAdalat": {
      "template_path": "templates/hdfc_lok_adalat.docx",
      "email_subject": "Important Communication - {NAME}",
      "email_body": "Dear {NAME},\nPlease find attached an important communication regarding your account {ACCOUNTNO}.\nFor any queries, contact us.",
      "wa_template_params": ["NAME", "ACCOUNTNO", "drive_link", "OFFICER_NO"],
      "column_mapping": {
        "NAME": "NAME",
        "EMAILID": "EMAILID",
        "MOBILENO": "MOBILENO",
        "AMOUNT": "AMT",
        "ACCOUNTNO": "ACCOUNT NO",
        "OFFICER_NO": "OFFICER NO"
      }
    }
  },
  "settings": {
    "output_folder": "./output",
    "log_folder": "./logs",
    "batch_restart_every": 50,
    "send_delay_min_sec": 3,
    "send_delay_max_sec": 5,
    "max_emails_per_day": 450,
    "drive_cleanup_enabled": true
  }
}
```

---

## 6. Application Structure

```
BulkNoticeAutomation/
│
├── main.py                     # Entry point — DPI aware, launches GUI
│
├── ui/
│   ├── app.py                  # Main CTkwindow, tab manager
│   ├── setup_tab.py            # Gmail + AiSensy API config + test buttons
│   ├── profiles_tab.py         # Create/edit/delete client profiles
│   ├── workflow_tab.py         # File pickers + "Generate All" button
│   ├── preview_tab.py          # Table view of generated items + approve/exclude
│   └── log_tab.py              # Results table, export CSV, retry failed
│
├── core/
│   ├── excel_reader.py         # openpyxl: read Excel → dict list + None handling
│   ├── doc_generator.py        # docxtpl: fill template + XML escaping + validate placeholders
│   ├── pdf_converter.py        # win32com direct: batch-restart every 50 files, DisplayAlerts=0
│   ├── cloud_uploader.py       # Google Drive: upload PDF, create shareable link, check quota
│   ├── email_sender.py         # Gmail SMTP + MIMEMultipart + 500/day check
│   └── whatsapp_sender.py      # AiSensy API: send_template() + error handling
│
├── utils/
│   ├── config_manager.py       # Load/save config.json + validation + corruption recovery
│   ├── checkpoint.py           # Atomic JSON writes + Excel hash verification + resume logic
│   ├── preflight.py            # Gmail auth test, AiSensy balance (?), row count warning
│   ├── validators.py           # Phone (10-digit), email, template variable checking
│   ├── logger.py               # Structured logging: per-recipient status + aggregates
│   └── sanitizer.py            # Escape XML chars (<>&), handle None values
│
├── templates/                  # Word template files (.docx)
│   ├── hdfc_bounce_notice.docx
│   └── sbi_notice.docx
│
├── output/                     # Generated PDFs (auto-created)
├── logs/                       # Batch logs as CSV (auto-created)
├── config.json                 # All settings + profiles
└── requirements.txt
```

---

## 6. GUI Design

### Tab 1 — Setup (one-time, per machine)

```
┌─────────────────────────────────────────────────────┐
│  ⚙  Setup                                           │
├─────────────────────────────────────────────────────┤
│  GMAIL SETTINGS                                     │
│  Email:        [lawfirm@gmail.com              ]    │
│  App Password: [•••• •••• •••• ••••            ]    │
│  (?) How to get App Password                        │
│  [  Test Connection  ]     ✅ Gmail: Connected      │
├─────────────────────────────────────────────────────┤
│  WHATSAPP SETTINGS (Meta Cloud API)                 │
│  Phone Number ID:   [123456789012345          ]     │
│  Access Token:      [••••••••••••••••••••••     ]     │
│  (?) How to get Meta API credentials                │
│  [  Test WhatsApp  ]       ✅ WhatsApp: Connected   │
├─────────────────────────────────────────────────────┤
│  [  Save Settings  ]                               │
└─────────────────────────────────────────────────────┘
```

### Tab 2 — Profiles (manage client templates)

```
┌─────────────────────────────────────────────────────┐
│  👥  Client Profiles                                │
├─────────────────────────────────────────────────────┤
│  Profiles:  [HDFC Bank ▼]  [+ New]  [✏ Edit]  [🗑] │
├─────────────────────────────────────────────────────┤
│  Profile Name:       [HDFC Bank                ]    │
│  Word Template:      [Browse...]  hdfc_bounce.docx   │
│  Email Subject:      [Legal Notice - {customer_name}]│
│  Email Body File:    [Browse...]  hdfc_email_body.txt│
├─────────────────────────────────────────────────────┤
│  COLUMN MAPPING (from Excel to template)            │
│  {{ customer_name }}  → [ Customer Name   ▼ ]       │
│  {{ email }}          → [ Email ID        ▼ ]       │
│  {{ phone }}          → [ Mobile No       ▼ ]       │
│  {{ bounce_amount }}  → [ Cheque Amount   ▼ ]       │
│  {{ reason }}         → [ Return Reason   ▼ ]       │
│  {{ branch }}         → [ Branch Name     ▼ ]       │
├─────────────────────────────────────────────────────┤
│  [  Save Profile  ]                                 │
└─────────────────────────────────────────────────────┘
```

### Tab 3 — Workflow (daily use)

```
┌─────────────────────────────────────────────────────┐
│  📄  Send Notices                                   │
├─────────────────────────────────────────────────────┤
│  Client Profile:  [HDFC Bank ▼]                     │
│  Excel File:      [Browse...]   hdfc_march_batch.xlsx│
│                                                     │
│  ┌─── Preview (first 5 rows) ─────────────────┐    │
│  │ Name       | Email       | Phone  | Amount  │    │
│  │ Ramesh K.  | r@mail.com  | 98765  | 50,000  │    │
│  │ Sunita P.  | s@mail.com  | 87654  | 25,000  │    │
│  └────────────────────────────────────────────┘    │
│                                                     │
│  ☑ Generate PDF    ☑ Send Email    ☑ Send WhatsApp  │
│                                                     │
│  [         START (120 rows)          ]              │
│                                                     │
│  ████████████████░░░░░░░░░  67/120                  │
│  ⏳ Sending WhatsApp to Ramesh Kumar...             │
└─────────────────────────────────────────────────────┘
```

### Tab 4 — Logs

```
┌─────────────────────────────────────────────────────┐
│  📋  Logs — HDFC Bank — 2026-05-28                  │
├─────────────────────────────────────────────────────┤
│  [All ▼]  [Export CSV]  [Retry Failed]              │
├────────────┬────────┬───────────┬──────────────────┤
│ Name       │ Email  │ WhatsApp  │ Time             │
├────────────┼────────┼───────────┼──────────────────┤
│ Ramesh K.  │ ✅     │ ✅        │ 10:32:15         │
│ Sunita P.  │ ✅     │ ❌ Failed │ 10:32:19         │
│ Ajay M.    │ ✅     │ ✅        │ 10:32:25         │
└────────────┴────────┴───────────┴──────────────────┘
│ Total: 120 | Email: 119✅ 1❌ | WA: 117✅ 3❌     │
└─────────────────────────────────────────────────────┘
```

---

## 7. Core Pipeline Logic

```python
def run_batch(profile, excel_path, send_email=True, send_whatsapp=True):
    rows = excel_reader.read(excel_path, profile.column_mapping)

    for i, row in enumerate(rows):
        # 1. Generate Word document
        docx_path = doc_generator.render(
            template=profile.template_path,
            data=row,
            output_dir="output"
        )

        # 2. Convert to PDF (uses MS Word COM)
        pdf_path = pdf_converter.convert(docx_path)

        # 3. Send Email
        if send_email:
            email_status = email_sender.send(
                to=row["email"],
                subject=profile.email_subject.format(**row),
                body_file=profile.email_body,
                attachment=pdf_path
            )

        # 4. Send WhatsApp (short text notification via official Meta Cloud API)
        if send_whatsapp:
            wa_status = whatsapp_sender.send_text(
                phone=row["phone"],
                message=profile.whatsapp_template.format(**row)
                # Example: "Notice sent to email. Amount: ₹{bounce_amount}. Contact: {officer_no}"
            )
            # Text only — no PDF attachment, no media upload needed

        # 5. Log
        logger.log_row(row, email_status, wa_status)

        # 6. Update GUI progress
        update_progress(i + 1, len(rows))
```

---

## 8. Word Template Format

The lawyer creates the Word notice as usual, then adds Jinja2 placeholders:

```
LEGAL NOTICE

To,
{{ customer_name }}

This is to inform you that cheque of Rs. {{ bounce_amount }} dated 
{{ cheque_date }} drawn on {{ branch }} has been returned/dishonoured 
due to "{{ reason }}".

You are hereby called upon to pay the above amount within 30 days.

For {{ firm_name }}
```

The **column mapping** in the profile tells the app which Excel column feeds each `{{ variable }}`.

---

## 9. Core Pipeline (v2.0 — Two-Stage: Generate → Preview → Send)

```python
import time, hashlib, threading, pythoncom

def run_batch_full(profile, excel_path, config):
    """Generate → Preview → Send with pause/resume support."""
    
    # STAGE 0: PRE-FLIGHT CHECKS
    preflight.check_gmail_auth(config.gmail)
    preflight.check_rows_vs_gmail_limit(len(rows))
    
    # STAGE 1: GENERATE ALL (with COM restart every 50)
    rows = excel_reader.read(excel_path, profile.column_mapping)
    excel_hash = hashlib.sha256(open(excel_path, 'rb').read()).hexdigest()
    generated = []
    
    word_app = init_word_com()
    for i, row in enumerate(rows):
        if i > 0 and i % config.settings.batch_restart_every == 0:
            word_app.Quit()
            pythoncom.CoUninitialize()
            time.sleep(1)
            pythoncom.CoInitialize()
            word_app = init_word_com()
        
        # Sanitize context (None → '', escape XML chars)
        row = sanitizer.sanitize_context(row)
        
        docx_path = doc_generator.render(profile.template_path, row)
        pdf_path = pdf_converter.convert(word_app, docx_path)
        drive_link = cloud_uploader.upload(pdf_path)
        
        generated.append({**row, "pdf_path": pdf_path, "drive_link": drive_link})
        ui.update_progress(i+1, len(rows), "Generating")
    
    word_app.Quit()
    pythoncom.CoUninitialize()
    
    # STAGE 2: PREVIEW (user approves/excludes)
    ui.show_preview_tab(generated)
    approved = ui.get_approved_rows()  # User clicks checkboxes
    
    # STAGE 3: SEND ONE-BY-ONE (with pause/resume)
    checkpoint = checkpoint_mgr.load_or_create(excel_hash, len(approved))
    
    for i in range(checkpoint.last_sent_index, len(approved)):
        if ui.pause_requested():
            checkpoint_mgr.save(checkpoint)
            return "PAUSED"
        
        row = approved[i]
        
        # Email (delay 5 sec per Gmail guidelines)
        email_ok = email_sender.send(..., row["pdf_path"])
        time.sleep(5)
        
        # WhatsApp (delay 3-5 sec random)
        msg = profile.wa_template_params[...].format(**row, link=row["drive_link"])
        wa_ok = whatsapp_sender.send_template(config.aisensy, row["MOBILENO"], msg)
        time.sleep(random.uniform(3, 5))
        
        logger.log_row(i, row, email_ok, wa_ok)
        checkpoint.last_sent_index = i
        checkpoint_mgr.save_atomic(checkpoint)
    
    cleanup_drive_old_files(config.google_drive)  # 30-day auto-delete
    return "COMPLETE"
```

---

## 10. Development Phases (v2.0 — With Mitigations)

### Phase 1 — Core Engine (Week 1–2)
- [ ] `excel_reader.py` — openpyxl + handle None values
- [ ] `doc_generator.py` — docxtpl + XML sanitization + variable pre-check
- [ ] `pdf_converter.py` — **pywin32 direct COM** (NOT docx2pdf), batch-restart logic, DisplayAlerts=0
- [ ] `cloud_uploader.py` — Google Drive upload + share link + quota check
- [ ] `email_sender.py` — Gmail SMTP + 500/day limit check + MIMEMultipart
- [ ] `whatsapp_sender.py` — AiSensy API + error handling
- [ ] `utils/preflight.py` — Gmail auth test, row count warning
- [ ] `utils/sanitizer.py` — Escape `<>&`, convert None → ""
- [ ] `utils/checkpoint.py` — Atomic JSON writes + Excel hash verify
- [ ] CLI test script: end-to-end with 5 sample rows

### Phase 2 — GUI + Preview/Verify (Week 2–4)
- [ ] Main window (CustomTkinter, DPI-aware via SetProcessDpiAwareness)
- [ ] **Setup Tab:** Gmail auth + AiSensy API key + Google Drive creds + Test buttons
- [ ] **Profiles Tab:** CRUD profiles + column mapping dropdowns
- [ ] **Workflow Tab:** File pickers → "Generate All" button
- [ ] **Preview Tab (NEW):** Table view + click-to-open PDF (os.startfile) + approve/exclude + "Send All"/"Send Selected"
- [ ] **Log Tab:** Results table (email/WhatsApp per row) + export CSV + "Retry Failed" (only failed channels)
- [ ] Background threading (CoInitialize per thread for COM)
- [ ] Pause/Resume button + progress indicator

### Phase 3 — Safety & Config (Week 4)
- [ ] `config_manager.py` — Load/save + JSON validation + corruption recovery
- [ ] `validators.py` — Template variable checking + docxtpl.get_undeclared_template_variables()
- [ ] Hidden imports + data files for PyInstaller spec
- [ ] Legal compliance warnings (Section 138, SARFAESI limitations) in UI

### Phase 4 — Packaging (Week 5)
- [ ] PyInstaller spec: hidden imports (win32com, googleapiclient), data collection
- [ ] Build + test .exe on clean Windows + Word installed
- [ ] User guide: template creation, DLT/AiSensy setup, legal warnings
- [ ] README + GitHub repo

---

## 11. Risk Register (v2.0 — 15 Mitigated Risks)

| # | Risk | Status | Likelihood | Impact | Mitigation |
|---|------|--------|-----------|--------|------------|
| 1 | AiSensy template rejected for "legal" language | **Mitigated** | Medium | High | Use neutral template ("important communication shared"); actual legal content in PDF |
| 2 | PII on Google Drive ("anyone with link") — IT Act violation | **Accepted (v1)** | Low | High | UUID filenames + 30-day auto-delete; upgrade to restricted share in v1.5 |
| 3 | PyInstaller + pywin32 DLL load failed | **Mitigated** | Medium | High | Late binding (Dispatch, not EnsureDispatch) + hidden imports in spec |
| 4 | google-api-python-client discovery cache missing | **Mitigated** | Low | High | collect_data_files() in spec file |
| 5 | win32com in background thread — CoInitialize missing | **Mitigated** | Medium | Critical | CoInitialize per thread + STA mode + DisplayAlerts=0 in finally block |
| 6 | docxtpl renders "None" when Excel cell empty | **Mitigated** | High | Medium | Pre-render sanitization: {k: (v or "") for k,v in context.items()} |
| 7 | XML-breaking chars (`<>&`) corrupt Word/PDF | **Mitigated** | Medium | Medium | Escape before docxtpl.render(): .replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;') |
| 8 | Missing template variables → Jinja2 UndefinedError crash | **Mitigated** | Medium | High | Pre-check: `tpl.get_undeclared_template_variables()` vs context keys |
| 9 | WhatsApp new number Tier 1 = 1,000 unique/day limit | **Documented** | Medium | Medium | Warn user: first week max 1K recipients/day; takes 7 days to scale up |
| 10 | Gmail 500/day limit exceeded → last 100 emails rejected | **Mitigated** | Medium | Medium | Pre-flight warning at row_count > 450; suggest batch splitting |
| 11 | App crashes mid-batch → incomplete checkpoint → resume duplication | **Mitigated** | Low | Medium | Stage-aware + Excel hash verify + per-channel status tracking |
| 12 | Email sent but WhatsApp failed (or vice versa) | **Mitigated** | Medium | Medium | Per-channel independent status; "Retry Failed" retries only failed channel |
| 13 | Section 138 cheque bounce sent WhatsApp-only (legally insufficient) | **Documented** | Low | High | UI warning: "WhatsApp/Email supplementary only; use registered post for Sec 138/SARFAESI" |
| 14 | Word shows dialog ("Enable Editing") → thread deadlock | **Mitigated** | Low | Critical | DisplayAlerts=0 + AutomationSecurity=3 + no Visible window |
| 15 | Google Drive link blocked/flagged by WhatsApp spam filters | **Accepted** | Low | Medium | Drive links are whitelisted by Meta; use full URL (not shortened); template pre-approved |

---

## 12. Monthly Cost Breakdown (Law Firm)

| Volume | AiSensy Platform | WhatsApp Messages | Email | Drive | Total |
|--------|-----------------|------------------|-------|-------|-------|
| 200/month | ₹999 | ₹100-140 | ₹0 | ₹0 | **~₹1,100** |
| 500/month | ₹999 | ₹250-350 | ₹0 | ₹0 | **~₹1,350** |
| 1,000/month | ₹999 | ₹500-700 | ₹0 | ₹0 | **~₹1,700** |
| 5,000/month | ₹999 | ₹2,500-3,500 | ₹0 | ₹0 | **~₹4,500** |

**Compare with GK Associates (legacy):** ₹1,000-5,000/month platform + similar per-msg → similar cost but modern tech stack.

---

## 13. Folder Structure After Setup

```
C:\LawFirmNotices\                 ← App install folder
├── NoticeAutomation.exe           ← Single executable
├── config.json                    ← Settings + profiles
├── drive_credentials.json         ← Google Drive service account
├── templates\
│   └── hdfc_lok_adalat.docx       ← Pre-built templates
├── output\                        ← Generated PDFs (auto-created)
│   └── 2026-05-31_HDFC_LokAdalat\
├── logs\                          ← Batch logs
│   └── 2026-05-31_HDFC_batch.json ← Checkpoint + results
└── README.txt                     ← Setup guide
```

---

## 14. Requirements & Mitigations Summary

| Requirement | v1.0 Solution | Build-Time Fix |
|-------------|---------------|----------------|
| Word COM in background thread | pythoncom.CoInitialize() | Ensure STA mode, DisplayAlerts=0 |
| PyInstaller .exe crashes on target | Late binding only | hiddenimports in spec |
| None/empty cells break template | Pre-sanitize context | sanitizer.sanitize_context() |
| XML chars corrupt PDF | Escape before render | sanitizer.escape_xml() |
| Template validation | Pre-check placeholders | docxtpl.get_undeclared_template_variables() |
| Gmail limit | Warn at 450 rows | preflight.check_email_capacity() |
| Pause/Resume state | JSON checkpoint | Atomic writes + Excel hash |
| Large batches freeze UI | Background threading | threading.Thread(daemon=True) |
| Google Drive quota exceeded | Check before upload | about().get(fields='storageQuota') |
| WhatsApp quality rating drops | Neutral template + spacing | Template pre-approved + 3-5 sec delay |

---

## 15. Legal Compliance Notes

**⚠️ Important:** This tool is **supplementary notification only**. For formally required legal notices:

| Notice Type | Requirement | Our Tool | Status |
|-------------|-------------|----------|--------|
| **Sec 138 (Cheque Bounce)** | Registered post (written notice) | Email + WhatsApp | ❌ **Insufficient alone** |
| **SARFAESI Demand** | Written notice to address | Email + WhatsApp | ❌ **Insufficient alone** |
| **EMI Default Reminder** | No formal requirement | Email + WhatsApp | ✅ **Acceptable** |
| **Pre-litigation Notice** | Common law requirement | Email + WhatsApp | ✅ **Acceptable** |
| **Proof of Delivery** | Delivery confirmation needed | WhatsApp "delivered" + email logs | ✅ **Accepted by courts** |

**User Guide Warning:**
```
⚠️ This tool sends legal notices via Email + WhatsApp.
   
For notices requiring physical dispatch (Section 138, SARFAESI):
  → Use this tool as SUPPLEMENTARY notification
  → Also send physical notice via registered post (RPAD)
  → Keep email + WhatsApp logs as supporting evidence
  
This tool alone does NOT satisfy legal service requirements for formal notices.
```

---

## 16. Folder Structure After Setup

```
C:\LawFirmNotices\                 ← App install folder
├── NoticeAutomation.exe           ← Single executable (all included)
├── config.json                    ← Settings + profiles (auto-created)
├── drive_credentials.json         ← Google Drive service account (user adds)

---

## 16. Requirements.txt (v2.0)

```
customtkinter==5.2.2
openpyxl>=3.1.0
docxtpl>=0.20.2
pywin32==306
google-api-python-client>=2.99.0
google-auth-oauthlib>=1.1.0
google-auth-httplib2>=0.2.0
requests>=2.31.0
Pillow>=10.0
pyinstaller>=6.0
```

**Build dependencies:** Before building .exe, run:
```bash
python -m PyInstaller.hooks.hook_pywin32  # Registers win32 COM
pywin32_postinstall -install              # Install COM registry entries
```

---

## 17. Gmail App Password Setup

1. Go to [myaccount.google.com](https://myaccount.google.com)
2. Security → Enable 2-Step Verification
3. Security → App Passwords → Select "Mail" → Generate
4. Copy 16-character password → paste in Setup Tab

---

## 18. AiSensy WhatsApp Setup (Recommended for v1.0)

### Registration (5-10 min)

1. Go to [aisensy.com](https://aisensy.com) → Sign up
2. Create account (email + business info)
3. WhatsApp section → Connect Business Account (link your WhatsApp Business number)
4. Copy **API Key** from Developer Settings
5. Template approval → Submit template (24-48 hrs):
   ```
   "Dear {{1}}, an important communication regarding your account {{2}} 
   has been shared with you. Please review: {{3}}. For queries: {{4}}"
   ```

### Configuration in app

In Setup Tab:
- API Key: [paste from AiSensy dashboard]
- Template Name: `legal_notice_notification` (or whatever you named it)

### Pricing

- Platform: ₹999/month
- Per message: ₹0.50-0.70 (utility template)
- Minimum recharge: ₹100

---

## 19. Google Drive Service Account Setup

### Create service account (one-time, 10 min)

1. [Google Cloud Console](https://console.cloud.google.com) → Create project
2. APIs → Enable Google Drive API
3. Service Accounts → Create service account → Download JSON key
4. Share a Drive folder with the service account email (read/write)
5. Copy JSON file path to config.json `service_account_json_path`

### Code pattern

```python
from googleapiclient.discovery import build
from google.oauth2 import service_account

creds = service_account.Credentials.from_service_account_file(
    "drive_credentials.json", scopes=['https://www.googleapis.com/auth/drive']
)
service = build('drive', 'v3', credentials=creds)
```

---

## 20. Verification Checklist (v2.0)

**Pre-Deployment:**
- [ ] 5-row sample: PDFs generated (win32com, no docx2pdf), all fields filled
- [ ] Gmail: auth test passes, 500/day limit check works
- [ ] Google Drive: PDF uploaded, shareable link created, quota check works
- [ ] Email: test send to own address, attachment opens
- [ ] AiSensy template: approved (check dashboard), test message sent
- [ ] WhatsApp: message received with Drive link clickable
- [ ] docxtpl: variable pre-check works (missing vars caught)
- [ ] XML sanitization: special chars (`<>&`, ₹) handled correctly
- [ ] Checkpoint: JSON written atomically, Excel hash verified on resume
- [ ] COM threading: background thread generates PDF without crashes
- [ ] PyInstaller .exe: runs on clean Windows (no Python), all features work

**In Production:**
- [ ] 100-row batch: no COM hangs (batch-restart logic works)
- [ ] 200-row batch: pause/resume works, checkpoint preserves per-channel status
- [ ] Log export: CSV has all columns (email_status, whatsapp_status, timestamp)
- [ ] Retry: "Retry Failed" only retries failed channel (not both)
- [ ] Legal warning: UI shows warning for Sec 138/SARFAESI limitations

---

## 21. Future Enhancements (v2.0+)

| Feature | Priority | Implementation |
|---------|---------|-----------------|
| Restricted Google Drive sharing | High | Share with recipient email + set expiry |
| Signed Drive URLs | Medium | Time-limited access (24-72 hrs) |
| WhatsApp delivery receipts | Medium | Meta Webhooks for `delivered`/`read` status |
| Migrate to Meta Cloud API | Medium | Drop AiSensy ₹999 platform fee (for 1000+/month) |
| Encrypted credential storage | High | OS keyring (Windows Credential Manager) |
| Email open tracking | Low | Tracking pixel in HTML body |
| Scheduled sending | Low | Windows Task Scheduler integration |
| Multi-language templates | Low | Support Hindi/Marathi notice text |
| Digital signature (PDF) | Low | pyhanko library |

---

## 22. Code Patterns (v2.0 — Mitigated)

### sanitizer.py — Context Safety

```python
def sanitize_context(row_dict: dict) -> dict:
    """Prepare row for docxtpl: None → "", escape XML."""
    sanitized = {}
    for k, v in row_dict.items():
        # Convert None to empty
        if v is None:
            v = ""
        # Escape XML-breaking chars
        if isinstance(v, str):
            v = v.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        sanitized[k] = v
    return sanitized
```

### pdf_converter.py — Win32com with Batch Restart

```python
import pythoncom, win32com.client, time

def init_word_com():
    """Initialize Word COM (STA mode, silent)."""
    pythoncom.CoInitialize()
    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0  # Suppress all dialogs
    word.AutomationSecurity = 3  # Force disable macros
    return word

def batch_convert(docx_paths, restart_every=50):
    """Convert batch with restart every N files."""
    wdFormatPDF = 17
    word = init_word_com()
    pdfs = []
    
    try:
        for i, docx_path in enumerate(docx_paths):
            if i > 0 and i % restart_every == 0:
                word.Quit()
                pythoncom.CoUninitialize()
                time.sleep(1)
                word = init_word_com()
            
            doc = word.Documents.Open(docx_path)
            pdf_path = docx_path.replace('.docx', '.pdf')
            doc.SaveAs(pdf_path, FileFormat=wdFormatPDF)
            doc.Close(0)
            pdfs.append(pdf_path)
    finally:
        word.Quit()
        pythoncom.CoUninitialize()
    
    return pdfs
```

### checkpoint.py — Atomic Resume

```python
import json, os, hashlib, tempfile

def save_checkpoint_atomic(checkpoint_path, data):
    """Atomic write: temp → rename (safe vs crash)."""
    dir_name = os.path.dirname(checkpoint_path) or '.'
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())  # Force to disk
        os.replace(tmp_path, checkpoint_path)  # Atomic
    except Exception as e:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise e

def load_checkpoint(checkpoint_path):
    if not os.path.exists(checkpoint_path):
        return {"stage": "generate", "last_index": 0, "results": {}}
    with open(checkpoint_path, 'r') as f:
        return json.load(f)

def verify_excel_match(excel_path, checkpoint):
    """Prevent resume if Excel changed."""
    with open(excel_path, 'rb') as f:
        new_hash = hashlib.sha256(f.read()).hexdigest()
    
    if checkpoint.get("excel_hash") != new_hash:
        raise ValueError("Excel file changed since last batch. Must regenerate.")
```

### doc_generator.py — Pre-check Variables

```python
from docxtpl import DocxTemplate

def render_with_validation(template_path, context_dict):
    """Validate variables before rendering."""
    tpl = DocxTemplate(template_path)
    
    # Get all {{var}} names in template
    required_vars = tpl.get_undeclared_template_variables()
    
    # Check what's missing
    missing = required_vars - set(context_dict.keys())
    if missing:
        raise ValueError(f"Missing template variables: {missing}")
    
    # Sanitize context
    context_dict = sanitizer.sanitize_context(context_dict)
    
    # Render
    tpl.render(context_dict)
    return tpl
```

---

## 23. SCALING ARCHITECTURE — v3.0+ (Future: 100+ Law Firms)

### 23.1 Desktop vs SaaS Analysis

**v1.0 (Current): Desktop app for 1–5 law firms**
- Cost: ₹0 (open-source) + $100/mo AiSensy platform
- Scaling limit: ~10K notices/batch (8–10 hrs runtime)
- Support: Linear (per-firm installations)
- Update deployment: Manual (30% adoption typical)

**v2.0 (Hybrid): Desktop + optional SaaS**
- Maintain desktop for small firms (cost-sensitive)
- Add SaaS option for enterprise (need uptime guarantee)

**v3.0 (SaaS only): Cloud-native for 100+ firms**
- Infrastructure: AWS Mumbai (₹300–500/mo) handles 500K msgs/day
- Multi-tenancy: Row-level security (per-firm isolation)
- Cost per firm: ₹500–1,000/month
- Revenue at 100 firms: ₹50–100L/month (sustains ₹6–8L/month ops)

### 23.2 Large-Scale Risks (Desktop, 5K–10K+ batches, 6+ months)

| # | Risk Category | Specific Issue | Likelihood | Impact | Mitigation | Roadmap |
|---|---|---|---|---|---|---|
| **16** | **Performance** | Word COM hangs on 10K batch after 8+ hrs | Medium | High | Distribute across multiple PCs (queue system) | v2.5 |
| **17** | **Storage** | 75 GB disk consumed in 6 months | Low | Medium | Auto-archive old batches to S3 (₹1.38/mo) | v2.0 |
| **18** | **Gmail scale** | 200 firms on 1 account = 500÷200 = 2.5 emails/firm/day | Critical | Critical | **Mandatory per-firm Gmail accounts** | v2.0 |
| **19** | **AiSensy reliability** | Single BSP = all firms blocked if downtime | Low | High | Fallback SMS provider (WazirX?) | v3.0 |
| **20** | **Concurrent users** | 2+ users run simultaneously = COM crash | Medium | High | Lock file + queue system | v2.0 |
| **21** | **Config.json plaintext** | Ransomware/theft of credentials | High | Critical | **Encrypt with Fernet + Windows ACLs** | v2.0 |
| **22** | **Audit logging** | No proof of send = inadmissible in court (Sec 65B) | Critical | Critical | **Mandatory: Store raw API logs + timestamps** | v2.0 |
| **23** | **TRAI compliance** | Sender ID not registered = ₹50K/msg fine | High | Critical | **Mandatory NDNC check + template registration** | v2.0 |
| **24** | **Data localization** | NBFC data on US servers violates RBI | High | Critical | **AWS Mumbai only (or on-premise for NBFC)** | v2.0 |
| **25** | **PyInstaller bugfixes** | 100 firms stuck on broken version (auto-update missing) | Medium | High | Implement pyupdater framework | v2.0 |
| **26** | **Python 3.10 EOL** | Oct 2026 (9 months) = critical security risk | Critical | High | **Migrate to 3.12 NOW (test in next 2 months)** | URGENT |
| **27** | **docxtpl abandonment** | Library unmaintained for Py 3.13+ | Low | High | Test Py 3.13 in Dec 2026; plan LibreOffice fallback | v2.5 |
| **28** | **Windows Update breaks COM** | Office library versioning issue post-update | Low | Medium | Late binding already mitigated; fallback docx-only mode | v2.0 |
| **29** | **Google Drive API rate limit** | 5000 PDFs uploaded = hit 1000/100s limit after ~30 min | Medium | Medium | Implement exponential backoff + resume from checkpoint | v1.0 ✓ |
| **30** | **Email spam reputation** | 50–70% emails land in spam if no SPF/DKIM | High | Medium | Add SPF/DKIM setup guide; warm IP reputation | v2.0 |
| **31** | **WhatsApp number ban** | Aggressive messaging patterns trigger Meta suspension | Medium | Critical | Rate-limiting + quality score monitoring + fallback number | v2.0 |
| **32** | **Lawyer approval gate** | Automated sending = Bar Council professional misconduct | Critical | Critical | **Mandatory: Dropdown per notice + human confirmation** | v2.0 |
| **33** | **Multi-channel enforcement** | Sec 138 sent WhatsApp-only = case dismissed | Critical | Critical | **Mandatory: Route-specific validation (Sec 138 needs post + email + WA)** | v2.0 |
| **34** | **Data backup disaster** | PC crashes = all notices lost | Medium | High | Weekly encrypted USB + S3 archive (₹30/year) | v2.0 |
| **35** | **GDPR violation** | EU customers' data on Gmail without DPA | Medium | Medium | Workspace + DPA required; document compliance | v2.0 |

### 23.3 Critical Gates for Production (Non-Negotiable)

These must be implemented BEFORE handling real legal notices:

| Gate | Component | Implementation | Deadline |
|------|-----------|---|---|
| **1. Lawyer Approval** | UI dropdown | "Notice Type" → ☐ Section 138 ☐ SARFAESI ☐ EMI Default ☐ Pre-litigation | v2.0 |
| **2. NDNC Check** | API integration | Before sending WhatsApp, query NDNC database (₹2K/mo) | v2.0 |
| **3. Audit Logging** | Database/JSON | Raw API responses + timestamp + recipient + status → immutable log | v2.0 |
| **4. Section 65B Template** | Auto-generation | Pre-fill affidavit: "I hereby certify that [notice X] was sent on [date] via [channel] with delivery proof [log ID]" | v2.0 |
| **5. Route Validation** | Business logic | IF Section 138: REQUIRE (Email + WhatsApp + Option for Post) ELSE allow Email+WA only | v2.0 |
| **6. Encryption** | Config storage | Encrypt `config.json` with Fernet + require password on startup | v2.0 |
| **7. Multi-Account Gmail** | Infrastructure | Setup per-firm Gmail accounts (free) OR switch to Workspace (₹300/mo for 100 firms) | v2.0 |
| **8. Backup System** | Automated | Weekly zip of checkpoint + logs → encrypted USB slot + S3 archive | v2.0 |

### 23.4 Roadmap: Desktop → SaaS Migration (18–24 months)

| Phase | Timeline | Goal | Investment | Revenue Impact |
|-------|----------|------|------------|-----------------|
| **v1.0** | Now–Jul 2026 | Launch desktop, 5–10 pilot firms | $500 (dev) | $0 (test) |
| **v2.0** | Jul–Oct 2026 | Production-ready: audit logs + compliance gates + auto-update | $3K (dev + testing) | ₹5L/yr (10 firms × ₹50K/yr) |
| **v2.5** | Oct 2026–Jan 2027 | Scale to 50 firms: queue system + load balancing | $2K (queue + monitoring) | ₹25L/yr (50 firms) |
| **v3.0 Beta** | Jan–Jun 2027 | SaaS alpha: multi-tenancy + cloud infrastructure | $25K (AWS + backend dev) | ₹50L/yr (100 beta users) |
| **v3.0 GA** | Jul 2027+ | Production SaaS for 100+ firms | Amortized | ₹100L/yr (200+ firms) |

### 23.5 Desktop Limits & Thresholds

| Metric | Threshold | Mitigation |
|--------|-----------|------------|
| **Batch size** | >10,000 notices | Migrate to SaaS OR split into 5K+5K |
| **Concurrent users** | >1 user/PC | Queue system + lock file |
| **Monthly volume** | >5,000 notices | Per-firm Gmail (not shared account) |
| **Disk space** | <100 GB free | Archive to S3 + warn user |
| **Daily sends** | >500/firm | Upgrade to Workspace Gmail (2K/day limit) |
| **Batch runtime** | >12 hours | Split batch or upgrade to SaaS |
| **Python version** | 3.10 (EOL Oct 2026) | **URGENT: Migrate to 3.12 by Aug 2026** |

### 23.6 SaaS Architecture (v3.0)

**Infrastructure:**
```
AWS Mumbai (ap-south-1)
├── ALB (load balancer)
├── Auto-scaling EC2 (2–10 instances, t3.medium)
├── RDS PostgreSQL (audit logs + batch history)
├── S3 (PDF archive, ₹1.38/mo per firm)
├── SQS (message queue for WhatsApp/Email)
└── CloudWatch (monitoring + alerts)

Cost: ₹300–500/mo ops | ₹500/firm revenue = breakeven at ~1 firm, profit on rest
```

**Multi-tenancy:**
- Row-level security (PostgreSQL) for audit logs
- Separate S3 buckets per firm (namespace isolation)
- Token-based API auth (per-firm)
- Dedicated WhatsApp Business accounts per firm (avoid cross-contamination)

### 23.7 Python 3.10 EOL — CRITICAL (9 months left)

**Current status:** Python 3.10 EOL = **Oct 2026** (only 9 months from now)

**Action items (next 2 months):**
1. Test v1.0 on **Python 3.12** (latest stable)
2. Check dependencies:
   - `docxtpl`: Test Py 3.12 support (sporadic updates; may need fork)
   - `pywin32`: 306+ supports 3.12 ✓
   - `openpyxl`: 3.1.5 supports 3.12 ✓
   - `google-api-python-client`: 2.99.0 supports 3.12 ✓
3. **Decision point (Aug 2026):**
   - If all deps OK → migrate to 3.12, test PyInstaller build
   - If `docxtpl` broken → plan fallback (LibreOffice headless? or fork docxtpl)

**Risk:** If we don't migrate before Oct 2026, bug fixes become impossible (security updates stop)

---

## 24. Compliance Gates & Legal Requirements

### 24.1 Bar Council & Professional Responsibility

**Requirement:** Lawyer must personally approve each notice before sending (automated dispatch = professional misconduct)

**Implementation in UI:**
```
Workflow Tab → Before "Send Selected":
┌──────────────────────────────────────────────┐
│ ⚠️  LAWYER APPROVAL REQUIRED                 │
├──────────────────────────────────────────────┤
│ Notice Type:  [Select ▼]                     │
│               ☐ Section 138 (Cheque Bounce)  │
│               ☐ SARFAESI (Demand Notice)     │
│               ☐ EMI Default (Reminder)       │
│               ☐ Pre-litigation (Custom)      │
├──────────────────────────────────────────────┤
│ I certify that I have personally verified    │
│ the above notices and approve for sending.   │
│                                              │
│ Signature: _________________________ (e-sign) │
│                                              │
│ [  APPROVE & SEND  ]  [  CANCEL  ]          │
└──────────────────────────────────────────────┘
```

### 24.2 TRAI DLT Registration (Mandatory for India)

**Required before ANY WhatsApp bulk send:**
1. Register with TRAI DND portal (JIO TrueConnect / Airtel UCC)
2. Register Sender ID (e.g., `GKLAW`) — approved in 1–3 days
3. Register template (neutral language) — approved in 24–48 hrs
4. Implement NDNC check: query national DND database before sending to each number
5. Penalties: ₹50,000 PER MESSAGE if violated

**Setup cost:** ₹2K–5K (one-time)
**Monthly:** ₹2K (NDNC API subscription) + ₹999 (AiSensy platform)

### 24.3 Section 65B (Electronic Evidence Admissibility)

**What courts require:**
- **Raw API logs** (not screenshots): timestamp, sender, recipient, status
- **Section 65B Certificate** (affidavit): IT officer certifies digital record authenticity
- **Chain of custody**: Original → log → archive (no modifications)
- **Retention:** 7 years minimum

**Implementation:**
- Every send stored to immutable log (JSON → quarterly archive to Glacier)
- Pre-filled affidavit template (lawyer prints, signs, submits to court)
- CSV export with columns: Date | Recipient | Status | Message ID

---

## 25. v2.0 Implementation Roadmap (4 weeks)

**Week 1:** Core engine (done in v1.0)  
**Week 2:** GUI + compliance gates  
**Week 3:** Encryption + audit logging + auto-update setup  
**Week 4:** Testing + packaging

**Critical features for compliance (NOT optional):**
- ✅ Lawyer approval gate (UI dropdown + e-sign)
- ✅ NDNC pre-check (API integration)
- ✅ Audit logging (raw API responses → immutable log)
- ✅ Section 65B certificate auto-generation
- ✅ Route-specific validation (Section 138 enforcement)
- ✅ Encryption (config.json)
- ✅ Per-firm Gmail accounts (or Workspace)
- ✅ Auto-update mechanism (pyupdater)

---

## 26. Cost Analysis: Desktop vs SaaS

### 26.1 Desktop (v1.0–v2.5): 1–50 firms

**Per firm annual cost:**
- AiSensy platform: ₹12K/yr (₹999/mo)
- WhatsApp messages: ₹2.4–6K/yr (200–500 msgs/mo @ ₹12-15/msg)
- Gmail Workspace (optional): ₹3.6K/yr (₹300/mo for 100 firms = negligible per firm)
- **Total: ₹14.4–21K/yr per firm**

**Vendor costs (your business):**
- Support: ₹0 (email-based; scales to ₹20K/mo at 50+ firms)
- Infrastructure: ₹0 (desktop runs on their PC)
- **Margin: High** (₹50–100K/setup fee × 50 firms = ₹25–50L lifetime)

### 26.2 SaaS (v3.0): 100+ firms

**Per firm annual cost:**
- Platform subscription: ₹60K/yr (₹5K/mo) ← Increase per firm as you scale
- WhatsApp: ₹2.4–6K/yr (same per-message rate, bulk discount at 500K msgs/day)
- Infrastructure (shared): ₹300–500/mo ÷ 100 firms = ₹36–60K/yr shared
- **Total: ₹98.4–120K/yr per firm** (3x more expensive than desktop)

**But:** SaaS revenue scales better
- 100 firms × ₹80K/yr = ₹80L revenue
- Ops cost: ₹6–8L/yr
- **Margin: ₹72–74L/yr (massive, single product!)**

**Decision:** Migrate to SaaS when 20–30 firms → economics shift

---

*Prepared by: GitHub Copilot | Project: Law Firm Automation | Version: 2.0 (Scaling Analysis Added) | Last Updated: 2026-05-31*
