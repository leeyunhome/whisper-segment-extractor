@echo off
chcp 65001 > nul
REM ============================================================================
REM EBS Whisper Daily Extractor - 작업 스케줄러 등록 런처
REM 매일 저녁 8시(20:00)에 실행되도록 등록합니다.
REM ============================================================================

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0register_task.ps1"

echo.
pause
