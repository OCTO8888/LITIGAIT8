param([int]$Port = 8000, [int]$TimeoutSeconds = 60)
$ErrorActionPreference = 'Stop'
$health = "http://localhost:$Port/health"
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
while ((Get-Date) -lt $deadline) {
  try {
    $result = Invoke-RestMethod -Uri $health -TimeoutSec 2
    Write-Host "LocalTtsEndpoint is reachable at $health"
    $result | ConvertTo-Json -Depth 6
    exit 0
  } catch {
    Start-Sleep -Milliseconds 500
  }
}
throw "LocalTtsEndpoint was not reachable at $health after $TimeoutSeconds seconds. If running in Docker, verify -p $Port`:$Port is published."
