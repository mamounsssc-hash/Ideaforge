"""Split-screen gameplay layout: the clip on top, a looping game on the bottom.

This is the retention format popularised on TikTok/Reels/Shorts — the talking
clip fills the top of the 9:16 frame while an endless gameplay video (Subway
Surfers, Minecraft parkour, GTA driving, satisfying loops…) plays underneath so
the viewer's eyes never get bored. Fully local & free: the game is any vertical
video the user drops in; ffmpeg stacks the two and burns the captions on top.

The composer is isolated so it can never break a normal render: render.py only
calls it when the user enables gameplay AND a game video exists, and falls back
to the standard single-input pass on any failure.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def _even(n: int) -> int:
    return n - (n % 2)


def split_heights(total_h: int, top_frac: float) -> tuple[int, int]:
    """Return (top_h, bottom_h) — both even and summing to total_h."""
    top_frac = max(0.35, min(0.8, float(top_frac)))
    top_h = _even(int(round(total_h * top_frac)))
    top_h = max(2, min(total_h - 2, top_h))
    return top_h, total_h - top_h


def compose(
    source: Path,
    game: Path,
    start: float,
    end: float,
    duration: float,
    tw: int,
    th: int,
    top_vf: str,
    cap_bar: str,
    audio_filter: str,
    out_path: Path,
    top_frac: float = 0.6,
) -> Path:
    """Stack a reframed clip (top) over a looping game (bottom) and burn captions.

    top_vf     : the clip's own layout/grade/zoom chain, already targeting tw×top_h.
    cap_bar    : comma-joined caption + progress-bar filters for the full tw×th frame
                 (no leading comma), or "" for none.
    audio_filter: an -af style chain for the voice, or "" to copy the clip audio.
    """
    top_h, bot_h = split_heights(th, top_frac)

    parts = [
        f"[0:v]{top_vf}[top]",
        f"[1:v]scale={tw}:{bot_h}:force_original_aspect_ratio=increase,"
        f"crop={tw}:{bot_h},setsar=1[bot]",
        "[top][bot]vstack=inputs=2[st]",
    ]
    if cap_bar:
        parts.append(f"[st]{cap_bar}[v]")
        vmap = "[v]"
    else:
        vmap = "[st]"

    if audio_filter:
        parts.append(f"[0:a]{audio_filter}[a]")
        amap = "[a]"
    else:
        amap = "0:a"

    fc = ";".join(parts)
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(source),
        "-stream_loop", "-1", "-i", str(game),
        "-filter_complex", fc,
        "-map", vmap, "-map", amap,
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return out_path
