"""Build clip candidates from the transcript on NATURAL boundaries.

This is the guarantee that a clip never starts or ends mid-sentence / mid-word.
Strategy:
  1. Flatten all words, then group them into "sentence units" using punctuation
     (. ? !) and silence gaps between consecutive words.
  2. Grow a sliding window over sentence units, only ever cutting at a unit edge,
     to produce candidate windows whose duration is within [min, max] seconds.
  3. De-duplicate heavily overlapping windows later during ranking.

No model is involved here, so it always works and always cuts cleanly.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..config import settings
from ..models import Segment, Word


SENTENCE_END = re.compile(r"[.!?…]+[\"')\]]*$")


@dataclass
class Unit:
    """One sentence-like unit of speech."""
    start: float
    end: float
    text: str
    words: list[Word] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.end - self.start


def _flatten_words(segments: list[Segment]) -> list[Word]:
    words: list[Word] = []
    for s in segments:
        if s.words:
            words.extend(s.words)
        else:
            # fallback: whole segment as a single pseudo-word
            words.append(Word(start=s.start, end=s.end, text=s.text))
    words.sort(key=lambda w: w.start)
    return words


def build_units(segments: list[Segment], silence_gap: float | None = None) -> list[Unit]:
    """Group words into sentence units on punctuation + silence."""
    gap = settings.boundary_silence if silence_gap is None else silence_gap
    words = _flatten_words(segments)
    units: list[Unit] = []
    cur: list[Word] = []

    def flush():
        if not cur:
            return
        units.append(
            Unit(
                start=cur[0].start,
                end=cur[-1].end,
                text=" ".join(w.text for w in cur).strip(),
                words=list(cur),
            )
        )
        cur.clear()

    for i, w in enumerate(words):
        cur.append(w)
        ends_sentence = bool(SENTENCE_END.search(w.text))
        big_gap = i + 1 < len(words) and (words[i + 1].start - w.end) >= gap
        if ends_sentence or big_gap:
            flush()
    flush()
    return units


def build_candidates(
    units: list[Unit],
    min_s: float | None = None,
    max_s: float | None = None,
) -> list[tuple[float, float, str, list[Word]]]:
    """Return candidate windows as (start, end, text, words), all on unit edges."""
    lo = settings.min_clip_seconds if min_s is None else min_s
    hi = settings.max_clip_seconds if max_s is None else max_s

    cands: list[tuple[float, float, str, list[Word]]] = []
    n = len(units)
    for i in range(n):
        # A strong clip usually begins at the start of a sentence.
        acc_words: list[Word] = []
        for j in range(i, n):
            acc_words.extend(units[j].words)
            start = units[i].start
            end = units[j].end
            dur = end - start
            if dur < lo:
                continue
            if dur > hi:
                break
            text = " ".join(u.text for u in units[i : j + 1]).strip()
            cands.append((start, end, text, list(acc_words)))
    # If the whole video is shorter than `lo`, still offer it as one clip.
    if not cands and units:
        allw: list[Word] = [w for u in units for w in u.words]
        cands.append((units[0].start, units[-1].end, " ".join(u.text for u in units), allw))
    return cands
