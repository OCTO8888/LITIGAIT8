param([int]$Port = 8000)
$ErrorActionPreference = 'Continue'
Write-Host "Checking dotnet..."
Get-Command dotnet | Format-List Source,Version
Write-Host "Checking localhost health..."
try { Invoke-RestMethod -Uri "http://localhost:$Port/health" -TimeoutSec 3 | ConvertTo-Json -Depth 6 } catch { Write-Host "Health failed: $($_.Exception.Message)" }
Write-Host "Checking PID/log files..."
$root = Split-Path -Parent $PSScriptRoot
$stateDir = Join-Path $root '.run'
Get-ChildItem $stateDir -ErrorAction SilentlyContinue | Format-Table FullName,Length,LastWriteTime
Write-Host "Checking matching dotnet processes..."
Get-CimInstance Win32_Process -Filter "name = 'dotnet.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*LocalTtsEndpoint*' } | Select-Object ProcessId,CommandLine | Format-List
Write-Host "If this reports connection refused, start with: .\scripts\start-local-tts.ps1 -Port $Port -TimeoutSeconds 90"
