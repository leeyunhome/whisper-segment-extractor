@echo off
chcp 65001 > nul
REM ============================================================================
REM EBS Auto Download + Extract - All in one
REM
REM Usage:
REM   run_all.bat                       (latest episode)
REM   run_all.bat --episode 2707        (specific episode)
REM   run_all.bat --episode 2658-2661   (episode range)
REM   run_all.bat --episode 2700,2705   (multiple)
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

python run_all.py %*

echo.
echo ================================================================================
echo  Done
echo ================================================================================
pause
