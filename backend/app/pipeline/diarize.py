"""Optional real speaker diarization — "who spoke when" — with pyannote.audio.

Fully optional and safe: if pyannote isn't installed or no HuggingFace token is
set, this is a no-op and the app uses the fast pause-based heuristic instead.

Enable it (real per-speaker caption colours + better multi-person handling):
  1) pip install "pyannote.audio>=3.1"          (downloads ~1-2 GB of models)
  2) Get a free token at huggingface.co/settings/tokens and ACCEPT the terms of
     the model at huggingface.co/pyannote/speaker-diarization-3.1
  3) Set  IDEAFORGE_HF_TOKEN=your_token   (START.bat can set it for you)
"""
from __future__ import annotations

import logging
from pathlib import Path

from ..config import settings
from ..models import Word

log = logging.getLogger("ideaforge.diarize")

_pipeline = None
_tried = False


def available() -> bool:
    return bool((settings.hf_token or "").strip())


def _load():
    global _pipeline, _tried
    if _tried:
        return _pipeline
    _tried = True
    try:
        from pyannote.audio import Pipeline
        _pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1", use_auth_token=settings.hf_token,
        )
        try:  # move to GPU when available
            import torch
            if torch.cuda.is_available():
                _pipeline.to(torch.device("cuda"))
        except Exception:  # noqa: BLE001
            pass
        print("[IdeaForge] Speaker diarization ready (pyannote).", flush=True)
    except Exception as e:  # noqa: BLE001
        log.warning("diarization unavailable (%s); using the pause heuristic.", e)
        print("[IdeaForge] Diarization not available — using the fast heuristic. "
              "Install pyannote.audio + set IDEAFORGE_HF_TOKEN to enable it.", flush=True)
        _pipeline = None
    return _pipeline


def label_words(media_path: Path, words: list[Word]) -> None:
    """Set each word's `speaker` (0..N-1) in place. No-op on any failure."""
    if not words or not available():
        return
    pipe = _load()
    if pipe is None:
        return
    try:
        diar = pipe(str(media_path))
        turns = [(seg.start, seg.end, lbl) for seg, _, lbl in diar.itertracks(yield_label=True)]
        order: list[str] = []

        def idx_for(lbl: str) -> int:
            if lbl not in order:
                order.append(lbl)
            return order.index(lbl)

        for w in words:
            mid = (w.start + w.end) / 2.0
            for (s, e, lbl) in turns:
                if s <= mid <= e:
                    w.speaker = idx_for(lbl)
                    break
    except Exception as e:  # noqa: BLE001
        log.warning("diarization run failed: %s", e)
