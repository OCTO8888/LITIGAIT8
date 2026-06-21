param(
  [int]$Port = 8000,
  [string]$BindHost = '0.0.0.0',
  [string]$PidFile = '',
  [string]$LogFile = '',
  [string]$ErrorLogFile = '',
  [int]$TimeoutSeconds = 90,
  [switch]$NoBuild
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$project = Join-Path $root 'LocalTtsEndpoint/LocalTtsEndpoint.csproj'
$stateDir = Join-Path $root '.run'
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
if (-not $PidFile) { $PidFile = Join-Path $stateDir 'local-tts.pid' }
if (-not $LogFile) { $LogFile = Join-Path $stateDir 'local-tts.out.log' }
if (-not $ErrorLogFile) { $ErrorLogFile = Join-Path $stateDir 'local-tts.err.log' }
if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) { throw 'dotnet was not found on PATH. Install .NET 10 SDK or open a shell where dotnet is available.' }
if (Test-Path $PidFile) {
  $oldPid = Get-Content $PidFile -ErrorAction SilentlyContinue
  if ($oldPid) {
    $old = Get-Process -Id ([int]$oldPid) -ErrorAction SilentlyContinue
    if ($old) { throw "LocalTtsEndpoint appears to already be running as PID $oldPid. Stop it first or remove $PidFile." }
  }
}
$env:LOCAL_TTS_LocalTts__Port = [string]$Port
$env:LOCAL_TTS_LocalTts__BindHost = $BindHost
$args = @('run')
if ($NoBuild) { $args += '--no-build' }
$args += @('--project', $project)
$process = Start-Process -FilePath 'dotnet' -ArgumentList $args -PassThru -RedirectStandardOutput $LogFile -RedirectStandardError $ErrorLogFile -WindowStyle Hidden
$process.Id | Set-Content -Encoding ASCII $PidFile
try {
  & (Join-Path $PSScriptRoot 'wait-local-tts.ps1') -Port $Port -TimeoutSeconds $TimeoutSeconds
  Write-Host "LocalTtsEndpoint started. PID=$($process.Id) Log=$LogFile ErrorLog=$ErrorLogFile"
} catch {
  Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
  Remove-Item $PidFile -ErrorAction SilentlyContinue
  Write-Host "stdout log: $LogFile"
  Write-Host "stderr log: $ErrorLogFile"
  throw
}
