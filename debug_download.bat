@echo off
chcp 65001 > nul
REM ============================================================================
REM Debug mode - Download trigger only, slowly
REM ============================================================================

echo.
echo ================================================================================
echo  EBS Auto Download (Debug Mode)
echo ================================================================================
echo  - Slow motion enabled
echo  - Browser stays open (close manually or Ctrl+C)
echo ================================================================================
echo.

call conda activate whisper_env
if errorlevel 1 (
    echo [ERROR] Failed to activate whisper_env
    pause
    exit /b 1
)

cd /d "%~dp0"

python ebs_auto_download.py --slow-mo 800 --keep-open

pause
