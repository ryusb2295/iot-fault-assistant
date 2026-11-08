# Start everything for the demo recording WITHOUT VS Code.
# Background services open as minimized windows; only the browser and
# one device terminal need to be on screen.
# Usage (PowerShell, project root):  .\scripts\start_demo.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$py = Join-Path $root ".venv\Scripts\python.exe"

# 0) clean up anything left from previous runs (avoids duplicate workers)
& (Join-Path $PSScriptRoot "stop_demo.ps1")
Start-Sleep 1

# 1) fresh, empty demo DB (never touches the dev DB)
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$db = Join-Path $root "backend\iot_demo_$stamp.sqlite3"
& $py scripts\prepare_presentation_db.py --output $db
$env:IOT_DB_PATH = $db
Write-Host "Demo DB: $db"

$pids = @()
# 2) Mosquitto (skip if something already listens on 1883, e.g. the service)
if (-not (Get-NetTCPConnection -LocalPort 1883 -State Listen -ErrorAction SilentlyContinue)) {
    $mq = "C:\Program Files\mosquitto\mosquitto.exe"
    $pids += (Start-Process $mq -ArgumentList "-v" -WindowStyle Minimized -PassThru).Id
    Write-Host "Mosquitto started"
} else { Write-Host "Mosquitto already running on 1883" }

# 2b) open the visible device window BEFORE the worker, so the demo starts
#     with 0 faults (otherwise the worker times out waiting for the device)
Start-Sleep 1
Start-Process "powershell.exe" -WorkingDirectory $root -ArgumentList "-ExecutionPolicy Bypass -NoExit -File `"$root\scripts\device.ps1`""
Start-Sleep 3

# 3) MQTT worker + FastAPI share the same IOT_DB_PATH (inherited env)
$pids += (Start-Process $py -ArgumentList "-m backend.mqtt_worker" -WorkingDirectory $root -WindowStyle Minimized -PassThru).Id
$pids += (Start-Process $py -ArgumentList "-m uvicorn backend.main:app --host 127.0.0.1 --port 8000" -WorkingDirectory $root -WindowStyle Minimized -PassThru).Id

# 4) Vue dev server
$pids += (Start-Process "cmd.exe" -ArgumentList "/c npm run dev" -WorkingDirectory (Join-Path $root "frontend") -WindowStyle Minimized -PassThru).Id
$pids | Set-Content (Join-Path $root "tmp\demo_pids.txt")

# 5) wait for API
for ($i = 0; $i -lt 30; $i++) {
    try { Invoke-RestMethod http://127.0.0.1:8000/api/health -TimeoutSec 2 | Out-Null; break } catch { Start-Sleep 1 }
}
Write-Host "API ready"

# 6) warm up Ollama so the first AI answer in the video is fast
try {
    $body = @{ model = "exaone3.5:2.4b"; prompt = "ok"; stream = $false; keep_alive = "30m" } | ConvertTo-Json
    Invoke-RestMethod http://127.0.0.1:11434/api/generate -Method Post -Body $body -ContentType "application/json" -TimeoutSec 120 | Out-Null
    Write-Host "Ollama warmed up"
} catch { Write-Host "WARNING: Ollama not reachable. Run 'ollama serve' first." -ForegroundColor Yellow }

Start-Sleep 2
Start-Process "http://localhost:5173"
Write-Host ""
Write-Host "Ready. The RPI-01 device window is already running." -ForegroundColor Green
Write-Host "Restart device later (in that window):  .\scripts\device.ps1"
Write-Host "When finished:                      .\scripts\stop_demo.ps1"
