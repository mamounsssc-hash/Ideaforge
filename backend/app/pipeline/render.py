"""Render a final clip through a clean chain of ffmpeg passes.

  (opt) tighten silence  ->  main pass (reframe + zoom + captions + watermark + bar)
  ->  (opt) B-roll overlay  ->  (opt) music mix

Each optional stage is isolated and degrades to a no-op on failure, so no single
feature can break a render. Fonts come from assets/fonts via fontconfig.
"""
from __future__ import annotations

import re
import subprocess
from copy import deepcopy
from pathlib import Path

from ..config import OUTPUT_DIR, WORK_DIR, FONTS_DIR, settings
from ..models import ClipCandidate, RenderOptions, StylePreset, ratio_dims
from . import captions, reframe, broll, tighten


def _escape_ass_path(p: Path) -> str:
    s = str(p)
    return s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def _safe_text(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9@#_. -]", "", s)[:40]


def render_clip(
    source: Path,
    clip: ClipCandidate,
    style: StylePreset,
    job_id: str,
    opts: RenderOptions,
    music_path: str = "",
) -> Path:
    tw, th = ratio_dims(opts.aspect_ratio)
    tag = f"{opts.aspect_ratio.replace(':', 'x')}"
    out_path = OUTPUT_DIR / f"{job_id}_{clip.id}_{style.id}_{tag}.mp4"

    # ---- 0. optional silence removal (produces a tightened source + retimed words) ----
    if opts.remove_silence and clip.words:
        tp = tighten.plan(clip.words, clip.start, clip.end)
        if tp:
            try:
                tight = tighten.cut(source, tp, job_id, clip.id)
                source = tight
                clip = deepcopy(clip)
                clip.start, clip.end, clip.words = 0.0, tp.duration, tp.words
            except Exception:  # noqa: BLE001
                pass

    duration = max(clip.end - clip.start, 0.1)

    # ---- 1. base video filter ----
    if opts.reframe:
        vf = reframe.build_filter(source, clip.start, clip.end, tw, th)
    else:
        vf = f"scale={tw}:{th}:force_original_aspect_ratio=increase,crop={tw}:{th}"

    # ---- 2. auto zoom / punch-in (before captions so text doesn't scale) ----
    if opts.auto_zoom:
        frames = max(1, int(duration * 30))
        vf += (
            f",zoompan=z='min(1.0+0.08*on/{frames},1.08)':d=1"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={tw}x{th}:fps=30"
        )

    # ---- 3. captions ----
    if opts.burn_captions and clip.words:
        ass_path = WORK_DIR / f"{job_id}_{clip.id}_{style.id}.ass"
        captions.write_ass(
            ass_path, clip.words, clip.start, clip.end, style,
            play_w=tw, play_h=th,
            keyword_set=set(clip.keywords) if opts.highlight_keywords else set(),
            add_emojis=opts.add_emojis,
            remove_fillers=opts.remove_fillers,
            hook_text=(clip.title if opts.hook_title else None),
            position_override=opts.caption_position,
            scale=opts.caption_scale,
            offset=opts.caption_offset,
            speaker_colors=opts.speaker_colors,
        )
        fonts_arg = f":fontsdir='{_escape_ass_path(FONTS_DIR)}'" if FONTS_DIR.exists() else ""
        vf += f",subtitles='{_escape_ass_path(ass_path)}'{fonts_arg}"

    # ---- 4. watermark / handle ----
    if opts.watermark_text.strip():
        wm = _safe_text(opts.watermark_text.strip())
        if wm:
            fs = max(22, th // 40)
            vf += (
                f",drawtext=text='{wm}':fontcolor=white@0.85:fontsize={fs}"
                f":x=(w-text_w)/2:y=h-text_h-{max(24, th // 30)}"
                f":box=1:boxcolor=black@0.28:boxborderw=8"
            )

    # ---- 5. progress bar ----
    if opts.progress_bar:
        bar_h = max(6, th // 240)
        vf += f",drawbox=x=0:y=ih-{bar_h}:w='iw*t/{duration:.3f}':h={bar_h}:color=white@0.92:t=fill"

    # ---- main pass ----
    stage = WORK_DIR / f"{job_id}_{clip.id}_stageA.mp4"
    _run([
        "ffmpeg", "-y", "-ss", f"{clip.start:.3f}", "-to", f"{clip.end:.3f}", "-i", str(source),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
        str(stage),
    ])
    current = stage

    # ---- optional B-roll overlay pass ----
    if opts.broll and broll.available():
        try:
            segs = broll.fetch_for(clip, tw, th, job_id)
            if segs:
                nxt = WORK_DIR / f"{job_id}_{clip.id}_stageB.mp4"
                broll.overlay(current, segs, nxt, tw, th)
                current = nxt
        except Exception:  # noqa: BLE001
            pass

    # ---- optional background music pass ----
    if opts.music_volume > 0 and music_path and Path(music_path).exists():
        try:
            nxt = WORK_DIR / f"{job_id}_{clip.id}_stageM.mp4"
            _mix_music(current, Path(music_path), nxt, opts.music_volume)
            current = nxt
        except Exception:  # noqa: BLE001
            pass

    Path(current).replace(out_path)
    return out_path


def _mix_music(video: Path, music: Path, out: Path, vol: float) -> Path:
    vol = max(0.0, min(1.0, vol))
    fc = (
        f"[0:a]volume=1.0[a0];[1:a]volume={vol:.2f}[a1];"
        f"[a0][a1]amix=inputs=2:duration=first:dropout_transition=0[aout]"
    )
    _run([
        "ffmpeg", "-y", "-i", str(video), "-stream_loop", "-1", "-i", str(music),
        "-filter_complex", fc, "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest",
        str(out),
    ])
    return out


def extract_keyframe(source: Path, t: float, out: Path) -> Path:
    _run(["ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", str(source),
          "-frames:v", "1", "-q:v", "3", str(out)])
    return out
