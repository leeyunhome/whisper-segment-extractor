@echo off
chcp 65001 > nul
REM ============================================================================
REM EBS Whisper Daily Scheduler (매일 저녁 8시 자동 실행 스크립트)
REM
REM 새 회차를 확인하고, 미처리된 회차가 있을 때만 Whisper 전사 파이프라인 가동.
REM
REM 수동 실행 옵션 예시:
REM   cron_run.bat             (기본 실행: 최대 3회차 처리)
REM   cron_run.bat --dry-run   (확인만)
REM   cron_run.bat --max-batch 1
REM ============================================================================

cd /d "%~dp0"

call conda activate whisper_env
if errorlevel 1 (
    echo [ERROR] Failed to activate conda environment: whisper_env
    exit /b 1
)

set KMP_DUPLICATE_LIB_OK=TRUE
set OMP_NUM_THREADS=1
set MKL_NUM_THREADS=1
set PYTHONIOENCODING=utf-8

python -m src.check_and_run %*

exit /b %errorlevel%
