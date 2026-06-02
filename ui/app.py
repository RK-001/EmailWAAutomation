"""
ui/app.py
---------
Main application window for BulkNoticeAutomation.

Acts as the central hub:
  - Owns the ConfigManager instance (shared by all tabs)
  - Owns the current batch state (generated rows, batch_id, etc.)
  - Provides inter-tab navigation methods (go_to_preview, go_to_logs)
  - Manages graceful window close (warns if batch is running)

Tab layout:
  ⚙  Setup      → Gmail, AiSensy, Drive credentials + test buttons
  👥  Profiles   → Create / edit / delete client profiles
  📄  Workflow   → Pick Excel + profile → generate all PDFs
  🔍  Preview    → Review generated rows, exclude, then send
  📋  Logs       → Real-time send results, export CSV, retry failed
"""

import queue
import sys
from pathlib import Path

import customtkinter as ctk

from utils.config_manager import ConfigManager

# ── Constants ────────────────────────────────────────────────────────────────

_APP_TITLE = "Bulk Notice Automation  —  Law Firm Edition"
_MIN_WIDTH = 1050
_MIN_HEIGHT = 700


class BulkNoticeApp(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        # ── Resolve base directory (works for .py and PyInstaller .exe) ──────
        if getattr(sys, "frozen", False):
            # Running as a compiled .exe (PyInstaller).
            # PyInstaller 6+ layout:
            #   dist\NoticeAutomation\
            #       NoticeAutomation.exe   ← user-editable files live here
            #       _internal\             ← bundled read-only data (sys._MEIPASS)
            #
            # Strategy for config.json:
            #   1. Always use the copy NEXT TO THE EXE (user edits this).
            #   2. On first run (no config.json next to exe), copy the bundled
            #      default from _internal/ so the user gets a working starting point.
            exe_dir = Path(sys.executable).parent
            internal_dir = Path(sys._MEIPASS)  # type: ignore[attr-defined]

            config_path_candidate = exe_dir / "config.json"
            if not config_path_candidate.exists():
                # First run: bootstrap user config from the bundled default
                bundled_cfg = internal_dir / "config.json"
                if bundled_cfg.exists():
                    import shutil
                    shutil.copy(str(bundled_cfg), str(config_path_candidate))

            base_dir = exe_dir  # output/, logs/ etc. sit next to the exe
        else:
            # Running as a script — use project root (parent of ui/)
            base_dir = Path(__file__).parent.parent

        config_path = str(base_dir / "config.json")

        # ── Shared application state ──────────────────────────────────────────
        self.config_manager = ConfigManager(config_path)
        self.progress_queue: queue.Queue = queue.Queue()

        # Current batch state (set by WorkflowTab after Stage 1 completes)
        self.current_batch: list[dict] = []
        self.current_batch_id: str = ""
        self.current_profile_name: str = ""
        self.current_log_path: str = ""

        # ── Window setup ──────────────────────────────────────────────────────
        self.title(_APP_TITLE)
        self.minsize(_MIN_WIDTH, _MIN_HEIGHT)

        # Center on screen
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w, h = _MIN_WIDTH, _MIN_HEIGHT
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        self._build_ui()

        # Graceful close handler
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build the top-bar, tab view, and status bar."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── Top bar ───────────────────────────────────────────────────────────
        top_bar = ctk.CTkFrame(self, height=44, corner_radius=0)
        top_bar.grid(row=0, column=0, sticky="ew")
        top_bar.grid_columnconfigure(0, weight=1)

        firm_name = self.config_manager.get("settings.firm_name") or "Law Firm"
        self._title_label = ctk.CTkLabel(
            top_bar,
            text=f"⚖  Bulk Notice Automation  |  {firm_name}",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self._title_label.grid(row=0, column=0, pady=10)

        # ── Tab view ──────────────────────────────────────────────────────────
        self.tab_view = ctk.CTkTabview(self, anchor="nw")
        self.tab_view.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 0))

        # Add tabs (order matters — displayed left-to-right)
        for tab_name in ("⚙  Setup", "👥  Profiles", "📄  Workflow", "🔍  Preview", "📋  Logs"):
            self.tab_view.add(tab_name)

        # Import tab classes here (avoids circular imports at module level)
        from ui.setup_tab import SetupTab
        from ui.profiles_tab import ProfilesTab
        from ui.workflow_tab import WorkflowTab
        from ui.preview_tab import PreviewTab
        from ui.log_tab import LogTab

        self.setup_tab = SetupTab(
            self.tab_view.tab("⚙  Setup"),
            app=self,
        )
        self.profiles_tab = ProfilesTab(
            self.tab_view.tab("👥  Profiles"),
            app=self,
        )
        self.workflow_tab = WorkflowTab(
            self.tab_view.tab("📄  Workflow"),
            app=self,
        )
        self.preview_tab = PreviewTab(
            self.tab_view.tab("🔍  Preview"),
            app=self,
        )
        self.log_tab = LogTab(
            self.tab_view.tab("📋  Logs"),
            app=self,
        )

        # ── Status bar ────────────────────────────────────────────────────────
        self._status_var = ctk.StringVar(value="Ready.")
        status_bar = ctk.CTkLabel(
            self,
            textvariable=self._status_var,
            anchor="w",
            font=ctk.CTkFont(size=11),
        )
        status_bar.grid(row=2, column=0, sticky="ew", padx=14, pady=(2, 4))

    # ── Public inter-tab API ──────────────────────────────────────────────────

    def set_status(self, message: str) -> None:
        """
        Update the bottom status bar. Thread-safe (uses after()).
        Called by tabs and workers to show current activity.
        """
        self.after(0, lambda msg=message: self._status_var.set(msg))

    def refresh_title(self) -> None:
        """Re-read firm name from config and update the top bar label."""
        firm_name = self.config_manager.get("settings.firm_name") or "Law Firm"
        self._title_label.configure(text=f"⚖  Bulk Notice Automation  |  {firm_name}")

    def go_to_preview(
        self,
        generated_rows: list[dict],
        batch_id: str,
        profile_name: str,
        log_path: str,
    ) -> None:
        """
        Called by WorkflowTab after Stage 1 (Generate) completes.
        Stores batch state and switches to the Preview tab.

        Args:
            generated_rows:  List of row dicts (each has pdf_path, drive_link added).
            batch_id:        Unique batch identifier string.
            profile_name:    Profile used for this batch.
            log_path:        Path to the JSON log file for this batch.
        """
        self.current_batch = generated_rows
        self.current_batch_id = batch_id
        self.current_profile_name = profile_name
        self.current_log_path = log_path

        self.preview_tab.load_batch(generated_rows, batch_id, profile_name)
        self.tab_view.set("🔍  Preview")

    def go_to_logs(self) -> None:
        """Switch to the Logs tab (called when sending begins)."""
        self.tab_view.set("📋  Logs")

    def notify_profiles_changed(self) -> None:
        """
        Called by ProfilesTab when a profile is created/edited/deleted.
        Refreshes profile dropdowns in WorkflowTab.
        """
        if hasattr(self, "workflow_tab"):
            self.workflow_tab.refresh_profiles()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def _on_close(self) -> None:
        """Warn user if a batch is running before closing."""
        if hasattr(self, "workflow_tab") and self.workflow_tab.is_batch_running():
            from tkinter import messagebox
            if not messagebox.askyesno(
                "Batch Running",
                "A batch is currently running.\n\n"
                "Closing will stop it (progress is saved — you can resume later).\n\n"
                "Close anyway?",
                icon="warning",
            ):
                return
        self.destroy()
