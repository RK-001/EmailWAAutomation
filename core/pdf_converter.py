"""
core/pdf_converter.py
---------------------
Convert .docx files to PDF using Microsoft Word via COM automation (win32com).

Why direct win32com instead of docx2pdf?
  - docx2pdf has a known memory leak causing hangs after ~100 files (GitHub #111, #97)
  - Direct COM gives us full control: restart Word every N files, suppress all dialogs

Key mitigations:
  - DisplayAlerts = 0         → suppress all Word popups
  - AutomationSecurity = 3    → force-disable macros (prevent dialog deadlocks)
  - word.Visible = False       → headless operation
  - CoInitialize per thread   → required for COM in background threads (STA mode)
  - Batch restart every N     → prevents Word COM memory leak hang

IMPORTANT: Call pdf_converter functions from a background thread only.
           The calling thread MUST call pythoncom.CoInitialize() before use.
           This module does NOT call CoInitialize itself — it is the caller's
           responsibility to manage COM thread initialization.

Usage:
    # In background thread:
    pythoncom.CoInitialize()
    try:
        converter = WordPdfConverter(restart_every=50)
        pdf_path = converter.convert(docx_path)
        converter.quit()
    finally:
        pythoncom.CoUninitialize()
"""

import os
import time

import pythoncom
import win32com.client

# Word fixed-format export constants.
_WD_EXPORT_FORMAT_PDF = 17
_WD_EXPORT_OPTIMIZE_FOR_PRINT = 0
_WD_EXPORT_ALL_DOCUMENT = 0
_WD_EXPORT_DOCUMENT_CONTENT = 0
_WD_EXPORT_CREATE_NO_BOOKMARKS = 0
_WD_FORMAT_PDF_SAVE_AS = 17


class WordPdfConverter:
    """
    Stateful Word COM converter that handles batch restart automatically.

    Create one instance per background thread. Call quit() when done.
    """

    def __init__(self, restart_every: int = 50):
        """
        Args:
            restart_every: Restart the Word COM process every N files
                           to prevent memory leak hangs.
        """
        self.restart_every = restart_every
        self._convert_count = 0
        self._word = None
        self._start_word()

    # ── Public interface ─────────────────────────────────────────────────────

    def convert(self, docx_path: str) -> str:
        """
        Convert a single .docx file to PDF.

        Args:
            docx_path: Absolute path to the .docx file.

        Returns:
            Absolute path to the generated .pdf file (same directory as docx).

        Raises:
            FileNotFoundError: If docx_path does not exist.
            RuntimeError:      If Word COM conversion fails.
        """
        docx_path = os.path.abspath(docx_path)
        if not os.path.exists(docx_path):
            raise FileNotFoundError(f"DOCX file not found: {docx_path}")

        # Auto-restart Word every N files to prevent memory leak
        if self._convert_count > 0 and self._convert_count % self.restart_every == 0:
            self._restart_word()

        pdf_path = os.path.splitext(docx_path)[0] + ".pdf"

        doc = None
        try:
            doc = self._open_document(docx_path)
            self._export_pdf(doc, pdf_path)
        except Exception as exc:
            raise RuntimeError(
                f"Word COM conversion failed for '{os.path.basename(docx_path)}': {exc}"
            ) from exc
        finally:
            if doc is not None:
                try:
                    doc.Close(0)   # 0 = do not save changes
                except Exception:
                    pass

        self._convert_count += 1
        return pdf_path

    def quit(self) -> None:
        """Cleanly shut down the Word COM application."""
        self._quit_word()

    # ── Internal ─────────────────────────────────────────────────────────────

    def _open_document(self, docx_path: str):
        """Open a document with dialog/recent-file side effects disabled."""
        try:
            return self._word.Documents.OpenNoRepairDialog(
                FileName=docx_path,
                ConfirmConversions=False,
                ReadOnly=True,
                AddToRecentFiles=False,
                Revert=False,
                Visible=False,
                OpenAndRepair=False,
                NoEncodingDialog=True,
            )
        except Exception:
            return self._word.Documents.Open(
                FileName=docx_path,
                ConfirmConversions=False,
                ReadOnly=True,
                AddToRecentFiles=False,
                Revert=False,
                Visible=False,
                OpenAndRepair=False,
                NoEncodingDialog=True,
            )

    def _export_pdf(self, doc, pdf_path: str) -> None:
        """Export PDF through Word's fixed-format API, with SaveAs fallback."""
        try:
            doc.ExportAsFixedFormat(
                OutputFileName=pdf_path,
                ExportFormat=_WD_EXPORT_FORMAT_PDF,
                OpenAfterExport=False,
                OptimizeFor=_WD_EXPORT_OPTIMIZE_FOR_PRINT,
                Range=_WD_EXPORT_ALL_DOCUMENT,
                Item=_WD_EXPORT_DOCUMENT_CONTENT,
                IncludeDocProps=True,
                KeepIRM=True,
                CreateBookmarks=_WD_EXPORT_CREATE_NO_BOOKMARKS,
                DocStructureTags=False,
                BitmapMissingFonts=True,
                UseISO19005_1=False,
            )
        except Exception:
            doc.SaveAs(pdf_path, FileFormat=_WD_FORMAT_PDF_SAVE_AS)

    def _start_word(self) -> None:
        """
        Launch a NEW Word COM instance using DispatchEx.

        DispatchEx always creates a fresh process instead of attaching to an
        already-running Word window.  This prevents the 'Visible can not be set'
        AttributeError that occurs when Dispatch() reuses an existing instance
        that was opened outside our control (e.g. a leftover from a previous run).
        """
        self._word = win32com.client.DispatchEx("Word.Application")
        # Wrap optional property sets — some Word versions/editions behave
        # differently when running as a server-side COM object.
        try:
            self._word.Visible = False
        except AttributeError:
            pass  # Already hidden; safe to ignore
        self._word.DisplayAlerts = 0        # Suppress ALL dialogs
        self._word.AutomationSecurity = 3   # Disable macros (prevent popup on open)
        
        # Warm up Word by creating and closing a blank document.
        # This pre-loads fonts, print subsystem, etc., making the first
        # actual conversion ~3-5x faster.
        try:
            warmup_doc = self._word.Documents.Add()
            warmup_doc.Close(0)
        except Exception:
            pass  # Non-critical; proceed even if warmup fails

    def _quit_word(self) -> None:
        """Quit Word COM cleanly, ignoring errors if already dead."""
        if self._word is not None:
            try:
                self._word.Quit()
            except Exception:
                pass
            finally:
                self._word = None

    def _restart_word(self) -> None:
        """Quit and restart Word COM to flush memory leaks."""
        self._quit_word()
        time.sleep(1)           # Brief pause to let Word fully exit
        self._start_word()

    def __del__(self) -> None:
        """Destructor safety net: quit Word if caller forgot to call quit()."""
        self._quit_word()


def is_word_installed() -> bool:
    """
    Check if Microsoft Word is available via COM.
    Called at application startup to give user a clear error.

    Returns:
        True if Word is registered and accessible, False otherwise.
    """
    try:
        pythoncom.CoInitialize()
        word = win32com.client.Dispatch("Word.Application")
        word.Quit()
        pythoncom.CoUninitialize()
        return True
    except Exception:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass
        return False
