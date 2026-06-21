param(
  [string]$Image = 'ghcr.io/remsky/kokoro-fastapi-cpu:latest',
  [string]$ContainerName = 'local-kokoro-cpu',
  [int]$Port = 8880,
  [switch]$PythonFallback
)
$ErrorActionPreference = 'Stop'
$health = "http://127.0.0.1:$Port/health"
if (-not $PythonFallback -and (Get-Command docker -ErrorAction SilentlyContinue)) {
  $existing = docker ps -aq --filter "name=^/$ContainerName$"
  if ($existing) { docker rm -f $ContainerName | Out-Null }
  docker run --name $ContainerName -p "$Port`:8880" -d $Image | Out-Null
} else {
  $backend = Join-Path (Split-Path -Parent $PSScriptRoot) 'kokoro_cpu_backend.py'
  $proc = Start-Process -FilePath python -ArgumentList @($backend, '--port', [string]$Port) -PassThru -WindowStyle Hidden
  Write-Host "Started in-repo CPU backend with PID $($proc.Id)"
}
for ($i = 0; $i -lt 60; $i++) {
  try {
    Invoke-RestMethod -Uri $health -TimeoutSec 2 | Out-Null
    Write-Host "Kokoro CPU backend is healthy at $health"
    exit 0
  } catch { Start-Sleep -Seconds 1 }
}
throw "Kokoro CPU backend did not become healthy at $health"
