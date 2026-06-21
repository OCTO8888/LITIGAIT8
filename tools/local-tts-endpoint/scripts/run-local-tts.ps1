param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$env:LOCAL_TTS_LocalTts__Port = [string]$Port
dotnet run --project (Join-Path $root 'LocalTtsEndpoint/LocalTtsEndpoint.csproj')
