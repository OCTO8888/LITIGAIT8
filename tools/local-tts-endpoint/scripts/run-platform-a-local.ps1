param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$env:LOCAL_TTS_LocalTts__RenderPlatform = 'platform-a-local-cpu'
$env:LOCAL_TTS_LocalTts__AllowRemoteGpuEngines = 'false'
$env:LOCAL_TTS_LocalTts__DefaultEngine = 'kokoro'
$env:LOCAL_TTS_LocalTts__Port = [string]$Port
dotnet run --project (Join-Path $root 'LocalTtsEndpoint/LocalTtsEndpoint.csproj')
