@echo off
chcp 65001 > nul
REM ============================================================================
REM EBS Whisper Daily Extractor - 작업 스케줄러 삭제 스크립트
REM ============================================================================

echo ==========================================================
echo  EBS Whisper Daily Extractor 작업 스케줄러 삭제
echo ==========================================================

schtasks /delete /tn "EBS_Whisper_Daily_Extractor" /f

if errorlevel 1 (
    echo.
    echo [INFO] 등록된 작업이 없거나 이미 삭제되었습니다.
) else (
    echo.
    echo [OK] 작업 스케줄러에서 성공적으로 삭제되었습니다.
)

echo.
pause
