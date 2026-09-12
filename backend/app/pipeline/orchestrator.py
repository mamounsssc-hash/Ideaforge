"""Ties the pipeline together and drives job progress.

Flow (each stage degrades gracefully — the run never dead-ends):
  download/probe -> transcribe -> build units -> candidates -> heuristic score
  -> dedupe/rank -> (optional) LLM/Qwen3-VL rerank -> mark ready.

Rendering of a specific clip+style happens later, on demand, from the API.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from ..config import settings, WORK_DIR
from ..jobs import store
from ..models import ClipCandidate
from . import download, transcribe, segment, score, llm, render

log = logging.getLogger("ideaforge.orchestrator")


def analyze(job_id: str, source: str, is_url: bool, language: str | None) -> None:
    """Run the full analysis pipeline for a job. Intended to run in a worker thread."""
    try:
        # ---- 1. acquire media ----
        if is_url:
            store.set_progress(job_id, "downloading", 0.03, "Downloading source…")
            src_path = download.download_url(source, job_id)
        else:
            src_path = Path(source)
        dur = download.probe_duration(src_path)
        store.update(job_id, source_path=str(src_path), duration=dur)

        # ---- 2. transcribe (local, word timestamps) ----
        store.set_progress(job_id, "transcribing", 0.08, "Transcribing audio…")

        def _tp(pct: float, msg: str):
            store.set_progress(job_id, "transcribing", 0.08 + pct * 0.5, msg)

        segments, lang = transcribe.transcribe(src_path, language, progress=_tp)
        store.update(job_id, language=lang)
        if not segments:
            raise RuntimeError("No speech detected in the video.")

        # ---- 3. natural-boundary units + candidates ----
        store.set_progress(job_id, "analyzing", 0.62, "Finding clean cut points…")
        units = segment.build_units(segments)
        raw = segment.build_candidates(units)
        if not raw:
            raise RuntimeError("Could not form any clip candidates.")

        # ---- 4. heuristic scoring (Layer 2 — always) ----
        store.set_progress(job_id, "analyzing", 0.72, "Scoring highlights…")
        candidates: list[ClipCandidate] = []
        for (start, end, text, words) in raw:
            sb = score.score_candidate(start, end, text, words)
            candidates.append(
                ClipCandidate(
                    id=uuid.uuid4().hex[:8],
                    start=round(start, 3),
                    end=round(end, 3),
                    text=text,
                    words=words,
                    title="",
                    score=sb,
                )
            )
        ranked = score.dedupe_and_rank(candidates, settings.target_clip_count)

        # ---- 5. optional LLM / Qwen3-VL rerank (Layer 3 — best effort) ----
        if llm.available():
            store.set_progress(job_id, "ranking", 0.85, "Refining with local model…")
            keyframes = None
            if settings.llm_vision:
                keyframes = {}
                for i, c in enumerate(ranked):
                    kf = WORK_DIR / f"{job_id}_{c.id}_kf.jpg"
                    try:
                        render.extract_keyframe(src_path, (c.start + c.end) / 2, kf)
                        keyframes[i] = kf
                    except Exception:  # noqa: BLE001
                        pass
            ranked = llm.rerank(ranked, keyframes)
            ranked.sort(key=lambda c: c.score.total, reverse=True)

        # ---- 6. titles fallback (if no model gave one) ----
        for c in ranked:
            if not c.title:
                c.title = _fallback_title(c.text)

        store.update(job_id, clips=ranked)
        store.set_progress(job_id, "ready", 1.0, f"Ready — {len(ranked)} clips")
        log.info("job %s ready with %d clips (lang=%s)", job_id, len(ranked), lang)

    except Exception as e:  # noqa: BLE001
        log.exception("job %s failed", job_id)
        store.update(job_id, status="error", error=f"{type(e).__name__}: {e}", message="Failed")


def _fallback_title(text: str) -> str:
    words = text.split()
    head = " ".join(words[:6]).strip(" ,.!?-")
    return (head[:60] or "Clip").title()
