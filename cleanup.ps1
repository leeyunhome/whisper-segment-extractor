# Cleanup script for whisper-segment-extractor
# Run with: .\cleanup.ps1

$ErrorActionPreference = "SilentlyContinue"

Set-Location $PSScriptRoot

Write-Host ""
Write-Host "Cleanup Step 1/3: Delete old Python scripts" -ForegroundColor Cyan
Write-Host ""

$oldScripts = @(
    "analyze_files.py",
    "batch_extract_conversation.py",
    "check_anchors.py",
    "check_mapping.py",
    "debug_english.py",
    "debug_reproduce_issue.py",
    "debug_transcription.py",
    "debug_verify_fix.py",
    "download_ebs_mp3.py",
    "dump_segments_20260102.py",
    "dump_segments_direct.py",
    "ebs.py",
    "extract_conversation.py",
    "fast_extract.py",
    "find_extraction_pattern.py",
    "improved_extract.py",
    "investigate_cuts.py",
    "investigate_end_20260108.py",
    "investigate_start_2026.py",
    "manual_timing_check.py",
    "pattern_analyzer.py",
    "precise_extract.py",
    "read_log.py",
    "robust_extract.py",
    "sample_analyzer.py",
    "scan_transcripts.py",
    "temp_debug_20260102.py",
    "temp_debug_timing.py",
    "test_one_file.py",
    "test_smart.py",
    "v_extract.py",
    "verify_fix_20260102.py",
    "verify_robust.py",
    # Old core (moved to src/)
    "smart_extract.py",
    "smart_extract.zip",
    "ebs_auto_download.py",
    "ebs_downloader_clicker.py",
    "ebs_episode_info.py",
    "watch_and_extract.py",
    "run_all.py",
    "run_all.bat",
    # Logs
    "analysis_log.txt",
    "analysis_output.txt",
    "analysis_result_utf8.txt",
    "debug_end_result.txt",
    "debug_out.json",
    "debug_output.md",
    "debug_output_utf8.md",
    "dump_full_2026.txt",
    "dump_full_utf8.txt",
    "dump_out.txt",
    "extract_history.txt",
    "install_log.txt",
    "investigation_result.txt",
    "investigation_start_result.txt",
    "timing_analysis.txt",
    "transcript_scan_results.txt",
    "verify_output.txt",
    "segments_22_26.json",
    "DEVLOG.md",
    "README_AUTOMATION.md"
)

$deletedCount = 0
foreach ($file in $oldScripts) {
    if (Test-Path $file) {
        Remove-Item $file -Force
        $deletedCount++
    }
}

# Wildcard patterns
Get-ChildItem -Filter "transcription_*.json" -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem -Filter "2*.txt" -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^\d{4}_' -or $_.Name -match '^\d{8}_' } | Remove-Item -Force

Write-Host "  Deleted $deletedCount files + wildcards" -ForegroundColor Green
Write-Host ""

Write-Host "Cleanup Step 2/3: Move old results to archive" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path "archive")) {
    New-Item -ItemType Directory -Path "archive" | Out-Null
}

$movedCount = 0

# MP3 with episode number prefix or date prefix
Get-ChildItem -Filter "*.mp3" | Where-Object {
    $_.Name -match '^\d+_' -or
    $_.Name -match '^precise_' -or
    $_.Name -match '^_precise_' -or
    $_.Name -eq 'candi1.mp3' -or
    $_.Name -match '^(여행|직업|관계|가정|일상)_'
} | ForEach-Object {
    Move-Item $_.FullName -Destination "archive\" -Force
    $movedCount++
}

# Old debug results
Get-ChildItem -Filter "_script_*.txt" | ForEach-Object { Move-Item $_.FullName "archive\" -Force; $movedCount++ }
Get-ChildItem -Filter "__script_*.txt" | ForEach-Object { Move-Item $_.FullName "archive\" -Force; $movedCount++ }
Get-ChildItem -Filter "_player_*.json" | ForEach-Object { Move-Item $_.FullName "archive\" -Force; $movedCount++ }

Write-Host "  Moved $movedCount files to archive\" -ForegroundColor Green
Write-Host ""

Write-Host "Cleanup Step 3/3: Delete __pycache__" -ForegroundColor Cyan
Write-Host ""

@("__pycache__", "src\__pycache__", "tools\__pycache__") | ForEach-Object {
    if (Test-Path $_) {
        Remove-Item -Recurse -Force $_
        Write-Host "  Removed $_" -ForegroundColor Green
    }
}
Write-Host ""

Write-Host "================================" -ForegroundColor Yellow
Write-Host " Cleanup complete!" -ForegroundColor Yellow
Write-Host "================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "Verify with:"
Write-Host "  python -m tools.check_gpu"
Write-Host "  python -m tools.check_mapping"
Write-Host ""
