import json
import math
import os
import shutil
import subprocess
import time
import wave
from pathlib import Path
from urllib import error, request

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "kokoro_cpu_backend.py"


def _post_speech(base_url, payload, out_file):
    req = request.Request(
        f"{base_url}/v1/audio/speech",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=60) as response:
        out_file.write_bytes(response.read())


def _wait_health(base_url):
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            with request.urlopen(f"{base_url}/health", timeout=2) as response:
                if response.status == 200:
                    return
        except (error.URLError, TimeoutError):
            time.sleep(0.2)
    raise AssertionError(f"backend did not become healthy at {base_url}")


def _wav_stats(path):
    with wave.open(str(path), "rb") as wav:
        rate = wav.getframerate()
        frames_count = wav.getnframes()
        frames = wav.readframes(frames_count)
    samples = [int.from_bytes(frames[i:i+2], "little", signed=True) for i in range(0, len(frames), 2)]
    rms = math.sqrt(sum(sample * sample for sample in samples) / max(1, len(samples)))
    return rate, frames_count / rate, rms


def _wer(reference, hypothesis):
    ref = reference.lower().split()
    hyp = hypothesis.lower().split()
    dp = [[0] * (len(hyp) + 1) for _ in range(len(ref) + 1)]
    for i in range(len(ref) + 1):
        dp[i][0] = i
    for j in range(len(hyp) + 1):
        dp[0][j] = j
    for i, r in enumerate(ref, 1):
        for j, h in enumerate(hyp, 1):
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + (r != h))
    return dp[-1][-1] / max(1, len(ref))


@pytest.fixture(scope="module")
def kokoro_base_url():
    if "KOKORO_BASE_URL" in os.environ:
        yield os.environ["KOKORO_BASE_URL"].rstrip("/")
        return
    port = "18880"
    process = subprocess.Popen(["python", str(BACKEND), "--port", port], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_health(base_url)
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


def test_kokoro_backend_conformance_two_voices(kokoro_base_url, tmp_path):
    first = tmp_path / "af_heart.wav"
    second = tmp_path / "am_adam.wav"
    _post_speech(kokoro_base_url, {"model": "kokoro", "input": "Kokoro conformance voice one.", "voice": "af_heart", "response_format": "wav"}, first)
    _post_speech(kokoro_base_url, {"model": "kokoro", "input": "Kokoro conformance voice two.", "voice": "am_adam", "response_format": "wav"}, second)
    first_rate, first_duration, first_rms = _wav_stats(first)
    second_rate, second_duration, second_rms = _wav_stats(second)
    assert first_rate == second_rate == 24000
    assert first_duration > 0.75
    assert second_duration > 0.75
    assert first_rms > 50
    assert second_rms > 50
    assert first.read_bytes() != second.read_bytes()


@pytest.mark.skipif("RUN_STT_GATE" not in os.environ, reason="set RUN_STT_GATE=1 with faster-whisper-compatible CLI installed to run STT gate")
def test_stt_round_trip_gate(kokoro_base_url, tmp_path):
    cli = shutil.which("faster-whisper") or shutil.which("whisper-ctranslate2")
    assert cli, "Install faster-whisper or whisper-ctranslate2 for the CPU STT gate"
    source = "Alice waited five seconds then said OBOBO clearly"
    audio = tmp_path / "roundtrip.wav"
    _post_speech(kokoro_base_url, {"model": "kokoro", "input": source, "voice": "af_heart", "response_format": "wav"}, audio)
    result = subprocess.run([cli, str(audio), "--device", "cpu", "--output_format", "json", "--output_dir", str(tmp_path)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    assert result.returncode == 0, result.stdout
    json_files = list(tmp_path.glob("*.json"))
    assert json_files, result.stdout
    payload = json.loads(json_files[0].read_text())
    transcript = payload.get("text") or " ".join(segment.get("text", "") for segment in payload.get("segments", []))
    assert _wer(source, transcript) <= float(os.environ.get("STT_WER_THRESHOLD", "0.25"))


def test_kokoro_backend_validation_errors(kokoro_base_url):
    req = request.Request(
        f"{kokoro_base_url}/v1/audio/speech",
        data=json.dumps({"model": "kokoro", "voice": "af_heart", "response_format": "wav"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(error.HTTPError) as exc:
        request.urlopen(req, timeout=10)
    assert exc.value.code == 400
    payload = json.loads(exc.value.read())
    assert "input is required" in payload["detail"]
