# EBS Whisper Extractor - Windows 작업 스케줄러 등록 스크립트
$ErrorActionPreference = "Stop"

$taskName = "EBS_Whisper_Daily_Extractor"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $scriptDir
$batPath = Join-Path $projectDir "cron_run.bat"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " EBS Whisper Extractor - 매일 20:00 자동 작업 등록" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "대상 스크립트: $batPath"

if (-not (Test-Path $batPath)) {
    Write-Host "[ERROR] cron_run.bat 파일을 찾을 수 없습니다: $batPath" -ForegroundColor Red
    exit 1
}

# 1. Action 생성
$action = New-ScheduledTaskAction -Execute $batPath -WorkingDirectory $projectDir

# 2. Trigger 생성 (매일 저녁 8시 / 20:00)
$trigger = New-ScheduledTaskTrigger -Daily -At "20:00"

# 3. Settings 생성
# - WakeToRun: 절전 모드 해제하여 실행
# - StartWhenAvailable: 지정 시간에 PC가 꺼져 있었으면 부팅 후 자동 실행
# - ExecutionTimeLimit: 최대 실행 제한 2시간
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -WakeToRun `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

# 4. Principal 생성 (현재 로그인된 사용자 계정, 대화형 실행 모드)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

# 5. 기존 작업이 있으면 삭제 후 재등록
Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue | Unregister-ScheduledTask -Confirm:$false

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "EBS 영어 방송 새 회차 자동 감지 및 Whisper 전사/배포 (매일 저녁 8시)" | Out-Null

Write-Host ""
Write-Host "✅ 작업 스케줄러에 성공적으로 등록되었습니다!" -ForegroundColor Green
Write-Host "   - 작업 이름: $taskName"
Write-Host "   - 실행 시각: 매일 20:00 (오후 8:00)"
Write-Host "   - 특징: 절전 모드 해제 지원, PC 부팅 시 누락 작업 즉시 실행"
Write-Host "==========================================================" -ForegroundColor Cyan
