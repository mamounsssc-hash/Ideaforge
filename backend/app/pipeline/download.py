"""Acquire source media: either a user upload (already on disk) or a URL.

URLs are fetched with yt-dlp, which supports YouTube, TikTok, Instagram, X, etc.
Fully local & free — no API key.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from ..config import WORK_DIR


def download_url(url: str, job_id: str) -> Path:
    out_tmpl = str(WORK_DIR / f"{job_id}_source.%(ext)s")
    cmd = [
        "yt-dlp",
        "-f", "bv*[height<=1080]+ba/b[height<=1080]/b",
        "--merge-output-format", "mp4",
        "-o", out_tmpl,
        "--no-playlist",
        url,
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    # yt-dlp resolved the extension; find the produced file.
    matches = sorted(WORK_DIR.glob(f"{job_id}_source.*"))
    if not matches:
        raise RuntimeError("yt-dlp produced no output file")
    return matches[0]


def probe_duration(path: Path) -> float:
    """Return media duration in seconds via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    out = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout.strip()
    try:
        return float(out)
    except ValueError:
        return 0.0
