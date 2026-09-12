"""Lightweight speaker turn detection for caption color-coding (Opus-style).

Default is a fast, model-free heuristic: a long pause between words starts a new
turn, and turns alternate through a small speaker set. It's approximate — good for
2-person interviews/podcasts — and can be upgraded to true diarization later
(pyannote) without touching callers.

Returns a per-word speaker index (0..N-1). captions.py maps each index to a color.
"""
from __future__ import annotations

from ..models import Word

# distinct highlight colors per speaker (RRGGBB)
SPEAKER_COLORS = ["F5D40A", "27C7FF", "31E36B", "FF7AD9", "FF6B4A", "B6FF3C"]


def assign(words: list[Word], turn_gap: float = 0.65, max_speakers: int = 2) -> list[int]:
    """Return a speaker index per word using pause-based turn segmentation."""
    if not words:
        return []
    speakers = [0] * len(words)
    cur = 0
    for i in range(1, len(words)):
        gap = words[i].start - words[i - 1].end
        if gap > turn_gap:
            cur = (cur + 1) % max_speakers
        speakers[i] = cur
    return speakers


def color_for(idx: int) -> str:
    return SPEAKER_COLORS[idx % len(SPEAKER_COLORS)]
