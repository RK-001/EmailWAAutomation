# -*- mode: python ; coding: utf-8 -*-
# NoticeAutomation.spec — PyInstaller build spec
# Build: pyinstaller NoticeAutomation.spec --noconfirm --clean

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

SPEC_DIR = os.path.abspath(os.path.dirname(SPEC))
MAIN_PY  = os.path.join(SPEC_DIR, "main.py")

# Hidden imports — only those PyInstaller cannot auto-detect
hidden_imports = [
    # pywin32 COM (loaded dynamically via Dispatch)
    "win32com.client", "pythoncom", "pywintypes", "win32api",
    # google-api-python-client (discovery loaded at runtime)
    "googleapiclient.discovery", "googleapiclient.http",
    "google.oauth2.service_account", "google.oauth2.credentials",
    "google.auth.transport.requests", "google.auth.exceptions",
    "google_auth_httplib2",
    # OAuth user login for personal Google Drive accounts
    "google_auth_oauthlib.flow",
    # PIL loaded by customtkinter
    "PIL._tkinter_finder",
] + collect_submodules("customtkinter") \
  + collect_submodules("google_auth_oauthlib") \
  + collect_submodules("requests_oauthlib") \
  + collect_submodules("oauthlib")

# Data files — themes, CA certs, templates, and factory config.
# Google discovery docs are intentionally not bundled; Drive uses runtime
# discovery with static_discovery=False to keep the desktop package smaller.
datas = (
    collect_data_files("customtkinter")
    + collect_data_files("certifi")
    + [
        (os.path.join(SPEC_DIR, "templates"), "templates"),
        (os.path.join(SPEC_DIR, "factory_config", "config.json"), "."),
    ]
)

a = Analysis(
    [MAIN_PY],
    pathex=[SPEC_DIR],
    hookspath=[os.path.join(SPEC_DIR, "hooks")],
    datas=datas,
    hiddenimports=hidden_imports,
    excludes=[
        "pytest","pdb", "pydoc",
        "matplotlib", "numpy", "pandas", "scipy", "torch", "tensorflow",
        # Optional GUI/dev modules that pywin32/Pillow hooks can pull in.
        "Pythonwin", "win32ui",
        # Platform-specific darkdetect probes; this app is built for Windows.
        "darkdetect._linux_detect", "darkdetect._mac_detect",
        "PIL._avif", "PIL.AvifImagePlugin",
        "PIL._webp", "PIL.WebPImagePlugin",
        "PIL.ImageQt",
        "lxml.objectify", "lxml.html", "lxml.isoschematron", "lxml.sax",
    ],
    noarchive=False,
)

a.datas = [
    item for item in a.datas
    if "googleapiclient\\discovery_cache\\documents" not in item[0].replace("/", "\\")
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="NoticeAutomation",
    debug=False,
    upx=True,
    console=False,
    icon=os.path.join(SPEC_DIR, "icon.ico") if os.path.exists(
        os.path.join(SPEC_DIR, "icon.ico")) else None,
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    upx=True,
    name="NoticeAutomation",
)
