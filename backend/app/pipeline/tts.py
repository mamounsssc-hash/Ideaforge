"""Text-to-speech for the faceless / story-video generator (Crayo-style).

Two engines, tried in order:
  1. piper  — fully offline, free (set IDEAFORGE_PIPER_BIN + a voice .onnx). Best for
     the "works offline" promise.
  2. edge-tts — free, high-quality Microsoft neural voices (needs internet).

`synthesize` returns a WAV/MP3 path. Word-level timing is recovered afterwards by
running the app's own Whisper on the generated audio, so captions stay in sync.
"""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from ..config import WORK_DIR, settings

# Curated voice list surfaced in the UI (edge-tts ids).
VOICES = [
    {"id": "en-US-GuyNeural", "name": "Guy (US, M)", "lang": "en"},
    {"id": "en-US-JennyNeural", "name": "Jenny (US, F)", "lang": "en"},
    {"id": "en-US-AriaNeural", "name": "Aria (US, F)", "lang": "en"},
    {"id": "en-US-ChristopherNeural", "name": "Christopher (US, M)", "lang": "en"},
    {"id": "en-GB-RyanNeural", "name": "Ryan (UK, M)", "lang": "en"},
    {"id": "en-GB-SoniaNeural", "name": "Sonia (UK, F)", "lang": "en"},
    {"id": "en-AU-NatashaNeural", "name": "Natasha (AU, F)", "lang": "en"},
    {"id": "ar-EG-ShakirNeural", "name": "Shakir (AR, M)", "lang": "ar"},
    {"id": "ar-EG-SalmaNeural", "name": "Salma (AR, F)", "lang": "ar"},
    {"id": "ar-SA-HamedNeural", "name": "Hamed (AR, M)", "lang": "ar"},
]


def _piper(text: str, out: Path) -> bool:
    if not settings.piper_bin or not settings.piper_voice:
        return False
    try:
        proc = subprocess.run(
            [settings.piper_bin, "--model", settings.piper_voice, "--output_file", str(out)],
            input=text, text=True, capture_output=True,
        )
        return proc.returncode == 0 and out.exists()
    except Exception:  # noqa: BLE001
        return False


def _edge(text: str, voice: str, out: Path) -> bool:
    try:
        import edge_tts
    except Exception:
        return False

    async def _go():
        comm = edge_tts.Communicate(text, voice)
        await comm.save(str(out))

    try:
        asyncio.run(_go())
        return out.exists() and out.stat().st_size > 0
    except Exception:  # noqa: BLE001
        return False


def synthesize(text: str, voice: str, job_id: str) -> Path:
    """Produce a voiceover audio file for `text`. Raises if no engine succeeds."""
    text = text.strip()
    if not text:
        raise RuntimeError("Empty script.")
    out = WORK_DIR / f"{job_id}_voiceover.mp3"

    order = settings.tts_engine
    tried = []
    if order in ("auto", "piper"):
        tried.append("piper")
        if _piper(text, out.with_suffix(".wav")):
            return out.with_suffix(".wav")
    if order in ("auto", "edge"):
        tried.append("edge-tts")
        if _edge(text, voice, out):
            return out
    raise RuntimeError(
        f"TTS failed (tried: {', '.join(tried)}). Install edge-tts (pip) for online "
        f"voices, or set IDEAFORGE_PIPER_BIN + IDEAFORGE_PIPER_VOICE for offline TTS."
    )
