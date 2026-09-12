"""Internal silence / dead-air removal with caption retiming.

This is the "remove awkward pauses" feature from Opus Clip. It finds gaps between
spoken words longer than `max_gap`, drops the dead air, and re-stamps the word
timestamps onto the new compressed timeline so captions stay perfectly in sync.

Implemented as a clean first ffmpeg pass (select/aselect + setpts) that produces a
tightened clip; the normal render (reframe + captions) then runs on that clip.
Fully local, no model.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..config import WORK_DIR
from ..models import Word


@dataclass
class TightenPlan:
    ranges: list[tuple[float, float]]     # kept spans in SOURCE time
    words: list[Word]                     # words retimed to the compressed timeline
    duration: float                       # new total duration


def plan(words: list[Word], clip_start: float, clip_end: float,
         max_gap: float = 0.5, pad: float = 0.12) -> TightenPlan | None:
    """Return a plan, or None if there is nothing worth removing."""
    if not words:
        return None
    spans: list[tuple[float, float]] = []
    run_start = max(clip_start, words[0].start - pad)
    prev_end = words[0].end
    for w in words[1:]:
        gap = w.start - prev_end
        if gap > max_gap:
            spans.append((run_start, min(clip_end, prev_end + pad)))
            run_start = max(clip_start, w.start - pad)
        prev_end = w.end
    spans.append((run_start, min(clip_end, prev_end + pad)))

    # merge tiny adjacent spans and drop invalid ones
    merged: list[tuple[float, float]] = []
    for s, e in spans:
        if e - s < 0.05:
            continue
        if merged and s - merged[-1][1] < 0.05:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))

    original = clip_end - clip_start
    kept = sum(e - s for s, e in merged)
    # not worth it if we'd remove < 0.4s total
    if original - kept < 0.4 or not merged:
        return None

    # retime words onto compressed timeline
    new_words: list[Word] = []
    cum = 0.0
    for (s, e) in merged:
        span_len = e - s
        for w in words:
            if w.start >= s and w.start < e:
                ns = cum + (w.start - s)
                ne = cum + (min(w.end, e) - s)
                new_words.append(Word(start=round(ns, 3), end=round(max(ne, ns + 0.05), 3),
                                      text=w.text, prob=w.prob))
        cum += span_len

    return TightenPlan(ranges=merged, words=new_words, duration=round(cum, 3))


def cut(source: Path, tp: TightenPlan, job_id: str, clip_id: str) -> Path:
    """Produce a tightened clip file from the kept ranges in a single ffmpeg pass."""
    out = WORK_DIR / f"{job_id}_{clip_id}_tight.mp4"
    sel = "+".join(f"between(t,{s:.3f},{e:.3f})" for s, e in tp.ranges)
    vf = f"select='{sel}',setpts=N/FRAME_RATE/TB"
    af = f"aselect='{sel}',asetpts=N/SR/TB"
    cmd = [
        "ffmpeg", "-y", "-i", str(source),
        "-vf", vf, "-af", af,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k",
        str(out),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return out
