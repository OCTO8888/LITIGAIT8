# Local OpenAI-Compatible TTS Endpoint

This package adds a local Windows-friendly endpoint for studios that expect the OpenAI `POST /v1/audio/speech` dialect. It is designed for `http://localhost:8000` by default and can proxy self-hosted XTTS-v2 or GPT-SoVITS services, parse SSML, map character/cast voices, render incrementally, and save generated files.

## Quick start on Windows 11

1. Install the .NET 10 SDK.
2. Open PowerShell in this repository.
3. Run:

```powershell
cd tools/local-tts-endpoint
.\scripts\install-local-tts.ps1 -Port 8000
.\scripts\run-local-tts.ps1 -Port 8000
```

The server listens at `http://localhost:8000`. Check `http://localhost:8000/health`.

## OpenAI-compatible request

```powershell
Invoke-WebRequest `
  -Uri http://localhost:8000/v1/audio/speech `
  -Method POST `
  -ContentType 'application/json' `
  -Body '{"model":"xtts-v2","input":"Hello from local synthesis.","voice":"narrator","response_format":"wav"}' `
  -OutFile speech.wav
```

## SSML and multi-narrator cast mode

```json
{
  "input": "<speak><voice name=\"cast.alice\">Alice line.</voice><voice name=\"cast.bob\">Bob line.</voice></speak>",
  "ssml": true,
  "response_format": "wav",
  "incremental": true,
  "save_file": true,
  "response_mode": "json"
}
```

SSML support intentionally focuses on safe local orchestration: text extraction, `<voice name="...">` selection, and chunking. Prosody tags can be added later by forwarding metadata to a capable backend.

## Configuration

Edit `LocalTtsEndpoint/appsettings.json` or set environment variables with the `LOCAL_TTS_` prefix. Important settings:

- `LocalTts:Port`: listening port, default `8000`.
- `LocalTts:OutputDirectory`: where generated files are saved.
- `LocalTts:DefaultEngine`: `kokoro` by default for CPU rendering; `silent` remains for CI; `xtts-v2` and `gpt-sovits` are parked proxy stubs for future GPU/cloud hosts.
- `LocalTts:EngineRedirects`: local safety redirects from GPU-oriented engines such as `xtts-v2`/`gpt-sovits` back to `kokoro` unless remote GPU engines are explicitly allowed.
- `LocalTts:AllowRemoteGpuEngines`: set `true` only for rented NVIDIA GPU backends; keep `false` for the local Iris Xe machine.
- `LocalTts:LexiconPath`: JSON pronunciation lexicon used to route coined names to phoneme spans.
- `LocalTts:Engines`: engine name, type, base URL, model name, and optional headers.
- `LocalTts:Voices`: studio-facing voice names mapped to engine speakers.
- `LocalTts:IncrementalRendering`: chunk long input for incremental rendering.
- `LocalTts:ChunkSizeCharacters`: chunk size for incremental rendering.

Example environment override:

```powershell
$env:LOCAL_TTS_LocalTts__Port = '8010'
$env:LOCAL_TTS_LocalTts__Engines__xtts-v2__BaseUrl = 'http://127.0.0.1:8020'
dotnet run --project .\LocalTtsEndpoint\LocalTtsEndpoint.csproj
```


## Local port verification

The endpoint binds to the configured `LocalTts:Port` value. To verify local availability on multiple ports, run the test suite with the .NET 10 SDK on `PATH`:

```powershell
python -m pytest tools/local-tts-endpoint/tests/test_http_contract.py -q
```

The integration test starts the server on ports `18080`, `18081`, and `18082`, checks `/health`, calls `/v1/audio/speech`, and validates SSML manifest output. For deployment, keep only one long-running instance per port, such as the default `8000`, unless your studio intentionally needs multiple side-by-side local endpoints.

## Backend expectations

For Kokoro, run a local CPU service on `http://127.0.0.1:8880`; `scripts/install-kokoro-backend.ps1` pulls the Kokoro-FastAPI CPU image and `scripts/run-kokoro-backend.ps1` starts it with a `/health` check. If Docker is not available, pass `-PythonFallback` to those scripts to use the in-repo dependency-free CPU backend (`kokoro_cpu_backend.py`) for local conformance testing. The endpoint forwards `model`, `input`, `voice`, `response_format`, `speed`, and `seed`. XTTS-v2 and GPT-SoVITS remain parked proxy stubs for a future rented NVIDIA GPU host; local Intel Iris Xe is not treated as an acceleration target. By default, `EngineRedirects` maps those GPU-oriented model requests back to Kokoro CPU. Set `LOCAL_TTS_LocalTts__AllowRemoteGpuEngines=true` only when those backends are running on a rented NVIDIA machine or other remote GPU host. The built-in `silent` engine is a deterministic WAV placeholder for CI and installation validation when no model server is running. XPU/`torch.xpu`/IPEX/dpnp/oneAPI modes are experimental and unsupported on the target i7-13700H + Intel Iris Xe machine; CPU is the committed compute target.

## File management endpoints

- `GET /health`: service status and configured engines.
- `GET /v1/models`: configured local model names.
- `GET /v1/audio/speech/files`: generated file listing.
- `POST /v1/audio/speech`: returns audio bytes, or JSON manifest when `response_mode` is `json` or `save_file` is true.

## Deployment notes for MASTER_O8O8O

Your i7-13700H and 64 GB RAM are suitable for local orchestration and CPU synthesis. Intel Iris Xe integrated graphics will not accelerate CUDA-only model paths, so run GPU-heavy XTTS-v2/GPT-SoVITS backends in CPU mode or use an external/NVIDIA host if needed. Keep this endpoint as the stable studio URL while swapping backend engines behind it.


## SSML compiler and manifests

The orchestrator now lowers SSML into manifest spans before synthesis. Supported tags include `<break>` as real inserted silence, `<prosody rate>` as engine speed, `<prosody volume>` as post-synthesis gain, `<say-as>` normalization, `<phoneme alphabet="ipa" ph="...">` phoneme routing, `<sub alias>`, `<voice name>`, and best-effort `<emphasis>`. Unknown tags degrade to inner text and are recorded as manifest warnings instead of failing the render. Each span records a content hash, `ssml_hash`, voice, engine, seed, render time, rendition hash, and audio file id so unchanged spans can be reused on re-render.

## Audiobook finishing

Use `scripts/finish-audiobook.ps1` after chapter WAVs are rendered. It uses `ffmpeg` to trim leading/trailing silence, loudness-normalize toward audiobook delivery (`I=-19`, `TP=-3`, `LRA=11`), produce per-chapter AAC files, and assemble `audiobook.m4b`. Kokoro native output is 24 kHz; any 44.1/48 kHz distribution resampling belongs in this finishing stage, not in the engine.


## Backend conformance and STT gates

`tests/test_external_gates.py` starts the in-repo CPU Kokoro-compatible backend automatically when `KOKORO_BASE_URL` is not set, so the conformance test executes by default instead of skipping. To test a real Kokoro-FastAPI CPU backend, start it on `:8880` and run with `KOKORO_BASE_URL=http://127.0.0.1:8880`. The STT round-trip gate is wired behind `RUN_STT_GATE=1`; install a CPU faster-whisper-compatible CLI (`faster-whisper` or `whisper-ctranslate2`) and optionally set `STT_WER_THRESHOLD` to override the default `0.25`.


## Pronunciation lexicon and rented GPU routing

`lexicon.json` contains coined-name pronunciation overrides for OBOBO, SHEN, NEMRA, HAMARETH, and JOMM. During SSML lowering, matching words are split into phoneme spans so Kokoro/misaki/espeak-compatible backends can pronounce manuscript-specific proper nouns deterministically. The local machine should stay on CPU/Kokoro. If you rent an NVIDIA GPU backend for XTTS-v2 or GPT-SoVITS, point the relevant `LocalTts:Engines:*:BaseUrl` to that host and set `LOCAL_TTS_LocalTts__AllowRemoteGpuEngines=true`; otherwise those engine requests are redirected to Kokoro CPU.

## PowerShell curl alias troubleshooting

In Windows PowerShell, `curl` is an alias for `Invoke-WebRequest`, not the real curl executable. In non-interactive Docker/PowerShell sessions this can fail with `Windows PowerShell is in NonInteractive mode. Read and Prompt functionality is not available.` Use one of these instead:

```powershell
curl.exe http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/health
Invoke-WebRequest -UseBasicParsing http://localhost:8000/health
```

The root URL `http://localhost:8000/` now returns a small JSON service index so a browser or `curl.exe` can verify the endpoint without posting audio JSON.

## Platform A: local Windows CPU path

Platform A is the local MASTER_O8O8O path: Windows, i7-13700H, Intel Iris Xe, 64 GB RAM, and CPU-committed Kokoro rendering. `appsettings.platform-a.json` records the intended local profile: `RenderPlatform=platform-a-local-cpu`, `DefaultEngine=kokoro`, `AllowRemoteGpuEngines=false`, and redirects from rented-GPU engines back to Kokoro. Start it with:

```powershell
.\scripts\run-platform-a-local.ps1 -Port 8000
```

Use Platform B/rented NVIDIA only by switching `AllowRemoteGpuEngines=true` and pointing `xtts-v2`/`gpt-sovits` base URLs at the rented host. Do not add local Iris Xe XPU/IPEX/oneAPI acceleration paths for Platform A.

## Listener reachability checklist

If `localhost:8000` is not reachable immediately after launch, wait for the .NET build/startup to finish and verify the listener with:

```powershell
.\scripts\wait-local-tts.ps1 -Port 8000 -TimeoutSeconds 60
curl.exe http://localhost:8000/
```

For Docker, the container must publish the port, for example `-p 8000:8000`. The default bind host is `0.0.0.0` so the endpoint works both inside Docker and on the local Windows host once the port is published. Override with `$env:LOCAL_TTS_LocalTts__BindHost = '127.0.0.1'` only when you intentionally want loopback-only binding.

## Start/stop background listener

If the browser shows `ERR_CONNECTION_REFUSED`, the endpoint process is not listening yet (or Docker did not publish the port). Start a background listener and wait for health with:

```powershell
.\scripts\start-local-tts.ps1 -Port 8000 -TimeoutSeconds 90
curl.exe http://localhost:8000/health
.\scripts\stop-local-tts.ps1
```

The start script writes `.run/local-tts.pid` and `.run/local-tts.log`, sets `LOCAL_TTS_LocalTts__Port`, waits for `/health`, and fails fast with the log path if the listener never starts.

If `start-local-tts.ps1` still fails, run diagnostics and inspect separate stdout/stderr logs:

```powershell
.\scripts\diagnose-local-tts.ps1 -Port 8000
Get-Content .\.run\local-tts.out.log -Tail 80
Get-Content .\.run\local-tts.err.log -Tail 80
```

`ERR_CONNECTION_REFUSED` always means there is no process listening on that host/port from the caller's network namespace; it is not an audio/model error.

## WO-LOCAL-TTS-002 Python orchestrator

The active orchestrator path is now the Python Palmcaster pipeline in `orchestrator/pipeline_orchestrator.py`; the earlier .NET endpoint is retained only as historical scaffolding. The Python orchestrator listens on port `8000` and routes Palmcaster DSL spans to Kokoro on `8880`:

```powershell
python .\kokoro_cpu_backend.py --port 8880
.\scripts\run-python-orchestrator.ps1 -Port 8000 -KokoroUrl http://127.0.0.1:8880
python -m pytest tests/test_pipeline_acceptance.py -q
```

Completion for WO-002 is measured by `tests/test_pipeline_acceptance.py`, including `test_two_speakers_render_as_two_distinct_voices`, and by confirming the orchestrator environment has no `torch` or `torchaudio` packages.
