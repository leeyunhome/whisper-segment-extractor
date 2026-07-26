@echo off
chcp 65001 > nul
REM ============================================================================
REM EBS Auto Download + Extract
REM
REM Usage:
REM   run.bat                       (latest episode)
REM   run.bat --episode 2707        (specific)
REM   run.bat --episode 2658-2661   (range)
REM ============================================================================

echo.
echo ================================================================================
echo  EBS Automation - Download + Extract
echo ================================================================================
echo.

call conda activate whisper_env
if errorlevel 1 (
    echo [ERROR] Failed to activate whisper_env
    pause
    exit /b 1
)

cd /d "%~dp0"

set KMP_DUPLICATE_LIB_OK=TRUE
set OMP_NUM_THREADS=1
set MKL_NUM_THREADS=1

python -m src.runner %*

echo.
echo ================================================================================
echo  Done
echo ================================================================================
pause
