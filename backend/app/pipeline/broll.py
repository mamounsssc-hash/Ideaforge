"""Optional B-roll: fetch short stock clips from Pexels and overlay them as
picture-in-picture cutaways on keyword moments (Crayo / Opus style).

Free but needs a Pexels API key (https://www.pexels.com/api/ — free tier).
Everything degrades to a silent no-op when the key is missing or a fetch fails,
so B-roll is a bonus, never a dependency.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import httpx

from ..config import WORK_DIR, settings
from ..models import ClipCandidate

log = logging.getLogger("ideaforge.broll")

_PEXELS = "https://api.pexels.com/videos/search"


def available() -> bool:
    return bool(settings.pexels_api_key.strip())


def _search_video(query: str) -> str | None:
    try:
        r = httpx.get(
            _PEXELS,
            params={"query": query, "per_page": 1, "orientation": "portrait"},
            headers={"Authorization": settings.pexels_api_key},
            timeout=15.0,
        )
        r.raise_for_status()
        vids = r.json().get("videos", [])
        if not vids:
            return None
        files = sorted(vids[0]["video_files"], key=lambda f: f.get("width", 0))
        # pick a mid-size file
        pick = files[len(files) // 2] if files else None
        return pick["link"] if pick else None
    except Exception as e:  # noqa: BLE001
        log.warning("pexels search failed: %s", e)
        return None


def _download(url: str, dest: Path) -> Path | None:
    try:
        with httpx.stream("GET", url, timeout=30.0, follow_redirects=True) as r:
            r.raise_for_status()
            with dest.open("wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
        return dest
    except Exception as e:  # noqa: BLE001
        log.warning("pexels download failed: %s", e)
        return None


def fetch_for(clip: ClipCandidate, tw: int, th: int, job_id: str) -> list[dict]:
    """Return up to 2 B-roll segments: {path, start, end} relative to the clip."""
    if not clip.keywords:
        return []
    duration = clip.end - clip.start
    segments: list[dict] = []
    # place B-roll on the 2 strongest keywords, ~2.5s each, spaced through the clip.
    slots = [(duration * 0.28, 2.5), (duration * 0.62, 2.5)]
    for idx, (kw, (t0, dur)) in enumerate(zip(clip.keywords[:2], slots)):
        if t0 + dur > duration:
            continue
        url = _search_video(kw)
        if not url:
            continue
        dest = WORK_DIR / f"{job_id}_{clip.id}_broll{idx}.mp4"
        if _download(url, dest):
            segments.append({"path": str(dest), "start": round(t0, 2), "end": round(t0 + dur, 2)})
    return segments


def _probe_duration(src: Path) -> float:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(src)],
            capture_output=True, text=True, check=True,
        )
        return float(r.stdout.strip())
    except Exception:  # noqa: BLE001
        return 0.0


def self_segments(source: Path, clip: ClipCandidate, tw: int, th: int, job_id: str) -> list[dict]:
    """B-roll WITHOUT the internet: cut short snippets from OTHER moments of the
    same source video and show them as picture-in-picture cutaways on keyword
    beats. Adds visual variety for free — degrades to [] on any problem.
    """
    clip_dur = clip.end - clip.start
    if clip_dur < 6:
        return []
    total = _probe_duration(source)
    if total < clip.end + 4 and clip.start < 4:
        return []
    # source timestamps clearly OUTSIDE the clip window (a moment before / after)
    picks = []
    before = clip.start - 35
    after = clip.end + 15
    if before >= 1:
        picks.append(before)
    if total and after + 3 <= total:
        picks.append(after)
    if not picks:
        return []
    # place the cutaways at ~30% and ~65% through the clip, ~2.2s each
    slots = [(clip_dur * 0.30, 2.2), (clip_dur * 0.64, 2.2)][: len(picks)]
    segments: list[dict] = []
    for idx, (src_t, (t0, dur)) in enumerate(zip(picks, slots)):
        if t0 + dur > clip_dur:
            continue
        dest = WORK_DIR / f"{job_id}_{clip.id}_selfbroll{idx}.mp4"
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-ss", f"{src_t:.3f}", "-i", str(source),
                 "-t", f"{dur:.3f}", "-an", "-c:v", "libx264", "-preset", "veryfast",
                 "-pix_fmt", "yuv420p", str(dest)],
                check=True, capture_output=True, text=True,
            )
            segments.append({"path": str(dest), "start": round(t0, 2), "end": round(t0 + dur, 2)})
        except Exception:  # noqa: BLE001
            continue
    return segments


def overlay(base: Path, segments: list[dict], out: Path, tw: int, th: int) -> Path:
    """Overlay each B-roll as a rounded PiP in the upper third during its window."""
    inputs = ["-i", str(base)]
    for seg in segments:
        inputs += ["-i", seg["path"]]

    pip_w = int(tw * 0.62)
    pip_h = int(pip_w * 9 / 16)
    x = (tw - pip_w) // 2
    y = int(th * 0.14)

    parts = []
    last = "0:v"
    for i, seg in enumerate(segments, start=1):
        parts.append(
            f"[{i}:v]scale={pip_w}:{pip_h}:force_original_aspect_ratio=increase,"
            f"crop={pip_w}:{pip_h},setsar=1[b{i}]"
        )
        parts.append(
            f"[{last}][b{i}]overlay={x}:{y}:enable='between(t,{seg['start']},{seg['end']})'[v{i}]"
        )
        last = f"v{i}"
    filter_complex = ";".join(parts)

    cmd = [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", filter_complex,
        "-map", f"[{last}]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
        str(out),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return out
