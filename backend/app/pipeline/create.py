"""Faceless / story-video generator (Crayo-style): script -> voiceover ->
background -> synced captions -> vertical short.

Reuses the app's own Whisper (to time the captions to the generated voiceover) and
the caption/render engine, so every caption style and toggle works here too.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from ..config import WORK_DIR, settings
from ..jobs import store
from ..models import CreateOptions, ClipCandidate, Word
from . import tts, transcribe, render, keywords, llm, broll

log = logging.getLogger("ideaforge.create")


def _script_from_topic(topic: str) -> str:
    """Ask the optional LLM for a short script; fall back to a simple template."""
    if llm.available():
        try:
            import httpx
            payload = {
                "model": settings.llm_model,
                "messages": [
                    {"role": "system", "content": "You write punchy 30-45 second vertical video scripts. "
                     "Return ONLY the narration text, one idea per sentence, strong hook first. No headings."},
                    {"role": "user", "content": f"Write a short faceless video script about: {topic}"},
                ],
                "temperature": 0.8, "stream": False,
            }
            url = settings.llm_base_url.rstrip("/") + "/chat/completions"
            r = httpx.post(url, json=payload, headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                           timeout=settings.llm_timeout)
            r.raise_for_status()
            txt = r.json()["choices"][0]["message"]["content"].strip()
            if txt:
                return txt
        except Exception as e:  # noqa: BLE001
            log.warning("script generation via LLM failed: %s", e)
    return (f"Here's something you didn't know about {topic}. "
            f"Most people get this completely wrong. "
            f"But once you understand it, everything changes. Follow for more.")


def create_faceless(job_id: str, opts: CreateOptions, background: str | None, music_path: str) -> None:
    try:
        store.update(job_id, kind="create")
        # ---- 1. script ----
        store.set_progress(job_id, "analyzing", 0.05, "Preparing script…")
        script = opts.script.strip() or _script_from_topic(opts.topic.strip() or "an interesting fact")

        # ---- 2. voiceover (TTS) ----
        store.set_progress(job_id, "analyzing", 0.2, "Generating voiceover…")
        voiceover = tts.synthesize(script, opts.voice, job_id)

        # ---- 3. word-level timing via Whisper on the voiceover ----
        store.set_progress(job_id, "transcribing", 0.45, "Timing captions…")
        segments, _lang = transcribe.transcribe(voiceover, language=None)
        words: list[Word] = [w for s in segments for w in (s.words or [])]
        if not words:
            # fall back to a single block if word timing failed
            from .download import probe_duration
            dur = probe_duration(voiceover)
            words = [Word(start=0.0, end=dur, text=script[:120])]
        dur = words[-1].end

        title = (opts.topic.strip() or " ".join(script.split()[:6])).title()[:60]
        clip = ClipCandidate(
            id=uuid.uuid4().hex[:8], start=0.0, end=dur, text=script, words=words,
            title=title, keywords=keywords.extract_keywords(script, top_n=6),
        )
        clip.hashtags = keywords.hashtags(script, extra=clip.keywords)
        clip.social_caption = keywords.social_caption(title, script)

        # ---- 4. background (optional Pexels fetch) ----
        bg_path: Path | None = Path(background) if background else None
        if opts.background == "pexels" and broll.available():
            store.set_progress(job_id, "analyzing", 0.6, "Fetching background…")
            url = broll._search_video(opts.background_query or "satisfying")
            if url:
                dest = WORK_DIR / f"{job_id}_bg.mp4"
                if broll._download(url, dest):
                    bg_path = dest

        # ---- 5. compose ----
        store.set_progress(job_id, "ranking", 0.75, "Rendering video…")
        out = render.render_faceless(clip, voiceover, __style(opts.style_id), job_id, opts, bg_path, music_path)

        store.update(job_id, clips=[clip], output_url=f"/api/file/{out.name}", duration=dur)
        store.set_progress(job_id, "ready", 1.0, "Your video is ready")
        log.info("faceless job %s ready (%.1fs)", job_id, dur)
    except Exception as e:  # noqa: BLE001
        log.exception("faceless job %s failed", job_id)
        store.update(job_id, status="error", error=f"{type(e).__name__}: {e}", message="Failed")


def __style(style_id: str):
    from ..styles import get_style
    return get_style(style_id)
