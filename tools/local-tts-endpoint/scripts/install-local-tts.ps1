param([int]$Port = 8000, [string]$InstallDir = "$env:LOCALAPPDATA\LocalTtsEndpoint")
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
dotnet publish (Join-Path $root 'LocalTtsEndpoint/LocalTtsEndpoint.csproj') -c Release -o $InstallDir
@"
@echo off
set LOCAL_TTS_LocalTts__Port=$Port
"$InstallDir\LocalTtsEndpoint.exe"
"@ | Set-Content -Encoding ASCII (Join-Path $InstallDir 'run-local-tts.cmd')
Write-Host "Installed LocalTtsEndpoint to $InstallDir"
Write-Host "Start with: $InstallDir\run-local-tts.cmd"
