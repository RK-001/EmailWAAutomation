@echo off
:: =============================================================================
:: build.bat — Build NoticeAutomation.exe using PyInstaller
::
:: Run from inside BulkNoticeAutomation\ directory:
::   build.bat
::
:: Pre-requisites:
::   1. Python 3.11+ in PATH  (py -3 works)
::   2. pip install -r requirements.txt  (including pyinstaller>=6.0)
::   3. Microsoft Word installed (required by pywin32 COM at runtime)
::   4. (Optional) UPX in PATH for binary compression
::
:: Output:
::   dist\NoticeAutomation\NoticeAutomation.exe
:: =============================================================================

setlocal EnableDelayedExpansion
echo.
echo ============================================================
echo  BulkNoticeAutomation -- PyInstaller Build
echo ============================================================
echo.

:: ── Check Python ──────────────────────────────────────────────────────────────
py -3 --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python launcher py -3 not found. Install Python 3.11+.
    exit /b 1
)
for /f "tokens=*" %%v in ('py -3 --version') do echo Python: %%v

:: ── Check PyInstaller ─────────────────────────────────────────────────────────
py -3 -m PyInstaller --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] PyInstaller not found. Run: py -3 -m pip install pyinstaller^>=6.0
    exit /b 1
)
for /f "tokens=*" %%v in ('py -3 -m PyInstaller --version') do echo PyInstaller: %%v

:: ── Clean previous build ──────────────────────────────────────────────────────
echo.
echo [1/4] Cleaning previous build artefacts...
if exist "build\NoticeAutomation" (
    rmdir /s /q "build\NoticeAutomation"
    echo       Removed build\NoticeAutomation
)
if exist "dist\NoticeAutomation" (
    rmdir /s /q "dist\NoticeAutomation"
    echo       Removed dist\NoticeAutomation
)

:: ── Ensure output and logs folders exist (bundled in the install) ─────────────
echo.
echo [2/4] Ensuring runtime folders exist...
if not exist "output" mkdir output
if not exist "logs"   mkdir logs
if not exist "templates" mkdir templates
echo       Done.

:: ── Run PyInstaller ───────────────────────────────────────────────────────────
echo.
echo [3/4] Running PyInstaller...
echo.
set PYTHONUTF8=1
py -3 -m PyInstaller NoticeAutomation.spec --noconfirm --clean
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] PyInstaller build failed. See output above.
    exit /b 1
)

:: ── Post-build: copy extra runtime files ─────────────────────────────────────
echo.
echo [4/4] Copying runtime assets to dist\NoticeAutomation\ ...

:: Blank output + logs folders next to the exe (not in _internal\)
:: These are user-facing write-able directories.
if not exist "dist\NoticeAutomation\output" mkdir "dist\NoticeAutomation\output"
if not exist "dist\NoticeAutomation\logs"   mkdir "dist\NoticeAutomation\logs"
:: Blank templates folder next to the exe for user-added templates
if not exist "dist\NoticeAutomation\templates" mkdir "dist\NoticeAutomation\templates"
if exist "templates\*.docx" copy /y "templates\*.docx" "dist\NoticeAutomation\templates\" >nul

:: NOTE: config.json is bundled inside _internal\ as the factory default.
:: On first run the app automatically copies it next to the exe so the user
:: can edit it. No manual copy needed here.

:: Copy README if present
if exist "README.md" copy /y "README.md" "dist\NoticeAutomation\README.md" >nul

:: Copy icon if present
if exist "icon.ico" copy /y "icon.ico" "dist\NoticeAutomation\icon.ico" >nul

echo.
echo ============================================================
echo  BUILD COMPLETE
echo  Executable: dist\NoticeAutomation\NoticeAutomation.exe
echo ============================================================
echo.
echo To test:
echo   cd dist\NoticeAutomation
echo   NoticeAutomation.exe
echo.
endlocal
