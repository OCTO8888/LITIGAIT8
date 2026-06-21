param(
  [string]$Image = 'ghcr.io/remsky/kokoro-fastapi-cpu:latest',
  [string]$ContainerName = 'local-kokoro-cpu',
  [int]$Port = 8880,
  [switch]$PythonFallback
)
$ErrorActionPreference = 'Stop'
if (-not $PythonFallback -and (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Host "Pulling Kokoro CPU backend image $Image"
  docker pull $Image
  Write-Host "Kokoro CPU backend image is installed. Start it with run-kokoro-backend.ps1 -Port $Port"
  exit 0
}
$backend = Join-Path (Split-Path -Parent $PSScriptRoot) 'kokoro_cpu_backend.py'
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Python is required for -PythonFallback when Docker is unavailable.' }
python -m py_compile $backend
Write-Host "Docker unavailable or -PythonFallback requested; verified in-repo CPU backend $backend"
