#!/usr/bin/env python3
"""Tiny CPU-only OpenAI-compatible Kokoro development backend.

This is a dependency-free local backend for contract testing and offline wiring. It
uses deterministic voice-dependent tones so conformance tests can verify non-silent,
distinct, 24 kHz WAV output without CUDA/XPU or cloud services. For production,
use Kokoro-FastAPI CPU on the same OpenAI-compatible routes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SAMPLE_RATE = 24000


def wav_tone(text: str, voice: str, speed: float) -> bytes:
    duration = max(0.8, min(12.0, len(text) * 0.055 / max(0.5, min(speed, 1.6))))
    voice_hash = int(hashlib.sha256(voice.encode("utf-8")).hexdigest()[:8], 16)
    frequency = 180 + voice_hash % 420
    frames = int(SAMPLE_RATE * duration)
    pcm = bytearray()
    envelope = min(1200, max(1, frames // 20))
    for index in range(frames):
        fade_in = min(1.0, index / envelope)
        fade_out = min(1.0, (frames - index - 1) / envelope)
        amp = 0.22 * min(fade_in, fade_out)
        value = int(32767 * amp * math.sin(2 * math.pi * frequency * index / SAMPLE_RATE))
        pcm.extend(struct.pack("<h", value))
    data_size = len(pcm)
    header = b"RIFF" + struct.pack("<I", 36 + data_size) + b"WAVEfmt "
    header += struct.pack("<IHHIIHH", 16, 1, 1, SAMPLE_RATE, SAMPLE_RATE * 2, 2, 16)
    header += b"data" + struct.pack("<I", data_size)
    return header + bytes(pcm)


class BackendValidationError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.rstrip("/") == "/health":
            self._json({"status": "ok", "service": "kokoro-dev-cpu", "sample_rate": SAMPLE_RATE})
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path.rstrip("/") != "/v1/audio/speech":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("content-length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            text, voice, speed = self._validate_payload(payload)
            audio = wav_tone(text, voice, speed)
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(audio)))
            self.end_headers()
            self.wfile.write(audio)
        except json.JSONDecodeError as exc:
            self._error(400, f"invalid JSON body: {exc.msg}")
        except BackendValidationError as exc:
            self._error(exc.status, exc.detail)

    def _validate_payload(self, payload):
        if not isinstance(payload, dict):
            raise BackendValidationError(400, "request body must be a JSON object")
        text = payload.get("input")
        if not isinstance(text, str) or not text.strip():
            raise BackendValidationError(400, "input is required and must be a non-empty string")
        voice = payload.get("voice", "af_heart")
        if not isinstance(voice, str) or not voice.strip():
            raise BackendValidationError(400, "voice must be a non-empty string")
        response_format = payload.get("response_format", payload.get("responseFormat", "wav"))
        if response_format != "wav":
            raise BackendValidationError(400, "kokoro dev backend supports response_format=wav only")
        try:
            speed = float(payload.get("speed", 1.0))
        except (TypeError, ValueError) as exc:
            raise BackendValidationError(400, "speed must be numeric") from exc
        if not 0.5 <= speed <= 1.6:
            raise BackendValidationError(400, "speed must be between 0.5 and 1.6")
        return text, voice, speed

    def _error(self, status, detail):
        body = json.dumps({"detail": detail, "status": status}).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return

    def _json(self, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8880)
    args = parser.parse_args()
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
