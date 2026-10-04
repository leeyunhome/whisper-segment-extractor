@echo off
chcp 65001 > nul
REM Download trigger only (no extract). For debugging.

echo.
echo ================================================================================
echo  EBS Auto Download (Debug Mode)
echo ================================================================================
echo.

call conda activate whisper_env
if errorlevel 1 (
    echo [ERROR] whisper_env activate failed
    pause
    exit /b 1
)

cd /d "%~dp0"

python -m src.auto_download --slow-mo 800 --keep-open %*

pause
