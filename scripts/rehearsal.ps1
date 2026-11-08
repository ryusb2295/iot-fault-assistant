# Rehearsal: make the running demo system record REAL faults of all three
# types (RESPONSE_DELAY, INVALID_MESSAGE, CONNECTION_TIMEOUT) by switching the
# device simulator mode. Nothing is inserted into the DB directly.
# Run AFTER start_demo.ps1, from the project root:
#   powershell -ExecutionPolicy Bypass -File .\scripts\rehearsal.ps1
$ErrorActionPreference = "Stop"
trap { Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*raspberry_pi.device_simulator*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; Write-Host "Rehearsal failed: $_" -ForegroundColor Red; break }
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
$api = "http://127.0.0.1:8000/api"

function Stop-Device {
    Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*raspberry_pi.device_simulator*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}
function Start-Mode($mode) {
    Start-Process $py -ArgumentList "-m raspberry_pi.device_simulator --mode $mode" -WorkingDirectory $root -NoNewWindow -PassThru
}
function Step($text) { Write-Host ""; Write-Host "== $text" -ForegroundColor Cyan }

try { Invoke-RestMethod "$api/health" -TimeoutSec 3 | Out-Null }
catch { Write-Host "API not running. Run start_demo.ps1 first." -ForegroundColor Red; exit 1 }

Stop-Device
Start-Sleep 1

Step "1/6 normal (8s)"
$p = Start-Mode normal; Start-Sleep 8; Stop-Process -Id $p.Id -Force

Step "2/6 delay mode: device answers after 4.2s -> RESPONSE_DELAY"
$p = Start-Mode delay
$t0 = Get-Date
# keep delay mode until 2+ delay faults exist and all are recovered.
# Stop right when a NEW recovery is observed (just after a late response,
# before the next request), so no request is left unanswered.
# (no date parsing: works with any Windows locale)
$prevRecovered = 0
while ($true) {
    Start-Sleep -Milliseconds 300
    $all = Invoke-RestMethod "$api/events" -TimeoutSec 3      # assign first (PS 5.1 array quirk)
    $ev = @($all | ForEach-Object { $_ } | Where-Object { $_.faultType -eq "RESPONSE_DELAY" })
    $recovered = @($ev | Where-Object { $_.recoveredAt }).Count
    $open = $ev.Count - $recovered
    if ($recovered -gt $prevRecovered) {
        if ($recovered -ge 2 -and $open -eq 0) { break }
        $prevRecovered = $recovered
    }
    if (((Get-Date) - $t0).TotalSeconds -gt 40) { Write-Host "(timeout, continuing)"; break }
}
Stop-Process -Id $p.Id -Force

Step "3/6 normal (8s)"
$p = Start-Mode normal; Start-Sleep 8; Stop-Process -Id $p.Id -Force

Step "4/6 invalid mode: broken JSON / missing fields -> INVALID_MESSAGE (5s)"
$p = Start-Mode invalid; Start-Sleep 5; Stop-Process -Id $p.Id -Force

Step "5/6 normal: valid messages recover INVALID_MESSAGE (8s)"
$p = Start-Mode normal; Start-Sleep 8; Stop-Process -Id $p.Id -Force

Step "6/6 device off 13s -> CONNECTION_TIMEOUT"
Start-Sleep 13

Step "Reopening the RPI-01 device window (normal) -> recovery"
Start-Process "powershell.exe" -WorkingDirectory $root -ArgumentList "-ExecutionPolicy Bypass -NoExit -File `"$root\scripts\device.ps1`""
Start-Sleep 4
$all = Invoke-RestMethod "$api/events"
Write-Host ""
$all | ForEach-Object { $_ } | Select-Object id, faultType, @{n="recovered";e={[bool]$_.recoveredAt}} | Format-Table -AutoSize
Write-Host "Done. Close the OLD device window if it is still open." -ForegroundColor Green
