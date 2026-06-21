param([int]$Port = 8000, [string]$KokoroUrl = 'http://127.0.0.1:8880')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$env:PALMCASTER_PORT = [string]$Port
$env:KOKORO_BASE_URL = $KokoroUrl
python (Join-Path $root 'orchestrator/pipeline_orchestrator.py') --port $Port --kokoro-url $KokoroUrl
