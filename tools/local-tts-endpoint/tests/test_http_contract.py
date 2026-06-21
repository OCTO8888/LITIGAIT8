import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "LocalTtsEndpoint" / "LocalTtsEndpoint.csproj"


def _request(url, data=None):
    body = None if data is None else json.dumps(data).encode("utf-8")
    headers = {} if data is None else {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=body, headers=headers, method="GET" if data is None else "POST")
    with urllib.request.urlopen(req, timeout=3) as response:
        return response.status, response.headers, response.read()


@pytest.mark.skipif(shutil.which("dotnet") is None, reason="dotnet CLI is not installed")
@pytest.mark.parametrize("port", ["18080", "18081", "18082"])
def test_silent_engine_serves_openai_audio_speech_on_configured_ports(tmp_path, port):
    output_dir = tmp_path / "tts-output"
    env = os.environ.copy()
    env["LOCAL_TTS_LocalTts__Port"] = port
    env["LOCAL_TTS_LocalTts__OutputDirectory"] = str(output_dir)
    env["ASPNETCORE_ENVIRONMENT"] = "Development"

    process = subprocess.Popen(
        ["dotnet", "run", "--no-build", "--project", str(PROJECT)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        base_url = f"http://127.0.0.1:{port}"
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                status, _, body = _request(f"{base_url}/health")
                if status == 200 and b"local-tts-endpoint" in body:
                    break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.25)
        else:
            output = process.stdout.read() if process.stdout else ""
            pytest.fail(f"server did not become healthy; output={output}")

        status, headers, audio = _request(
            f"{base_url}/v1/audio/speech",
            {"model": "silent", "input": "Hello local endpoint.", "voice": "default", "response_format": "wav"},
        )
        assert status == 200
        assert headers.get_content_type() == "audio/wav"
        assert audio[:4] == b"RIFF"
        assert len(audio) > 44

        status, _, manifest = _request(
            f"{base_url}/v1/audio/speech",
            {"model": "silent", "input": "<speak><voice name='cast.alice'>Alice.</voice><voice name='cast.bob'>Bob.</voice></speak>", "ssml": True, "response_mode": "json", "incremental": True},
        )
        payload = json.loads(manifest)
        assert status == 200
        assert len(payload["spans"]) == 2
        assert payload["ssmlHash"]
        assert payload["spans"][0]["spanHash"]
        assert Path(payload["file"]).exists()
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()



@pytest.mark.skipif(shutil.which("dotnet") is None, reason="dotnet CLI is not installed")
def test_ssml_lowering_break_say_as_phoneme_and_unknown_tag(tmp_path):
    port = "18083"
    env = os.environ.copy()
    env["LOCAL_TTS_LocalTts__Port"] = port
    env["LOCAL_TTS_LocalTts__OutputDirectory"] = str(tmp_path / "tts-output")
    process = subprocess.Popen(["dotnet", "run", "--no-build", "--project", str(PROJECT)], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        base_url = f"http://127.0.0.1:{port}"
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                status, _, body = _request(f"{base_url}/health")
                if status == 200 and b"local-tts-endpoint" in body:
                    break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.25)
        else:
            pytest.fail("server did not become healthy")

        ssml = "<speak><voice name='cast.alice'>Call <say-as interpret-as='telephone'>555-0100</say-as>.</voice><break time='500ms'/><phoneme alphabet='ipa' ph='oʊboʊboʊ'>OBOBO</phoneme><unknown>kept text</unknown></speak>"
        status, _, manifest = _request(f"{base_url}/v1/audio/speech", {"model": "silent", "input": ssml, "ssml": True, "response_mode": "json"})
        payload = json.loads(manifest)
        assert status == 200
        assert any(span["kind"] == "silence" and span["silenceMs"] == 500 for span in payload["spans"])
        assert any("unsupported SSML tag <unknown>" in warning for warning in payload["warnings"])
        assert all(span["spanHash"] and span["renditionHash"] for span in payload["spans"])
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()



@pytest.mark.skipif(shutil.which("dotnet") is None, reason="dotnet CLI is not installed")
def test_lexicon_routes_coined_names_to_phoneme_spans(tmp_path):
    port = "18084"
    env = os.environ.copy()
    env["LOCAL_TTS_LocalTts__Port"] = port
    env["LOCAL_TTS_LocalTts__OutputDirectory"] = str(tmp_path / "tts-output")
    process = subprocess.Popen(["dotnet", "run", "--no-build", "--project", str(PROJECT)], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        base_url = f"http://127.0.0.1:{port}"
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                status, _, body = _request(f"{base_url}/health")
                if status == 200 and b"local-tts-endpoint" in body:
                    break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.25)
        else:
            pytest.fail("server did not become healthy")
        ssml = "<speak>OBOBO meets SHEN.</speak>"
        status, _, manifest = _request(f"{base_url}/v1/audio/speech", {"model": "silent", "input": ssml, "ssml": True, "response_mode": "json"})
        payload = json.loads(manifest)
        assert status == 200
        phonemes = [span.get("phoneme") for span in payload["spans"] if span.get("phoneme")]
        assert "oʊboʊboʊ" in phonemes
        assert "ʃɛn" in phonemes
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()



@pytest.mark.skipif(shutil.which("dotnet") is None, reason="dotnet CLI is not installed")
def test_palmcaster_dsl_front_end_routes_speaker_and_lexicon(tmp_path):
    port = "18085"
    env = os.environ.copy()
    env["LOCAL_TTS_LocalTts__Port"] = port
    env["LOCAL_TTS_LocalTts__OutputDirectory"] = str(tmp_path / "tts-output")
    process = subprocess.Popen(["dotnet", "run", "--no-build", "--project", str(PROJECT)], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        base_url = f"http://127.0.0.1:{port}"
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                status, _, body = _request(f"{base_url}/health")
                if status == 200 and b"local-tts-endpoint" in body:
                    break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.25)
        else:
            pytest.fail("server did not become healthy")
        dsl = "\ufeff# Chapter One\n{speaker:RAEL} {style:slow} OBOBO answers {lex:SHEN}."
        status, _, manifest = _request(f"{base_url}/v1/audio/speech", {"model": "silent", "input": dsl, "input_format": "palmcaster-dsl", "response_mode": "json"})
        payload = json.loads(manifest)
        assert status == 200
        assert any(span["voiceId"] == "RAEL" for span in payload["spans"])
        phonemes = [span.get("phoneme") for span in payload["spans"] if span.get("phoneme")]
        assert "oʊboʊboʊ" in phonemes
        assert "ʃɛn" in phonemes
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()



@pytest.mark.skipif(shutil.which("dotnet") is None, reason="dotnet CLI is not installed")
def test_root_endpoint_returns_service_index_for_browser_and_curl(tmp_path):
    port = "18086"
    env = os.environ.copy()
    env["LOCAL_TTS_LocalTts__Port"] = port
    env["LOCAL_TTS_LocalTts__OutputDirectory"] = str(tmp_path / "tts-output")
    process = subprocess.Popen(["dotnet", "run", "--no-build", "--project", str(PROJECT)], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        base_url = f"http://127.0.0.1:{port}"
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                status, _, body = _request(f"{base_url}/")
                if status == 200 and b"Use GET /health" in body:
                    break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.25)
        else:
            pytest.fail("root endpoint did not become available")
        payload = json.loads(body)
        assert payload["service"] == "local-tts-endpoint"
        assert payload["localhost_url"].endswith(f":{port}")
        assert "curl" in payload["powershell"].lower()
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()



@pytest.mark.skipif(shutil.which("dotnet") is None, reason="dotnet CLI is not installed")
def test_platform_a_health_reports_cpu_profile(tmp_path):
    port = "18087"
    env = os.environ.copy()
    env["LOCAL_TTS_LocalTts__Port"] = port
    env["LOCAL_TTS_LocalTts__OutputDirectory"] = str(tmp_path / "tts-output")
    env["LOCAL_TTS_LocalTts__RenderPlatform"] = "platform-a-local-cpu"
    env["LOCAL_TTS_LocalTts__AllowRemoteGpuEngines"] = "false"
    process = subprocess.Popen(["dotnet", "run", "--no-build", "--project", str(PROJECT)], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        base_url = f"http://127.0.0.1:{port}"
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                status, _, body = _request(f"{base_url}/health")
                if status == 200 and b"platform-a-local-cpu" in body:
                    break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.25)
        else:
            pytest.fail("platform A health endpoint did not become available")
        payload = json.loads(body)
        assert payload["platform"] == "platform-a-local-cpu"
        assert payload["allow_remote_gpu_engines"] is False
        assert payload["default_engine"] == "kokoro"
        assert payload["bind_host"] == "0.0.0.0"
        assert payload["localhost_url"].endswith(f":{port}")
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


def _wait_url(url, contains, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            status, _, body = _request(url)
            if status == 200 and contains in body:
                return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.25)
    pytest.fail(f"{url} did not become available")


@pytest.mark.skipif(shutil.which("dotnet") is None, reason="dotnet CLI is not installed")
def test_orchestrator_proxies_to_kokoro_backend(tmp_path):
    backend_port = "18888"
    endpoint_port = "18088"
    backend = subprocess.Popen(["python", str(ROOT / "kokoro_cpu_backend.py"), "--port", backend_port], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    endpoint_env = os.environ.copy()
    endpoint_env["LOCAL_TTS_LocalTts__Port"] = endpoint_port
    endpoint_env["LOCAL_TTS_LocalTts__OutputDirectory"] = str(tmp_path / "tts-output")
    endpoint_env["LOCAL_TTS_LocalTts__Engines__kokoro__BaseUrl"] = f"http://127.0.0.1:{backend_port}"
    endpoint = subprocess.Popen(["dotnet", "run", "--no-build", "--project", str(PROJECT)], cwd=ROOT, env=endpoint_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        _wait_url(f"http://127.0.0.1:{backend_port}/health", b"kokoro-dev-cpu")
        _wait_url(f"http://127.0.0.1:{endpoint_port}/health", b"local-tts-endpoint")
        status, headers, audio = _request(
            f"http://127.0.0.1:{endpoint_port}/v1/audio/speech",
            {"input": "Kokoro proxy verification.", "voice": "narrator", "response_format": "wav"},
        )
        assert status == 200
        assert headers.get_content_type() == "audio/wav"
        assert audio[:4] == b"RIFF"
        assert len(audio) > 24000
    finally:
        endpoint.terminate()
        backend.terminate()
        for process in (endpoint, backend):
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
