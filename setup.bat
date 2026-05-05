@echo off
chcp 65001 > nul
REM ============================================================================
REM Initial setup - Install packages
REM Run once on first install
REM ============================================================================

echo.
echo ================================================================================
echo  EBS Automation - Initial Setup
echo ================================================================================
echo.
echo Installing required packages to whisper_env:
echo   - playwright (browser automation)
echo   - python-dotenv (env management)
echo   - pyautogui (GUI automation for EBS Downloader button)
echo   - Chromium browser (for Playwright)
echo.
pause

call conda activate whisper_env
if errorlevel 1 (
    echo [ERROR] Failed to activate whisper_env
    pause
    exit /b 1
)

echo.
echo [1/4] Installing playwright + python-dotenv + pyautogui...
pip install playwright python-dotenv pyautogui
if errorlevel 1 (
    echo [ERROR] pip install failed
    pause
    exit /b 1
)

echo.
echo [2/4] Downloading Chromium browser (may take a few minutes)...
playwright install chromium
if errorlevel 1 (
    echo [ERROR] Chromium install failed
    pause
    exit /b 1
)

echo.
echo [3/4] Checking .env file...
cd /d "%~dp0"
if exist .env (
    echo [OK] .env already exists
) else (
    if exist .env.example (
        copy .env.example .env
        echo [OK] Copied .env.example to .env
        echo.
        echo ================================================================================
        echo  IMPORTANT: Open .env and enter your EBS account info!
        echo ================================================================================
        echo.
        pause
        notepad .env
    ) else (
        echo [WARNING] .env.example not found
    )
)

echo.
echo [4/4] All set!
echo ================================================================================
echo.
echo Next steps:
echo   1. Make sure .env has your EBS credentials
echo   2. Run debug_download.bat for first test
echo   3. If working, use run_all.bat for daily use
echo.
pause
