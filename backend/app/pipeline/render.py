"""Render a final vertical clip: cut -> reframe (track speaker) -> burn captions.

Everything is done in a single ffmpeg pass where possible for speed. Fonts are
picked up from assets/fonts via fontconfig dir, so bundled TTFs "just work".
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from ..config import OUTPUT_DIR, WORK_DIR, FONTS_DIR, settings
from ..models import ClipCandidate, StylePreset, Word
from . import captions, reframe


def _escape_ass_path(p: Path) -> str:
    # ffmpeg subtitles filter needs escaped path (esp. on Windows drive letters).
    s = str(p)
    s = s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    return s


def render_clip(
    source: Path,
    clip: ClipCandidate,
    style: StylePreset,
    job_id: str,
    reframe_on: bool = True,
    burn_captions: bool = True,
) -> Path:
    out_path = OUTPUT_DIR / f"{job_id}_{clip.id}_{style.id}.mp4"
    ass_path = WORK_DIR / f"{job_id}_{clip.id}_{style.id}.ass"

    # 1) video filter: reframe to 9:16 (with speaker tracking) or plain scale
    if reframe_on:
        vf = reframe.build_filter(source, clip.start, clip.end)
    else:
        tw, th = settings.target_width, settings.target_height
        vf = f"scale={tw}:{th}:force_original_aspect_ratio=increase,crop={tw}:{th}"

    # 2) captions: write ASS then append subtitles filter
    if burn_captions and clip.words:
        captions.write_ass(ass_path, clip.words, clip.start, clip.end, style)
        fonts_arg = f":fontsdir='{_escape_ass_path(FONTS_DIR)}'" if FONTS_DIR.exists() else ""
        vf = f"{vf},subtitles='{_escape_ass_path(ass_path)}'{fonts_arg}"

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{clip.start:.3f}",
        "-to", f"{clip.end:.3f}",
        "-i", str(source),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return out_path


def extract_keyframe(source: Path, t: float, out: Path) -> Path:
    """Grab a single JPEG frame at time t (used to feed Qwen3-VL vision reranking)."""
    cmd = [
        "ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", str(source),
        "-frames:v", "1", "-q:v", "3", str(out),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return out
