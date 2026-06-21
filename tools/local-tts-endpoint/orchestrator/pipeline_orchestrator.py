#!/usr/bin/env python3
"""WO-LOCAL-TTS-002 Python Palmcaster orchestrator.

CPU-only, dependency-free HTTP orchestrator for Platform A. It accepts the local
OpenAI-compatible /v1/audio/speech surface, lowers Palmcaster DSL to cast spans,
routes each span to a Kokoro-compatible backend, and assembles deterministic WAV
output/manifest data. It deliberately imports no torch/torchaudio stack.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import request as urlrequest
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VOICE_MAP = {
    "NARRATOR": "af_heart",
    "OBOBO": "am_michael",
    "WENDY": "bf_emma",
    "RAEL": "af_bella",
    "NESEN": "bf_isabella",
    "SHEN": "am_adam",
    "NEMRA": "af_nicole",
    "HAMARETH": "bm_george",
    "JOMM": "bm_lewis",
}
CONSTRAINED_VOICES = {"af_heart", "af_bella", "af_nicole", "af_sarah", "am_adam", "am_michael", "bf_emma", "bf_isabella", "bm_george", "bm_lewis"}
LEXICON = {"OBOBO": "oh-BOH-boh"}
STYLE_SPEED = {"the_question": 0.85}
STYLE_SILENCE = {"chapter_header": (500, 500)}
_CACHE: dict[str, bytes] = {}


@dataclass(frozen=True)
class Span:
    text: str
    speaker: str
    voice_id: str
    style: str | None = None
    phoneme: str | None = None


def sha(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def load_config(config_path: str | None = None) -> dict:
    path = Path(config_path or os.environ.get("PALMCASTER_CONFIG", ROOT / "orchestrator_config.json"))
    if not path.exists():
        return {"voice_pack": "constrained", "voices": DEFAULT_VOICE_MAP, "lexicon": LEXICON, "styles": {}}
    with path.open("r", encoding="utf-8-sig") as f:
        config = json.load(f)
    config.setdefault("voice_pack", "constrained")
    voices = {**DEFAULT_VOICE_MAP, **config.get("voices", {})}
    if config["voice_pack"] == "constrained":
        invalid = {k: v for k, v in voices.items() if v not in CONSTRAINED_VOICES}
        if invalid:
            raise ValueError(f"orchestrator_config.json maps studio voices to unavailable constrained Kokoro voices: {invalid}")
    config["voices"] = voices
    config["lexicon"] = {**LEXICON, **config.get("lexicon", {})}
    return config


def apply_lexicon(text: str, lexicon: dict[str, str] | None = None) -> tuple[str, bool]:
    applied = False
    for surface, respelling in (lexicon or LEXICON).items():
        text, count = re.subn(rf"\b{re.escape(surface)}\b", respelling, text)
        applied = applied or count > 0
    return text, applied


def parse_palmcaster_dsl(text: str, voice_map: dict[str, str], lexicon: dict[str, str] | None = None) -> list[Span]:
    text = text.lstrip("\ufeff").replace("\r\n", "\n")
    spans: list[Span] = []
    token = re.compile(r"\{(speaker|style):([^{}]+)\}|\{/(speaker|style)\}")
    speaker_stack = ["NARRATOR"]
    style_stack: list[str | None] = [None]
    cursor = 0
    for match in token.finditer(text):
        emit = text[cursor:match.start()]
        _append_text_span(spans, emit, speaker_stack[-1], style_stack[-1], voice_map, lexicon)
        if match.group(1) == "speaker":
            speaker_stack.append(match.group(2).strip())
        elif match.group(1) == "style":
            style_stack.append(match.group(2).strip())
        elif match.group(3) == "speaker" and len(speaker_stack) > 1:
            speaker_stack.pop()
        elif match.group(3) == "style" and len(style_stack) > 1:
            style_stack.pop()
        cursor = match.end()
    _append_text_span(spans, text[cursor:], speaker_stack[-1], style_stack[-1], voice_map, lexicon)
    return spans


def _append_text_span(spans: list[Span], raw: str, speaker: str, style: str | None, voice_map: dict[str, str], lexicon: dict[str, str] | None = None) -> None:
    raw = re.sub(r"^#+\s+.*$", " ", raw, flags=re.MULTILINE)
    raw = re.sub(r"\{lex:([^{}]+)\}", lambda m: m.group(1), raw)
    cleaned = " ".join(raw.split())
    if not cleaned:
        return
    text, _ = apply_lexicon(cleaned, lexicon)
    spans.append(Span(text, speaker, voice_map.get(speaker, voice_map["NARRATOR"]), style))

def wav_concat(wavs: list[bytes]) -> bytes:
    if not wavs:
        return make_silence(0.25)
    sample_rate = struct.unpack("<I", wavs[0][24:28])[0]
    pcm = b"".join(wav[44:] for wav in wavs)
    return wav_header(sample_rate, len(pcm)) + pcm


def wav_header(sample_rate: int, data_size: int) -> bytes:
    return b"RIFF" + struct.pack("<I", 36 + data_size) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16) + b"data" + struct.pack("<I", data_size)


def make_silence(seconds: float, sample_rate: int = 24000) -> bytes:
    pcm = b"\x00\x00" * int(seconds * sample_rate)
    return wav_header(sample_rate, len(pcm)) + pcm


class PipelineOrchestrator:
    def __init__(self, kokoro_base_url: str, config: dict | None = None):
        self.kokoro_base_url = kokoro_base_url.rstrip("/")
        self.config = config or load_config()
        self.voice_map = self.config.get("voices", DEFAULT_VOICE_MAP)
        self.lexicon = self.config.get("lexicon", LEXICON)
        self.styles = self.config.get("styles", {})

    def style_speed(self, style: str | None, default: float = 1.0) -> float:
        if style and isinstance(self.styles.get(style), dict) and "speed" in self.styles[style]:
            return float(self.styles[style]["speed"])
        return STYLE_SPEED.get(style or "", default)

    def style_silence(self, style: str | None) -> tuple[int, int]:
        configured = self.styles.get(style or "")
        if isinstance(configured, dict):
            return int(configured.get("lead_silence_ms", 0)), int(configured.get("trail_silence_ms", 0))
        return STYLE_SILENCE.get(style or "", (0, 0))

    def render(self, payload: dict) -> tuple[bytes, dict]:
        started = time.time()
        input_text = payload.get("input")
        if not isinstance(input_text, str) or not input_text.strip():
            raise ValueError("input is required")
        input_format = payload.get("input_format", payload.get("inputFormat", "text"))
        if input_format == "palmcaster-dsl":
            spans = parse_palmcaster_dsl(input_text, self.voice_map, self.lexicon)
        else:
            voice = str(payload.get("voice", "NARRATOR"))
            plain, _ = apply_lexicon(" ".join(input_text.split()), self.lexicon)
            spans = [Span(plain, voice, self.voice_map.get(voice, voice))]
        audios: list[bytes] = []
        segments = []
        rendered_segments = 0
        cached_segments = 0
        for span in spans:
            lead_ms, trail_ms = self.style_silence(span.style)
            if lead_ms:
                segments.append({"kind": "silence", "duration_ms": lead_ms, "source": "structural"})
            segment_id = sha(f"{span.speaker}|{span.voice_id}|{span.text}|{span.style}")
            cache_hit = segment_id in _CACHE
            if cache_hit:
                cached_segments += 1
                audio = _CACHE[segment_id]
            else:
                rendered_segments += 1
                audio = self._render_span(span, payload)
                _CACHE[segment_id] = audio
            audios.append(audio)
            lex_applied = any(respelling in span.text for respelling in self.lexicon.values())
            segments.append({
                "kind": "speech",
                "studio_voice": span.speaker,
                "voice": span.voice_id,
                "engine": "kokoro",
                "speed": self.style_speed(span.style),
                "text": span.text,
                "lexicon_applied": lex_applied,
                "segment_id": segment_id,
                "audio_hash": sha(audio),
                "bytes": len(audio),
            })
            if trail_ms:
                segments.append({"kind": "silence", "duration_ms": trail_ms, "source": "structural"})
        audio = wav_concat(audios)
        manifest = {
            "id": sha(input_text)[:16],
            "input_format": input_format,
            "engine": "kokoro",
            "backend": self.kokoro_base_url,
            "render_time_ms": int((time.time() - started) * 1000),
            "rendition_hash": sha(audio),
            "segments": segments,
            "rendered_segments": rendered_segments,
            "cached_segments": cached_segments,
            "audio_format": "wav",
        }
        return audio, manifest

    def _render_span(self, span: Span, payload: dict) -> bytes:
        body = json.dumps({
            "model": "kokoro",
            "input": span.phoneme or span.text,
            "voice": span.voice_id,
            "response_format": payload.get("response_format", "wav"),
            "speed": self.style_speed(span.style, float(payload.get("speed", 1.0))),
        }).encode("utf-8")
        req = urlrequest.Request(f"{self.kokoro_base_url}/v1/audio/speech", data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urlrequest.urlopen(req, timeout=30) as resp:
            return resp.read()


class Handler(BaseHTTPRequestHandler):
    orchestrator: PipelineOrchestrator

    def do_GET(self):
        if self.path.rstrip("/") in ("", "/health"):
            self._json({"status": "ok", "service": "palmcaster-python-orchestrator", "backend": self.orchestrator.kokoro_base_url})
        elif self.path.rstrip("/") == "/v1/voices":
            self._json({"voices": self.orchestrator.voice_map})
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path.rstrip("/") != "/v1/audio/speech":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("content-length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            audio, manifest = self.orchestrator.render(payload)
            if payload.get("response_mode") == "json" or payload.get("responseMode") == "json":
                self._json(manifest)
                return
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(audio)))
            self.end_headers()
            self.wfile.write(audio)
        except (ValueError, HTTPError) as exc:
            self._json({"detail": str(exc)}, status=400)

    def _json(self, payload: dict, status: int = 200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


def run(host: str, port: int, kokoro_base_url: str, config_path: str | None = None):
    Handler.orchestrator = PipelineOrchestrator(kokoro_base_url, load_config(config_path))
    ThreadingHTTPServer((host, port), Handler).serve_forever()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("PALMCASTER_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PALMCASTER_PORT", "8000")))
    parser.add_argument("--kokoro-url", default=os.environ.get("KOKORO_BASE_URL", "http://127.0.0.1:8880"))
    parser.add_argument("--config", default=os.environ.get("PALMCASTER_CONFIG"))
    args = parser.parse_args()
    run(args.host, args.port, args.kokoro_url, args.config)


if __name__ == "__main__":
    main()
