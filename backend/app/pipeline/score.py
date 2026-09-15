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
# Markers of a payoff / conclusion — the "so what" that makes a clip feel complete
# and meaningful instead of a random slice. Strongly favoured.
CONCLUSION_WORDS = {
    "so", "because", "therefore", "which means", "that's why", "the point",
    "the reason", "in the end", "bottom line", "the lesson", "the truth is",
    "here's the thing", "what i learned", "the key", "this is how", "that means",
    "and that's", "the result", "turns out", "the takeaway", "moral",
}
# A meaningful clip usually lands in this length band (seconds).
_SWEET_MIN, _SWEET_MAX = 16.0, 45.0
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


def _payoff(text: str) -> float:
    """Does the clip resolve into a point? Setup->payoff reads as complete & meaningful."""
    low = text.lower()
    score = 0.0
    for kw in CONCLUSION_WORDS:
        if kw in low:
            score += 0.5
            break
    # a question early that is then answered by later statements (classic arc)
    qpos = low.find("?")
    if 0 <= qpos < len(low) * 0.6:
        score += 0.35
    # explicit list/steps signal structured value ("three things", "first… then…")
    if re.search(r"\b(first|second|third|number one|step one|reason (one|1))\b", low):
        score += 0.25
    return min(1.0, score)


def _length_fit(duration: float) -> float:
    """1.0 inside the sweet-spot band, tapering off for very short/long clips."""
    if duration <= 0:
        return 0.0
    if _SWEET_MIN <= duration <= _SWEET_MAX:
        return 1.0
    if duration < _SWEET_MIN:
        return max(0.0, duration / _SWEET_MIN)
    return max(0.35, 1 - (duration - _SWEET_MAX) / 60.0)


def _topic_match(text: str, topic_terms: set[str]) -> float:
    """0..1 overlap between the clip and a user topic ('find clips about X')."""
    if not topic_terms:
        return 0.0
    words = {w.lower().strip(".,!?;:\"'") for w in text.split()}
    hits = len(topic_terms & words)
    return min(1.0, hits / max(1, len(topic_terms)) + (0.15 if hits else 0.0))


def score_candidate(start: float, end: float, text: str, words: list[Word],
                    topic_terms: set[str] | None = None) -> ScoreBreakdown:
    duration = end - start
    hook = _hook(text, words)
    emotion = _emotion(text)
    info = _info(text)
    completeness = _completeness(text)
    pacing = _pacing(words, duration)
    payoff = _payoff(text)
    topic = _topic_match(text, topic_terms or set())

    # Fold the "meaningful arc" signals into the shown dimensions so the UI still
    # reads clearly: a resolved point lifts both completeness and info.
    completeness = min(1.0, completeness + 0.35 * payoff)
    info = min(1.0, info + 0.25 * payoff)

    # Weighted blend -> 0..1, then scale to a 20..99 band (nothing scores a flat 0).
    blend = (
        0.24 * hook
        + 0.15 * emotion
        + 0.15 * info
        + 0.17 * completeness
        + 0.11 * pacing
        + 0.10 * payoff
        + 0.08 * topic
    )
    # Synergy: a strong hook AND a resolved ending is what actually retains viewers.
    if hook > 0.4 and (completeness > 0.7 or payoff > 0.4):
        blend = min(1.0, blend + 0.06)
    # Prefer clips that sit in the natural short-form length band.
    blend *= 0.75 + 0.25 * _length_fit(duration)
    if topic_terms and topic == 0.0:
        blend *= 0.6            # off-topic clips are pushed down when a topic is set
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


def _overlap_frac(c: ClipCandidate, k: ClipCandidate) -> float:
    inter = max(0.0, min(c.end, k.end) - max(c.start, k.start))
    shorter = min(c.duration, k.duration) or 1.0
    return inter / shorter


def dedupe_and_rank(cands: list[ClipCandidate], target: int,
                    min_start_gap: float = 4.0) -> list[ClipCandidate]:
    """Rank by score and select up to `target` clips.

    Pass 1 keeps the best, mutually-distinct clips (overlap < 50%) — this is the
    quality tier. If the user asked for more clips than fit without overlapping
    (e.g. 100 from one video), pass 2 relaxes: it adds the next best candidates
    as long as their START time differs from every kept clip by at least
    `min_start_gap` seconds, so extra clips are still distinct high-retention
    moments rather than near-duplicates.
    """
    ranked = sorted(cands, key=lambda c: c.score.total, reverse=True)
    kept: list[ClipCandidate] = []
    kept_ids: set[int] = set()

    # Pass 1 — strict: no two clips overlap by more than half.
    for c in ranked:
        if len(kept) >= target:
            return kept
        if all(_overlap_frac(c, k) <= 0.5 for k in kept):
            kept.append(c)
            kept_ids.add(id(c))

    # Pass 2 — relax to reach a large target, keeping starts spread out.
    if len(kept) < target:
        starts = [k.start for k in kept]
        for c in ranked:
            if len(kept) >= target:
                break
            if id(c) in kept_ids:
                continue
            if all(abs(c.start - s) >= min_start_gap for s in starts):
                kept.append(c)
                kept_ids.add(id(c))
                starts.append(c.start)

    return kept
