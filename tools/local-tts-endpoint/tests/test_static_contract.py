from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = (ROOT / "LocalTtsEndpoint" / "Program.cs").read_text()
CONFIG = (ROOT / "LocalTtsEndpoint" / "appsettings.json").read_text()
README = (ROOT / "README.md").read_text()


def test_openai_audio_speech_route_exists():
    assert 'MapPost("/v1/audio/speech"' in PROGRAM
    assert 'JsonPropertyName("response_format")' in PROGRAM
    assert 'JsonPropertyName("voice")' in PROGRAM


def test_management_routes_exist():
    assert 'MapGet("/health"' in PROGRAM
    assert 'MapGet("/v1/models"' in PROGRAM
    assert 'MapGet("/v1/audio/speech/files"' in PROGRAM


def test_ssml_cast_incremental_features_are_present():
    assert "XDocument.Parse" in PROGRAM
    assert 'Attribute("name")' in PROGRAM
    assert 'JsonPropertyName("cast")' in PROGRAM
    assert 'JsonPropertyName("incremental")' in PROGRAM
    assert "SplitSegments" in PROGRAM


def test_default_configuration_targets_localhost_8000_and_engines():
    assert '"Port": 8000' in CONFIG
    assert '"DefaultEngine": "kokoro"' in CONFIG
    assert '"kokoro"' in CONFIG
    assert '"xtts-v2"' in CONFIG
    assert '"gpt-sovits"' in CONFIG
    assert '"silent"' in CONFIG


def test_windows_installation_docs_exist():
    assert "install-local-tts.ps1" in README
    assert "run-local-tts.ps1" in README
    assert "install-kokoro-backend.ps1" in README
    assert "run-kokoro-backend.ps1" in README
    assert "finish-audiobook.ps1" in README
    assert "http://localhost:8000" in README


def test_project_targets_dotnet_10():
    project = (ROOT / "LocalTtsEndpoint" / "LocalTtsEndpoint.csproj").read_text()
    assert "<TargetFramework>net10.0</TargetFramework>" in project
    assert "net8.0" not in project


def test_ssml_lowering_and_manifest_features_are_present():
    assert 'case "break"' in PROGRAM
    assert 'case "say-as"' in PROGRAM
    assert 'case "phoneme"' in PROGRAM
    assert 'unsupported SSML tag' in PROGRAM
    assert 'SpanManifest' in PROGRAM
    assert 'SsmlHash' in PROGRAM
    assert 'CacheHit' in PROGRAM


def test_no_unsupported_xpu_path_added():
    combined = PROGRAM + CONFIG
    forbidden = ["torch.xpu", "ipex.optimize", "dpnp", "oneAPI"]
    assert not any(token in combined for token in forbidden)


def test_in_repo_kokoro_backend_and_stt_gate_are_wired():
    assert (ROOT / "kokoro_cpu_backend.py").exists()
    external = (ROOT / "tests" / "test_external_gates.py").read_text()
    assert "def test_kokoro_backend_conformance_two_voices" in external
    assert "def test_stt_round_trip_gate" in external
    assert "RUN_STT_GATE" in external
    assert "_wer" in external


def test_lexicon_and_engine_redirects_are_configured():
    assert (ROOT / "lexicon.v1.json").exists()
    assert '"LexiconPath": "lexicon.v1.json"' in CONFIG
    assert '"AllowRemoteGpuEngines": false' in CONFIG
    assert '"EngineRedirects"' in CONFIG
    assert '"xtts-v2": "kokoro"' in CONFIG
    assert '"gpt-sovits": "kokoro"' in CONFIG
    assert "SourceEngine" in PROGRAM
    assert "LoadLexicon" in PROGRAM


def test_palmcaster_dsl_and_render_appsettings_are_present():
    assert (ROOT / "LocalTtsEndpoint" / "Dsl" / "PalmcasterDslParser.cs").exists()
    assert (ROOT / "LocalTtsEndpoint" / "Lexicon" / "LexiconPrePass.cs").exists()
    assert (ROOT / "LocalTtsEndpoint" / "Lowering" / "RenderPlanBuilder.cs").exists()
    render_settings = (ROOT / "LocalTtsEndpoint" / "appsettings.render.json").read_text()
    assert '''"RAEL": "af_sky"''' in render_settings
    assert '''"NESEN": "bf_emma"''' in render_settings
    assert "palmcaster-dsl" in PROGRAM


def test_root_endpoint_and_powershell_curl_docs_exist():
    assert 'MapGet("/"' in PROGRAM
    assert "GetRoot" in PROGRAM
    assert "curl.exe http://localhost:8000/health" in README
    assert "Invoke-RestMethod http://localhost:8000/health" in README
    assert "-UseBasicParsing" in README


def test_platform_a_local_cpu_profile_is_present():
    platform = (ROOT / "LocalTtsEndpoint" / "appsettings.platform-a.json").read_text()
    assert '''"RenderPlatform": "platform-a-local-cpu"''' in CONFIG
    assert '''"AllowRemoteGpuEngines": false''' in platform
    assert '''"DefaultEngine": "kokoro"''' in platform
    assert "Intel Iris Xe" in platform
    assert "run-platform-a-local.ps1" in README
    assert "allow_remote_gpu_engines" in PROGRAM


def test_listener_bindhost_and_wait_script_exist():
    assert '''"BindHost": "0.0.0.0"''' in CONFIG
    assert "BindHost" in PROGRAM
    assert "listen_url" in PROGRAM
    assert (ROOT / "scripts" / "wait-local-tts.ps1").exists()
    assert "wait-local-tts.ps1" in README
    assert "-p 8000:8000" in README


def test_start_stop_listener_scripts_exist_for_connection_refused():
    assert (ROOT / "scripts" / "start-local-tts.ps1").exists()
    assert (ROOT / "scripts" / "stop-local-tts.ps1").exists()
    start_script = (ROOT / "scripts" / "start-local-tts.ps1").read_text()
    assert "wait-local-tts.ps1" in start_script
    assert "RedirectStandardOutput" in start_script
    assert "LOCAL_TTS_LocalTts__BindHost" in start_script
    assert "ERR_CONNECTION_REFUSED" in README


def test_start_script_uses_separate_logs_and_diagnostics():
    start_script = (ROOT / "scripts" / "start-local-tts.ps1").read_text()
    assert "local-tts.out.log" in start_script
    assert "local-tts.err.log" in start_script
    assert "Get-Command dotnet" in start_script
    assert (ROOT / "scripts" / "diagnose-local-tts.ps1").exists()
    assert "diagnose-local-tts.ps1" in README
    assert "ERR_CONNECTION_REFUSED` always means" in README
