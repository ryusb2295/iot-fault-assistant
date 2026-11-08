# The only terminal shown in the demo video: the simulated device RPI-01.
# Usage: .\scripts\device.ps1            (normal mode)
#        .\scripts\device.ps1 delay      (normal | disconnect | delay | invalid)
param([string]$mode = "normal")
$root = Split-Path -Parent $PSScriptRoot
$Host.UI.RawUI.WindowTitle = "RPI-01 device simulator ($mode)"
Clear-Host
Write-Host "RPI-01  ->  factory/RPI-01/status   mode: $mode" -ForegroundColor Green
& (Join-Path $root ".venv\Scripts\python.exe") -m raspberry_pi.device_simulator --mode $mode
