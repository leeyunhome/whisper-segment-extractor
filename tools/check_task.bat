@echo off
chcp 65001 > nul
REM ============================================================================
REM EBS Whisper Daily Extractor - 작업 스케줄러 등록 상태 확인 스크립트
REM ============================================================================

echo ==========================================================
echo  EBS Whisper Daily Extractor 작업 스케줄러 상태 조회
echo ==========================================================
echo.

schtasks /query /tn "EBS_Whisper_Daily_Extractor" /fo LIST /v

if errorlevel 1 (
    echo.
    echo [WARN] 작업이 등록되어 있지 않습니다.
    echo tools\register_task.bat 를 실행하여 등록하세요.
)

echo.
pause
