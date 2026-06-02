# EmailWAAutomation — Complete Technical Index & Understanding Document

**Generated:** June 2, 2026  
**Project:** BulkEmailWA / EmailWAAutomation (Law Firm Bulk Notice Automation)  
**Status:** Production-ready, packaged as single .exe  
**Memory Location:** Repository memory (/memories/repo/)

---

## 📚 TABLE OF CONTENTS

1. [Knowledge Base Overview](#knowledge-base-overview)
2. [Project Summary](#project-summary)
3. [Complete Memory Index](#complete-memory-index)
4. [Technical Deep Dives](#technical-deep-dives)
5. [Key Architecture Patterns](#key-architecture-patterns)
6. [Critical Issues & Solutions](#critical-issues--solutions)
7. [State Management & Data Flow](#state-management--data-flow)
8. [Quick Navigation Guide](#quick-navigation-guide)

---

## KNOWLEDGE BASE OVERVIEW

### 📖 Documents Stored in Memory

I have **4 comprehensive technical documents** stored in repository memory, totaling **44,194 words** of detailed knowledge:

| Document | Lines | Size | Purpose |
|----------|-------|------|---------|
| **PROJECT_ARCHITECTURE.md** | 400+ | 14.8 KB | Complete tech stack, module breakdown, build process |
| **QUICK_REFERENCE.md** | 200+ | 5.3 KB | Developer patterns, debug tips, command reference |
| **GOTCHAS_AND_SOLUTIONS.md** | 350+ | 9.4 KB | 15 critical gotchas with solutions and workarounds |
| **DATA_FLOW_AND_STATE.md** | 450+ | 14.9 KB | State management, threading model, data flow diagrams |

### 🎯 What This Index Does

This document provides:
- ✅ Master roadmap to all stored knowledge
- ✅ Quick lookup for specific topics
- ✅ Understanding of how everything connects
- ✅ Links to detailed explanations
- ✅ One-page reference for developers

---

## PROJECT SUMMARY

### What It Does

**EmailWAAutomation** is a desktop application for law firms to automate bulk legal notice distribution:

```
INPUT: Excel file (customer data)
  ↓
PROCESS: Generate PDFs, upload to Drive, send emails & WhatsApp
  ↓
OUTPUT: Delivery logs with proof of delivery
```

### Key Features

1. **Two-Stage Pipeline**
   - Stage 1: Generate all PDFs from templates
   - Stage 2: Preview, approve, then send emails & WhatsApp

2. **Multi-Client Profiles**
   - Each bank/client has own template & settings
   - Customizable email subjects & WhatsApp templates

3. **Crash-Safe Checkpoint System**
   - Pause/Resume capability
   - Excel hash verification
   - Atomic file writes

4. **Real-Time Progress Tracking**
   - Live GUI updates
   - Per-recipient logging
   - Selective retry for failed sends

### Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **UI** | CustomTkinter 5.2.2 | Modern desktop GUI, DPI-aware |
| **Data** | openpyxl 3.1+ | Excel reading |
| **Templates** | docxtpl 0.20.2 | Jinja2-based Word templating |
| **PDF** | pywin32 (win32com) | Direct Word COM for PDF conversion |
| **Cloud** | google-api-python-client | Google Drive API |
| **Email** | smtplib + email.mime | Gmail SMTP |
| **WhatsApp** | requests + AiSensy | Official Meta BSP integration |
| **Logging** | JSON (atomic) | Crash-safe per-recipient logs |
| **Packaging** | PyInstaller 6.x | Single .exe distribution |

---

## COMPLETE MEMORY INDEX

### 📄 Document 1: PROJECT_ARCHITECTURE.md

**Coverage:** Complete technical architecture and design decisions

#### Sections Included:
- **1. Problem & Solution** — Business context
- **2. Tech Stack** — Detailed library choices and versions
- **3. Architecture Overview** — Main flow diagram (5 tabs)
- **4. Two-Stage Pipeline** — Generate & Send stages
- **5. Key Design Decisions** — Why Word COM, AiSensy, checkpoint system
- **6. Code-Level Details** — All core modules (9 modules detailed)
- **7. Utils & Support Modules** — Helper functions
- **8. UI Modules** — All 5 tabs explained
- **9. Config.json Structure** — Complete configuration reference
- **10. Critical Mitigations** — Thread safety, crash recovery, idempotency
- **11. Build & Packaging** — PyInstaller configuration

#### Key Modules Documented:
```
Core:
  └─ batch_runner.py (orchestration)
  └─ pdf_converter.py (Word → PDF)
  └─ doc_generator.py (template rendering)
  └─ email_sender.py (Gmail SMTP)
  └─ whatsapp_sender.py (AiSensy API)
  └─ cloud_uploader.py (Google Drive)
  └─ excel_reader.py (Excel parsing)

Utils:
  └─ checkpoint.py (crash-safe state)
  └─ config_manager.py (config I/O)
  └─ logger.py (per-recipient logs)
  └─ atomic_io.py (atomic writes)
  └─ sanitizer.py (input sanitization)
  └─ validators.py (email/phone/template validation)
  └─ preflight.py (pre-batch checks)
  └─ ssl_compat.py (Windows cert handling)

UI:
  └─ app.py (main window)
  └─ setup_tab.py (credentials & auth tests)
  └─ profiles_tab.py (CRUD client profiles)
  └─ workflow_tab.py (Excel + profile selection)
  └─ preview_tab.py (row review before send)
  └─ log_tab.py (results & retry)
```

#### When to Reference:
- Need to understand overall project architecture
- Want to know WHY certain libraries were chosen
- Building new features or extending functionality
- Understanding module responsibilities

---

### 📄 Document 2: QUICK_REFERENCE.md

**Coverage:** Developer patterns, debug tips, and command reference

#### Sections Included:
- **Quick Architecture Diagram** — Visual flow from click to completion
- **Key Patterns** (5 patterns explained)
  - Pattern 1: Background Thread + Queue Communication
  - Pattern 2: Atomic File Writes
  - Pattern 3: Crash Recovery
  - Pattern 4: Threading + COM (Word)
  - Pattern 5: Error Handling (Return Tuple)
- **Debug Tips** — Common issues and solutions
- **Testing Checklist** — 10 test items
- **Common Commands** — Build, test, run
- **File Locations** — Relative to app
- **Config Edit Tips** — Gmail, AiSensy, Drive setup

#### When to Reference:
- Implementing new features using existing patterns
- Debugging specific issues
- Setting up development environment
- Quick lookup of common commands

---

### 📄 Document 3: GOTCHAS_AND_SOLUTIONS.md

**Coverage:** Critical issues, workarounds, and lessons learned

#### 15 Critical Gotchas Documented:

1. **DPI Awareness** — Must set BEFORE window creation
2. **Word COM Memory Leak** — Restart every 50 files
3. **COM Thread Initialization** — pythoncom.CoInitialize() required
4. **Atomic File Writes** — Never use raw json.dump()
5. **Excel Hash for Resume** — SHA-256 change detection
6. **Threading + GUI** — Queue-based communication only
7. **Gmail App Password** — Not regular password
8. **WhatsApp Content Policy** — Meta blocks "legal" language
9. **Document Variable Sanitization** — XML escaping required
10. **Google Drive Sharing** — Public link vs email-restricted
11. **PyInstaller Hidden Imports** — Explicit dependency list needed
12. **Pause/Resume Semantics** — Event naming confusing
13. **First Run Bootstrap** — Copy default config from bundled
14. **Template Variable Pre-Check** — Fail-fast validation
15. **Column Mapping Flexibility** — Excel columns → Template variables

#### Performance Bottlenecks Table:
- PDF render: 2-3 sec (Word COM)
- Drive upload: 0.5-1 sec
- Email send: 1-2 sec
- WhatsApp send: 0.5-1 sec
- Total per row: 4-7 sec
- Batch of 100: 7-12 minutes

#### When to Reference:
- Encountering unexpected errors
- Understanding design trade-offs
- Avoiding common pitfalls
- Performance optimization needs

---

### 📄 Document 4: DATA_FLOW_AND_STATE.md

**Coverage:** Complete state management, threading model, and data flow

#### Sections Included:
- **Data Flow Diagram** — Excel → PDF → Drive → Email/WhatsApp
- **State Management Architecture** (3 levels)
  - Global State (ConfigManager)
  - Per-Batch State (BulkNoticeApp + BatchRunner)
  - Checkpoint State (CheckpointManager)
  - Batch Log State (BatchLogger)
- **Threading Model** — Main thread vs Background thread
- **Config.json Profiles Section** — Detailed structure
- **Error State Propagation** — How errors are handled per stage
- **Time/ID Generation** — Batch IDs, Drive filenames
- **Cleanup & Persistence** — On success/pause/cancel
- **Key Invariants** (7 invariants listed)
- **Testing State Flows** (4 test scenarios)

#### State Objects Documented:

```
ConfigManager
  └─ gmail: {sender_email, app_password}
  └─ aisensy: {api_key, template_name, mock_mode}
  └─ google_drive: {path, folder_id, delete_days, mock_mode}
  └─ profiles: {name → {template, subject, body, params}}
  └─ settings: {output_folder, log_folder, delays, limits}

BulkNoticeApp (Main Window)
  └─ current_batch: list[dict]
  └─ current_batch_id: str
  └─ current_profile_name: str
  └─ current_log_path: str

CheckpointManager (Per-Batch)
  └─ batch_id, excel_path, excel_hash
  └─ stage: "generate" | "send"
  └─ last_generated_index, last_sent_index
  └─ results: {index → {pdf_path, drive_link, included}}

BatchLogger (Per-Recipient)
  └─ index, name, email, phone
  └─ pdf_path, drive_link
  └─ email_status, email_error
  └─ whatsapp_status, whatsapp_error
  └─ timestamp
```

#### When to Reference:
- Understanding how state is managed across operations
- Implementing pause/resume functionality
- Debugging state inconsistencies
- Adding new state tracking
- Understanding checkpoint recovery

---

## TECHNICAL DEEP DIVES

### 1. PDF Conversion (Word COM)

**From:** PROJECT_ARCHITECTURE.md (Section 4.2.1)

**Key Points:**
- Uses `win32com.client.Dispatch("Word.Application")`
- Auto-restarts every 50 files to prevent memory leak
- Settings:
  - `AutomationSecurity = 3` (disable macros)
  - `DisplayAlerts = 0` (suppress popups)
  - `Visible = False` (headless)
- Must call in background thread with `pythoncom.CoInitialize()`

**Related Gotcha:** GOTCHAS_AND_SOLUTIONS.md (#2, #3, #4)

---

### 2. Google Drive Integration

**From:** PROJECT_ARCHITECTURE.md (Section 4.2.3)

**Key Points:**
- Service account JSON authentication
- UUID filenames for security
- "Anyone with link" public sharing (with 30-day auto-delete)
- Returns shareable view URLs
- Mock mode for testing

**JWT Error Solution:**
- Root cause: Expired service account key
- Fix: Regenerate key from Google Cloud Console
- Test: `py -3 test_drive_auth.py`

---

### 3. WhatsApp via AiSensy

**From:** PROJECT_ARCHITECTURE.md (Section 4.2.2)

**Key Points:**
- Official Meta Business Solution Partner (no ban risk)
- Pre-approved template system (24-48h review)
- Template: Neutral notification (avoids legal language rejection)
- Variables: `{{1}}` name, `{{2}}` account, `{{3}}` drive_link, `{{4}}` contact
- Mock mode: Log without API calls

**Critical:** GOTCHAS_AND_SOLUTIONS.md (#8) — Meta blocks "legal" language

---

### 4. Checkpoint System

**From:** DATA_FLOW_AND_STATE.md (Section 1.3)

**Key Points:**
- Saves after each row (atomic JSON writes)
- Excel hash (SHA-256) for change detection
- Can resume from last_generated_index
- File: `logs/<batch_id>_checkpoint.json`
- Persists on crash; recovers on next run

---

### 5. Threading Model

**From:** DATA_FLOW_AND_STATE.md (Section 2)

**Key Points:**
```
Main Thread (GUI)
  ├─ UI event handlers
  ├─ Polling progress_queue every 150ms
  └─ Display updates

Background Thread (Worker)
  ├─ pythoncom.CoInitialize() at start
  ├─ Process rows in loop
  ├─ Post to progress_queue (thread-safe)
  ├─ Check pause_event / cancel_event
  └─ pythoncom.CoUninitialize() at end
```

**Critical:** Never call GUI updates from background thread; use queue only

---

## KEY ARCHITECTURE PATTERNS

### Pattern 1: Background Thread + Queue

**File:** core/batch_runner.py, ui/workflow_tab.py

```python
# Background thread posts progress:
self._q.put({"type": "progress", "current": i, "total": total})

# UI thread polls periodically:
def _poll_queue(self):
    while not self._app.progress_queue.empty():
        msg = self._app.progress_queue.get()
        self._update_progress(msg)
    self.after(150, self._poll_queue)  # Repeat every 150ms
```

**Why:** Tkinter not thread-safe; queue is thread-safe

---

### Pattern 2: Atomic File Writes

**File:** utils/atomic_io.py

```python
def atomic_write_json(path, data):
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f)
    os.replace(tmp_path, path)  # Atomic on Windows/Unix
```

**Why:** Crash mid-write doesn't corrupt checkpoint file

---

### Pattern 3: Crash Recovery

**File:** utils/checkpoint.py

```python
def __init__(self, path, batch_id, excel_path, excel_hash, ...):
    existing = self._load()
    if existing and existing.get("excel_hash") == excel_hash:
        self._data = existing  # Resume from checkpoint
    else:
        self._data = {...}  # Fresh start
```

**Why:** User can pause app, crash happens, and resume from last checkpoint

---

### Pattern 4: Error Per-Row (Not Batch-Stopping)

**File:** core/email_sender.py, core/whatsapp_sender.py

```python
ok, err = email_sender.send(...)
if not ok:
    logger.log_row(..., email_status="failed", email_error=err)
    continue  # Don't crash batch, just skip this row
```

**Why:** One recipient's email failure shouldn't stop entire batch

---

### Pattern 5: Config-Driven Behavior

**File:** utils/config_manager.py, config.json

```python
cfg.get("profiles.HDFC_PSS_Notice.template_path")  # → "templates/Notice_Template.docx"
cfg.get("gmail.sender_email")  # → "rkorade.01@gmail.com"
```

**Why:** No code changes needed for different clients/templates

---

## CRITICAL ISSUES & SOLUTIONS

### Issue 1: PDF Conversion Hangs After 100 Files

**Symptoms:** App freezes around file 100+

**Root Cause:** Word COM memory leak (not cleaned up)

**Solution:** WordPdfConverter auto-restarts every 50 files

**Reference:** GOTCHAS_AND_SOLUTIONS.md (#2)

---

### Issue 2: "Invalid JWT Signature" on Drive Upload

**Symptoms:** Google Drive authentication fails

**Root Causes (in order of likelihood):**
1. Service account key expired/rotated
2. Drive folder not shared with service account
3. Computer clock out of sync
4. Google Drive API not enabled

**Solution:** 
1. Regenerate key in Google Cloud Console
2. Share Drive folder with service account email
3. Sync system time
4. Enable Drive API

**Reference:** DRIVE_JWT_TROUBLESHOOTING.md (created during recent session)

---

### Issue 3: Template Render Fails with Missing Variables

**Symptoms:** docxtpl throws error about undefined `{{VARIABLE}}`

**Root Cause:** Template has `{{VAR}}` not present in row data

**Solution:** Pre-validate template variables before rendering

**Code:** doc_generator.py calls `validate_template_variables()`

**Reference:** GOTCHAS_AND_SOLUTIONS.md (#14)

---

### Issue 4: WhatsApp Message Rejected by Meta

**Symptoms:** Message fails with "template not approved" or "content policy"

**Root Causes:**
1. Template not pre-approved on AiSensy
2. Template contains "legal", "court", "demand", "seize"
3. Template language doesn't match approved version

**Solution:** Use neutral notification template only

**Approved Template:** 
```
"Dear {{1}}, an important communication regarding your account {{2}} 
has been shared with you. Please review: {{3}}. For queries: {{4}}. 
— [Firm Name]"
```

**Reference:** PROJECT_ARCHITECTURE.md (Section 4)

---

### Issue 5: Config.json Corruption on Crash

**Symptoms:** App fails to load config with JSON error

**Root Cause:** Unbuffered write crashed mid-JSON

**Solution:** All writes use atomic_write_json (write to .tmp, then replace)

**Recovery:** ConfigManager backs up to config.json.bak, creates fresh from defaults

**Reference:** utils/config_manager.py

---

## STATE MANAGEMENT & DATA FLOW

### Excel → PDF → Drive → Email/WhatsApp Flow

```
┌──────────────┐
│  Excel File  │  → excel_reader.read_excel()
└──────────────┘     → List[Dict] rows
      │
      ├─→ Template Render (docxtpl)
      │   → Sanitize context (escape XML)
      │   → output/batch_id/ACCOUNT_Name.docx
      │
      ├─→ PDF Convert (Word COM)
      │   → pdf_converter.WordPdfConverter.convert()
      │   → output/batch_id/ACCOUNT_Name.pdf
      │
      ├─→ Drive Upload
      │   → cloud_uploader.DriveUploader.upload_pdf()
      │   → UUID-named file on Drive
      │   → Return shareable link
      │
      ├─→ Checkpoint Save (Atomic)
      │   → logs/batch_id_checkpoint.json
      │   → {pdf_path, drive_link, included: true}
      │
      ├─→ (Preview Tab — User Approves)
      │
      ├─→ Email Send
      │   → email_sender.EmailSender.send()
      │   → Gmail SMTP with PDF attachment
      │   → Log status: "sent" or "failed"
      │
      ├─→ WhatsApp Send (3-5 sec delay)
      │   → whatsapp_sender.WhatsAppSender.send()
      │   → AiSensy API with Drive link
      │   → Log status: "sent" or "failed"
      │
      └─→ Batch Log Write (Atomic)
          → logs/batch_id.json
          → [{index, name, email, pdf_path, drive_link, 
               email_status, wa_status, timestamp}]
```

### Per-Batch State Lifecycle

```
1. Start Generate
   └─ New batch_id generated
   └─ New checkpoint created
   └─ Rows processed one by one

2. Stage 1 Complete
   └─ All PDFs generated (or some skipped on error)
   └─ Checkpoint fully populated
   └─ Preview tab shows generated rows

3. User Approves
   └─ Can exclude individual rows
   └─ Marks as "approved"

4. Stage 2 Starts
   └─ For each approved row:
   │  ├─ Send Email
   │  ├─ Send WhatsApp
   │  └─ Log result

5. Stage 2 Complete
   └─ Final log written
   └─ Checkpoint can be deleted
   └─ Output files retained for reference
```

---

## QUICK NAVIGATION GUIDE

### I Need To...

#### Understand How Something Works
1. **Start with:** QUICK_REFERENCE.md (Quick Architecture Diagram)
2. **Then read:** PROJECT_ARCHITECTURE.md (Detailed module breakdown)
3. **For state:** DATA_FLOW_AND_STATE.md (State management)

#### Fix a Bug
1. **Check:** GOTCHAS_AND_SOLUTIONS.md (Common issues list)
2. **Debug:** QUICK_REFERENCE.md (Debug Tips section)
3. **Understand:** PROJECT_ARCHITECTURE.md (Relevant module details)

#### Implement a New Feature
1. **Review patterns:** QUICK_REFERENCE.md (Key Patterns)
2. **Check existing code:** PROJECT_ARCHITECTURE.md (Module responsibilities)
3. **State implications:** DATA_FLOW_AND_STATE.md (State management)

#### Troubleshoot Google Drive Issues
- **JWT Error:** See memory session notes or REGENERATE_SERVICE_KEY.md
- **Upload fails:** Check GOTCHAS_AND_SOLUTIONS.md (#10)
- **Quota issues:** CONFIG.json google_drive section

#### Understand Threading
1. **Overview:** QUICK_REFERENCE.md (Pattern 1: Background Thread)
2. **Detailed:** DATA_FLOW_AND_STATE.md (Section 2: Threading Model)
3. **Gotchas:** GOTCHAS_AND_SOLUTIONS.md (#3, #4, #6)

#### Optimize Performance
1. **Bottlenecks:** GOTCHAS_AND_SOLUTIONS.md (Performance Bottlenecks table)
2. **Word COM:** GOTCHAS_AND_SOLUTIONS.md (#2)
3. **Parallelization:** Future improvements section

#### Set Up New Client Profile
1. **Config structure:** PROJECT_ARCHITECTURE.md (Section 9)
2. **Column mapping:** DATA_FLOW_AND_STATE.md (Section 3: Column Mapping)
3. **Template validation:** GOTCHAS_AND_SOLUTIONS.md (#14)

---

## SUMMARY TABLE: What You Know

| Area | Coverage | Source | Details |
|------|----------|--------|---------|
| **Architecture** | Complete | PROJECT_ARCHITECTURE.md | All 10 modules + core libraries |
| **Data Flow** | Complete | DATA_FLOW_AND_STATE.md | Excel → PDF → Drive → Email/WhatsApp |
| **State Management** | Complete | DATA_FLOW_AND_STATE.md | Config, batch, checkpoint, logger |
| **Threading** | Complete | DATA_FLOW_AND_STATE.md + QUICK_REFERENCE.md | Queue-based communication |
| **Error Handling** | Complete | GOTCHAS_AND_SOLUTIONS.md | 15 critical issues + solutions |
| **Patterns** | Complete | QUICK_REFERENCE.md | 5 core architectural patterns |
| **Gotchas** | Complete | GOTCHAS_AND_SOLUTIONS.md | DPI, COM, atomic writes, etc. |
| **API Integration** | Complete | PROJECT_ARCHITECTURE.md | Gmail, AiSensy, Google Drive |
| **Configuration** | Complete | DATA_FLOW_AND_STATE.md | Config.json structure explained |
| **Crash Recovery** | Complete | GOTCHAS_AND_SOLUTIONS.md (#4, #5) | Checkpoint + Excel hash |

---

## ACCESSING YOUR MEMORY

All stored knowledge is in: `/memories/repo/`

Files:
```
/memories/repo/
├─ PROJECT_ARCHITECTURE.md      (14.8 KB)
├─ QUICK_REFERENCE.md           (5.3 KB)
├─ GOTCHAS_AND_SOLUTIONS.md      (9.4 KB)
└─ DATA_FLOW_AND_STATE.md        (14.9 KB)
```

### Using Memory in Conversations

To reference specific information:
```python
# Example query
memory.view(path="/memories/repo/GOTCHAS_AND_SOLUTIONS.md")
memory.view(path="/memories/repo/DATA_FLOW_AND_STATE.md", view_range=[1, 100])
```

---

## NEXT STEPS FOR DEVELOPMENT

### For Feature Development
1. Reference appropriate architecture section
2. Follow established patterns from QUICK_REFERENCE.md
3. Check GOTCHAS_AND_SOLUTIONS.md for related issues
4. Understand state implications in DATA_FLOW_AND_STATE.md

### For Bug Fixes
1. Search GOTCHAS_AND_SOLUTIONS.md first
2. Check debug tips in QUICK_REFERENCE.md
3. Review module code in PROJECT_ARCHITECTURE.md
4. Understand state context in DATA_FLOW_AND_STATE.md

### For New Contributors
1. Read PROJECT_ARCHITECTURE.md (overview)
2. Study QUICK_REFERENCE.md (patterns and commands)
3. Review GOTCHAS_AND_SOLUTIONS.md (critical issues)
4. Deep dive: DATA_FLOW_AND_STATE.md (for assigned area)

---

**This index was generated to provide a complete technical understanding of the EmailWAAutomation project stored in memory. Reference the appropriate documents for detailed information on any topic.**
