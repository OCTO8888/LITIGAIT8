param([string]$PidFile = '')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not $PidFile) { $PidFile = Join-Path $root '.run/local-tts.pid' }
if (-not (Test-Path $PidFile)) { Write-Host "No LocalTtsEndpoint PID file found at $PidFile"; exit 0 }
$pidValue = Get-Content $PidFile
$process = Get-Process -Id ([int]$pidValue) -ErrorAction SilentlyContinue
if ($process) {
  Stop-Process -Id $process.Id -Force
  Write-Host "Stopped LocalTtsEndpoint PID $pidValue"
}
Remove-Item $PidFile -ErrorAction SilentlyContinue
