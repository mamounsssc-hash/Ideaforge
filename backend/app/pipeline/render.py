"""Render a final clip: cut -> reframe (track speaker) -> B-roll -> captions -> bar.

Single ffmpeg pass where possible. Fonts come from assets/fonts via fontconfig, so
bundled TTFs "just work". All feature toggles arrive via RenderOptions.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from ..config import OUTPUT_DIR, WORK_DIR, FONTS_DIR, settings
from ..models import ClipCandidate, RenderOptions, StylePreset, ratio_dims
from . import captions, reframe, broll


def _escape_ass_path(p: Path) -> str:
    s = str(p)
    s = s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    return s


def render_clip(
    source: Path,
    clip: ClipCandidate,
    style: StylePreset,
    job_id: str,
    opts: RenderOptions,
) -> Path:
    tw, th = ratio_dims(opts.aspect_ratio)
    out_path = OUTPUT_DIR / f"{job_id}_{clip.id}_{style.id}_{opts.aspect_ratio.replace(':','x')}.mp4"
    ass_path = WORK_DIR / f"{job_id}_{clip.id}_{style.id}.ass"
    duration = max(clip.end - clip.start, 0.1)

    # ---- 1. video filter: reframe or plain scale to target ratio ----
    if opts.reframe:
        vf = reframe.build_filter(source, clip.start, clip.end, tw, th)
    else:
        vf = f"scale={tw}:{th}:force_original_aspect_ratio=increase,crop={tw}:{th}"

    # ---- 3. captions (ASS) ----
    if opts.burn_captions and clip.words:
        keyword_set = set(clip.keywords) if opts.highlight_keywords else set()
        captions.write_ass(
            ass_path, clip.words, clip.start, clip.end, style,
            play_w=tw, play_h=th,
            keyword_set=keyword_set,
            add_emojis=opts.add_emojis,
            remove_fillers=opts.remove_fillers,
            hook_text=(clip.title if opts.hook_title else None),
        )
        fonts_arg = f":fontsdir='{_escape_ass_path(FONTS_DIR)}'" if FONTS_DIR.exists() else ""
        vf = f"{vf},subtitles='{_escape_ass_path(ass_path)}'{fonts_arg}"

    # ---- 4. progress bar along the bottom ----
    if opts.progress_bar:
        bar_h = max(6, th // 240)
        vf = (
            f"{vf},drawbox=x=0:y=ih-{bar_h}:w='iw*t/{duration:.3f}':h={bar_h}"
            f":color=white@0.92:t=fill"
        )

    # ---- 5. assemble ffmpeg command (main pass) ----
    main_target = out_path
    do_broll = opts.broll and broll.available()
    if do_broll:
        main_target = WORK_DIR / f"{job_id}_{clip.id}_base.mp4"

    cmd = [
        "ffmpeg", "-y", "-ss", f"{clip.start:.3f}", "-to", f"{clip.end:.3f}", "-i", str(source),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart",
        str(main_target),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)

    # ---- 6. optional B-roll overlay as a clean second pass (safe no-op on failure) ----
    if do_broll:
        try:
            segments = broll.fetch_for(clip, tw, th, job_id)
            if segments:
                broll.overlay(main_target, segments, out_path, tw, th)
                return out_path
        except Exception:  # noqa: BLE001 — never let B-roll break a render
            pass
        main_target.replace(out_path)
    return out_path


def extract_keyframe(source: Path, t: float, out: Path) -> Path:
    """Grab a single JPEG frame at time t (used to feed Qwen3-VL vision reranking)."""
    cmd = [
        "ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", str(source),
        "-frames:v", "1", "-q:v", "3", str(out),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return out
