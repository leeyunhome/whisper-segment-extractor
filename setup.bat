@echo off
chcp 65001 > nul
REM ============================================================================
REM Initial setup
REM ============================================================================

echo.
echo ================================================================================
echo  EBS Automation - Initial Setup
echo ================================================================================
echo.
echo Installing required packages to whisper_env:
echo   - playwright (browser automation)
echo   - python-dotenv (env management)
echo   - pyautogui + pygetwindow (GUI automation)
echo   - faster-whisper (speech recognition)
echo   - inaSpeechSegmenter + tensorflow (music/speech detection)
echo   - pydub (audio processing)
echo.
pause

call conda activate whisper_env
if errorlevel 1 (
    echo [ERROR] whisper_env activate failed
    pause
    exit /b 1
)

cd /d "%~dp0"

echo.
echo [1/4] Installing Python packages...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] pip install failed
    pause
    exit /b 1
)

echo.
echo [2/4] Installing Chromium browser...
playwright install chromium
if errorlevel 1 (
    echo [ERROR] Chromium install failed
    pause
    exit /b 1
)

echo.
echo [3/4] Setting up .env...
if exist .env (
    echo [OK] .env exists
) else (
    if exist .env.example (
        copy .env.example .env
        echo [OK] Copied .env.example to .env
        echo.
        echo IMPORTANT: Edit .env with your EBS credentials!
        pause
        notepad .env
    )
)

echo.
echo [4/4] Done!
echo.
echo Next: run.bat or run.bat --episode 2707
pause
