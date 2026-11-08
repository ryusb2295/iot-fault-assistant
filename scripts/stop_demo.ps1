# Stop every demo process of this project, even ones left over from
# earlier runs (matched by command line, not only by saved PIDs).
$ErrorActionPreference = "SilentlyContinue"
$root = Split-Path -Parent $PSScriptRoot
$patterns = @("backend.mqtt_worker", "backend.main:app", "raspberry_pi.device_simulator", "vite")
$procs = @(Get-CimInstance Win32_Process | Where-Object {
    $cl = $_.CommandLine
    $cl -and ($cl -like "*iot-fault-assistant*" -or $cl -like "*backend.*" -or $cl -like "*raspberry_pi.*") -and
    ($patterns | Where-Object { $cl -like "*$_*" })
})
foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force }
$f = Join-Path $root "tmp\demo_pids.txt"
if (Test-Path $f) {
    Get-Content $f | ForEach-Object { cmd /c "taskkill /T /F /PID $_ >nul 2>&1" }
    Remove-Item $f
}
Write-Host ("Stopped {0} demo process(es)" -f $procs.Count)
