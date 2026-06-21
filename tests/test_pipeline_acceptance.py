"""
WO-LOCAL-TTS-002 §14 — ACCEPTANCE GATE (the definition of "done").

These tests hit the orchestrator's HTTP API on :8000. They are LANGUAGE-AGNOSTIC
(they do not care whether the orchestrator is Python or .NET) and a Kokoro
*proxy* cannot pass any of them — passing them requires the actual pipeline:
DSL parsing, cast routing, the lexicon pre-pass, style delivery, and a manifest.

"28 passed" on proxy/serialization tests does NOT count. Completion = this file green.

REQUIRED RESPONSE CONTRACT (implement this if it does not exist):
  POST /v1/audio/speech
    body: {"input": <text>, "input_format": "palmcaster-dsl"|"plain",
           "response_mode": "json"|"audio", "response_format": "wav"}
  When response_mode == "json", return:
    {
      "segments": [
        {"kind": "speech", "studio_voice": "OBOBO", "voice": "am_michael",
         "engine": "kokoro", "speed": 1.0, "text": "\"Yes.\"", "lexicon_applied": false},
        {"kind": "silence", "duration_ms": 500, "source": "structural"},
        ...
      ],
      "rendered_segments": <int>,   # engine calls made this request
      "cached_segments": <int>,     # segments served from the content-hash manifest
      "audio_format": "wav"
    }
  (`voice` = the resolved ENGINE voice; `text` = the exact text sent to the engine,
   i.e. AFTER lexicon respelling substitution.)

  GET /v1/voices -> the studio cast (NARRATOR, OBOBO, WENDY, ...), not raw Kokoro ids.

Run:  python -m pytest test_pipeline_acceptance.py -q
Env:  ORCH_URL (default http://127.0.0.1:8000)
"""
import os, requests, pytest

BASE = os.environ.get("ORCH_URL", "http://127.0.0.1:8000")


def _post_dsl(text, fmt="palmcaster-dsl"):
    try:
        r = requests.post(f"{BASE}/v1/audio/speech",
                          json={"input": text, "input_format": fmt,
                                "response_mode": "json", "response_format": "wav"},
                          timeout=120)
    except requests.exceptions.RequestException as e:
        pytest.fail(f"Orchestrator not reachable on {BASE} — is it running? ({e})")
    assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
    return r.json()


def _speech_segments(payload):
    return [s for s in payload.get("segments", []) if s.get("kind") == "speech"]


def test_voices_endpoint_returns_studio_cast():
    """A proxy exposes Kokoro's raw voices; the orchestrator exposes the cast."""
    r = requests.get(f"{BASE}/v1/voices", timeout=30)
    assert r.status_code == 200, r.text[:200]
    body = r.text
    for name in ("NARRATOR", "OBOBO", "WENDY"):
        assert name in body, f"/v1/voices missing studio voice {name!r} — this is a passthrough, not the orchestrator"


def test_two_speakers_render_as_two_distinct_voices():
    """THE proxy-defeating test. Two {speaker:} spans must resolve to different engine voices."""
    payload = _post_dsl('{speaker:OBOBO}"Yes."{/speaker} {speaker:WENDY}"No."{/speaker}')
    segs = _speech_segments(payload)
    assert len(segs) >= 2, f"Expected >=2 speech segments, got {len(segs)} — DSL parsing/cast routing not implemented"
    obobo = next((s for s in segs if s.get("studio_voice") == "OBOBO"), None)
    wendy = next((s for s in segs if s.get("studio_voice") == "WENDY"), None)
    assert obobo and wendy, "OBOBO/WENDY segments not found — speaker spans not being routed"
    assert obobo["voice"] != wendy["voice"], "Both lines rendered with the same voice — this is a forwarder"


def test_lexicon_respelling_is_applied_to_bare_names():
    """A bare 'OBOBO' must be substituted to its lexicon respelling before synthesis."""
    payload = _post_dsl("He named himself OBOBO.", fmt="plain")
    segs = _speech_segments(payload)
    joined = " ".join(s.get("text", "") for s in segs)
    applied = any(s.get("lexicon_applied") for s in segs)
    assert "oh-BOH-boh" in joined or applied, \
        "Lexicon not applied — 'OBOBO' reached the engine unrespelled (default G2P will mispronounce it)"
    assert "OBOBO" not in joined, "Raw 'OBOBO' still present in engine text — lexicon pre-pass not run"


def test_the_question_style_slows_delivery():
    payload = _post_dsl('{style:the_question}Was it yours.{/style}')
    segs = _speech_segments(payload)
    assert any(abs(s.get("speed", 1.0) - 0.85) < 1e-6 for s in segs), \
        "the_question style not realized (expected speed 0.85) — styles not implemented"


def test_style_emits_silence_segments():
    payload = _post_dsl('{style:chapter_header}Book One{/style}')
    sils = [s for s in payload.get("segments", []) if s.get("kind") == "silence"]
    assert sils, "No silence segments emitted around chapter_header — lead/trail pauses not implemented"


def test_manifest_skips_unchanged_segments_on_rerender():
    text = '{speaker:OBOBO}"The hand does not close."{/speaker}'
    _post_dsl(text)                      # first render populates the manifest
    second = _post_dsl(text)             # identical input
    assert second.get("cached_segments", 0) >= 1 or second.get("rendered_segments", 1) == 0, \
        "Re-render synthesized again — content-hash manifest / determinism not implemented"
