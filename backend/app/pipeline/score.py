"""Heuristic clip scoring — Layer 2. Always runs, never needs a model.

Produces a 0..99 "virality-style" score from measurable signals so the app can
rank clips well even with every LLM turned off. Mirrors the dimensions Opus Clip
and supoclip advertise (hook / emotion / value / completeness / pacing) but with
transparent, deterministic rules.
"""
from __future__ import annotations

import math
import re

from ..models import ClipCandidate, ScoreBreakdown, Word


HOOK_WORDS = {
    "how", "why", "what", "when", "who", "secret", "mistake", "never", "always",
    "stop", "start", "the truth", "nobody", "everyone", "here's", "listen",
    "imagine", "remember", "warning", "biggest", "worst", "best", "reason",
}
EMOTION_WORDS = {
    "love", "hate", "amazing", "incredible", "insane", "crazy", "shocking",
    "unbelievable", "terrible", "beautiful", "scary", "hilarious", "wow",
    "honestly", "literally", "actually", "seriously", "painful", "proud",
}
NUM_RE = re.compile(r"\b\d+([.,]\d+)?%?\b")
QUESTION_RE = re.compile(r"\?")
FILLER_RE = re.compile(r"\b(um+|uh+|erm+|like|you know)\b", re.I)


def _norm(x: float, k: float) -> float:
    """Squash x>=0 into 0..1 with soft saturation."""
    return 1 - math.exp(-x / k)


def _hook(text: str, first_words: list[Word]) -> float:
    head = " ".join(w.text for w in first_words[:8]).lower()
    score = 0.0
    if QUESTION_RE.search(head):
        score += 0.45
    for kw in HOOK_WORDS:
        if kw in head:
            score += 0.28
            break
    if NUM_RE.search(head):
        score += 0.2
    if first_words and first_words[0].text[:1].isupper():
        score += 0.1
    return min(1.0, score)


def _emotion(text: str) -> float:
    low = text.lower()
    hits = sum(1 for w in EMOTION_WORDS if w in low)
    punch = low.count("!") * 0.15
    return min(1.0, _norm(hits, 2.0) + punch)


def _info(text: str) -> float:
    nums = len(NUM_RE.findall(text))
    words = text.split()
    unique = len(set(w.lower() for w in words))
    density = unique / max(len(words), 1)
    return min(1.0, _norm(nums, 2.0) * 0.5 + density * 0.6)


def _completeness(text: str) -> float:
    t = text.strip()
    if not t:
        return 0.0
    starts_cap = t[0].isupper()
    ends_punct = t[-1] in ".!?…\"')"
    return 0.5 * starts_cap + 0.5 * ends_punct


def _pacing(words: list[Word], duration: float) -> float:
    if duration <= 0 or not words:
        return 0.0
    wps = len(words) / duration               # words per second
    ideal = 2.6                                # lively but intelligible
    closeness = max(0.0, 1 - abs(wps - ideal) / ideal)
    filler = len(FILLER_RE.findall(" ".join(w.text for w in words)))
    penalty = min(0.4, filler * 0.05)
    return max(0.0, closeness - penalty)


def score_candidate(start: float, end: float, text: str, words: list[Word]) -> ScoreBreakdown:
    duration = end - start
    hook = _hook(text, words)
    emotion = _emotion(text)
    info = _info(text)
    completeness = _completeness(text)
    pacing = _pacing(words, duration)

    # Weighted blend -> 0..1, then scale to a 20..99 band (nothing scores a flat 0).
    blend = (
        0.30 * hook
        + 0.20 * emotion
        + 0.18 * info
        + 0.17 * completeness
        + 0.15 * pacing
    )
    total = round(20 + blend * 79, 1)
    return ScoreBreakdown(
        hook=round(hook, 3),
        emotion=round(emotion, 3),
        info=round(info, 3),
        completeness=round(completeness, 3),
        pacing=round(pacing, 3),
        total=min(99.0, total),
        source="heuristic",
    )


def dedupe_and_rank(cands: list[ClipCandidate], target: int) -> list[ClipCandidate]:
    """Sort by score, then greedily drop candidates that overlap a better one > 50%."""
    ranked = sorted(cands, key=lambda c: c.score.total, reverse=True)
    kept: list[ClipCandidate] = []
    for c in ranked:
        overlap = False
        for k in kept:
            inter = max(0.0, min(c.end, k.end) - max(c.start, k.start))
            shorter = min(c.duration, k.duration) or 1.0
            if inter / shorter > 0.5:
                overlap = True
                break
        if not overlap:
            kept.append(c)
        if len(kept) >= target:
            break
    return kept
