@echo off
chcp 65001 > nul
setlocal

cd /d "%~dp0"

echo.
echo Cleanup Step 1/3: Delete old Python scripts
echo.

del /q analyze_files.py 2>nul
del /q batch_extract_conversation.py 2>nul
del /q check_anchors.py 2>nul
del /q check_mapping.py 2>nul
del /q debug_english.py 2>nul
del /q debug_reproduce_issue.py 2>nul
del /q debug_transcription.py 2>nul
del /q debug_verify_fix.py 2>nul
del /q download_ebs_mp3.py 2>nul
del /q dump_segments_20260102.py 2>nul
del /q dump_segments_direct.py 2>nul
del /q ebs.py 2>nul
del /q extract_conversation.py 2>nul
del /q fast_extract.py 2>nul
del /q find_extraction_pattern.py 2>nul
del /q improved_extract.py 2>nul
del /q investigate_cuts.py 2>nul
del /q investigate_end_20260108.py 2>nul
del /q investigate_start_2026.py 2>nul
del /q manual_timing_check.py 2>nul
del /q pattern_analyzer.py 2>nul
del /q precise_extract.py 2>nul
del /q read_log.py 2>nul
del /q robust_extract.py 2>nul
del /q sample_analyzer.py 2>nul
del /q scan_transcripts.py 2>nul
del /q temp_debug_20260102.py 2>nul
del /q temp_debug_timing.py 2>nul
del /q test_one_file.py 2>nul
del /q test_smart.py 2>nul
del /q v_extract.py 2>nul
del /q verify_fix_20260102.py 2>nul
del /q verify_robust.py 2>nul

del /q smart_extract.py 2>nul
del /q smart_extract.zip 2>nul
del /q ebs_auto_download.py 2>nul
del /q ebs_downloader_clicker.py 2>nul
del /q ebs_episode_info.py 2>nul
del /q watch_and_extract.py 2>nul
del /q run_all.py 2>nul
del /q run_all.bat 2>nul

del /q analysis_log.txt 2>nul
del /q analysis_output.txt 2>nul
del /q analysis_result_utf8.txt 2>nul
del /q debug_end_result.txt 2>nul
del /q debug_out.json 2>nul
del /q debug_output.md 2>nul
del /q debug_output_utf8.md 2>nul
del /q dump_full_2026.txt 2>nul
del /q dump_full_utf8.txt 2>nul
del /q dump_out.txt 2>nul
del /q extract_history.txt 2>nul
del /q install_log.txt 2>nul
del /q investigation_result.txt 2>nul
del /q investigation_start_result.txt 2>nul
del /q timing_analysis.txt 2>nul
del /q transcript_scan_results.txt 2>nul
del /q verify_output.txt 2>nul
del /q segments_22_26.json 2>nul
del /q DEVLOG.md 2>nul
del /q README_AUTOMATION.md 2>nul

del /q "2*.txt" 2>nul
del /q transcription_*.json 2>nul

echo Step 1 done.
echo.

echo Cleanup Step 2/3: Move old results to archive
echo.

if not exist archive mkdir archive

move "2*.mp3" archive\ 2>nul
move "precise_*.mp3" archive\ 2>nul
move "_precise_*.mp3" archive\ 2>nul
move "_script_*.txt" archive\ 2>nul
move "__script_*.txt" archive\ 2>nul
move "_player_*.json" archive\ 2>nul
move candi1.mp3 archive\ 2>nul

move "여행_*.mp3" archive\ 2>nul
move "직업_*.mp3" archive\ 2>nul
move "관계_*.mp3" archive\ 2>nul
move "가정_*.mp3" archive\ 2>nul
move "일상_*.mp3" archive\ 2>nul

move "20251*.mp3" archive\ 2>nul
move "20260101_*.mp3" archive\ 2>nul

echo Step 2 done.
echo.

echo Cleanup Step 3/3: Delete __pycache__
echo.

if exist __pycache__ rmdir /s /q __pycache__
if exist src\__pycache__ rmdir /s /q src\__pycache__
if exist tools\__pycache__ rmdir /s /q tools\__pycache__

echo Step 3 done.
echo.

echo ================================
echo  Cleanup complete!
echo ================================
echo.
echo Verify:
echo   python -m tools.check_gpu
echo   python -m tools.check_mapping
echo.

endlocal
pause
