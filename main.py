"""
main.py
-------
Entry point for BulkNoticeAutomation desktop application.

Responsibilities:
  - Set Windows per-monitor DPI awareness BEFORE any window is created
    (required for crisp rendering on high-DPI / 4K displays)
  - Initialize CustomTkinter appearance
  - Launch the main application window

Must be invoked as:
    python main.py                   (development)
    NoticeAutomation.exe             (PyInstaller build)
"""

import ctypes
import sys


def _set_dpi_awareness() -> None:
    """
    Enable per-monitor DPI awareness on Windows.
    This must be called BEFORE any Tkinter/CTk window is created.
    Silently ignored on Linux/macOS.
    """
    if sys.platform != "win32":
        return
    try:
        # PROCESS_PER_MONITOR_DPI_AWARE = 2 (Windows 8.1 / shcore.dll)
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            # Fallback: PROCESS_SYSTEM_DPI_AWARE (Windows Vista+)
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass   # Non-Windows or very old Windows — skip silently


# DPI awareness must be set before ANY window-creation import
_set_dpi_awareness()

import customtkinter as ctk  # noqa: E402 (must import after DPI set)
from ui.app import BulkNoticeApp  # noqa: E402


def main() -> None:
    # "System" follows the OS dark/light mode toggle automatically
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    app = BulkNoticeApp()
    app.mainloop()


if __name__ == "__main__":
    main()
