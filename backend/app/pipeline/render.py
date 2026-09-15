"""Render a final clip through a clean chain of ffmpeg passes.

  (opt) tighten silence  ->  main pass (reframe + zoom + captions + watermark + bar)
  ->  (opt) B-roll overlay  ->  (opt) music mix

Each optional stage is isolated and degrades to a no-op on failure, so no single
feature can break a render. Fonts come from assets/fonts via fontconfig.
"""
from __future__ import annotations

import subprocess
from copy import deepcopy
from pathlib import Path

from ..config import OUTPUT_DIR, WORK_DIR, FONTS_DIR, settings
from ..models import ClipCandidate, RenderOptions, StylePreset, ratio_dims
from . import captions, reframe, broll, tighten, effects, sfx, gameplay


def _keyword_times(clip: ClipCandidate) -> list[float]:
    kws = {k.lower() for k in clip.keywords}
    ts: list[float] = []
    for w in clip.words:
        norm = "".join(ch for ch in w.text.lower() if ch.isalnum())
        if norm in kws:
            ts.append(round(w.start - clip.start, 3))
    return ts


def _escape_ass_path(p: Path) -> str:
    s = str(p)
    return s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def _layout_vf(source: Path, clip: ClipCandidate, opts: RenderOptions,
               tw: int, target_h: int, duration: float, safe: bool = False) -> str:
    """Build the clip's own footage chain (layout + grade + zoom) at tw×target_h.

    safe=True strips the optional visual effects (grade, zoom-punch, auto-zoom)
    so a render that failed with them can be retried with just the layout.
    """
    if not opts.reframe or opts.reframe_layout == "fill":
        cx = max(0.0, min(1.0, getattr(opts, "crop_x", 0.5)))
        vf = (
            f"scale={tw}:{target_h}:force_original_aspect_ratio=increase,"
            f"crop={tw}:{target_h}:x='(iw-ow)*{cx:.3f}':y='(ih-oh)*0.5',setsar=1"
        )
    elif opts.reframe_layout == "fit":
        vf = (
            f"split=2[bg][fg];"
            f"[bg]scale={tw}:{target_h}:force_original_aspect_ratio=increase,crop={tw}:{target_h},boxblur=40[bgb];"
            f"[fg]scale={tw}:{target_h}:force_original_aspect_ratio=decrease[fgs];"
            f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2"
        )
    else:  # "track" — follow the active speaker
        vf = reframe.build_filter(source, clip.start, clip.end, tw, target_h)

    if safe:
        return vf

    grade = effects.color_grade(opts.color_grade)
    if grade:
        vf += "," + grade
    if opts.zoom_punch:
        zp = effects.zoom_punch(_keyword_times(clip), tw, target_h)
        if zp:
            vf += "," + zp
    if opts.auto_zoom:
        frames = max(1, int(duration * 30))
        vf += (
            f",zoompan=z='min(1.0+0.08*on/{frames},1.08)':d=1"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={tw}x{target_h}:fps=30"
        )
    return vf


def render_clip(
    source: Path,
    clip: ClipCandidate,
    style: StylePreset,
    job_id: str,
    opts: RenderOptions,
    music_path: str = "",
    gameplay_path: str = "",
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

    # Gameplay split-screen: clip fills the top, a looping game fills the bottom.
    use_game = bool(opts.gameplay and gameplay_path and Path(gameplay_path).exists())
    top_h = gameplay.split_heights(th, opts.gameplay_split)[0] if use_game else th

    # ---- captions (+ CTA) and progress bar, targeting the FULL frame ----
    extras: list[str] = []
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
            cta_text=opts.cta_text or None,
            progressive=opts.caption_reveal,
            emoji_font=settings.emoji_font,
        )
        fonts_arg = f":fontsdir='{_escape_ass_path(FONTS_DIR)}'" if FONTS_DIR.exists() else ""
        extras.append(f"subtitles='{_escape_ass_path(ass_path)}'{fonts_arg}")
    if opts.progress_bar:
        bar_h = max(6, th // 240)
        extras.append(f"drawbox=x=0:y=ih-{bar_h}:w='iw*t/{duration:.3f}':h={bar_h}:color=white@0.92:t=fill")
    cap_bar = ",".join(extras)

    af = "afftdn=nf=-25,acompressor=threshold=-18dB:ratio=3,loudnorm=I=-16:TP=-1.5:LRA=11" if opts.enhance_audio else ""

    # ---- main pass: try with all effects, then retry with a safe layout-only
    # chain if anything in the filter graph fails. A clip must always render.
    stage = WORK_DIR / f"{job_id}_{clip.id}_stageA.mp4"

    def _single_pass(safe: bool) -> None:
        target_h = top_h if use_game else th
        vf = _layout_vf(source, clip, opts, tw, target_h, duration, safe=safe)
        if use_game:
            gameplay.compose(
                source, Path(gameplay_path), clip.start, clip.end, duration,
                tw, th, vf, cap_bar, af, stage, top_frac=opts.gameplay_split,
            )
            return
        full_vf = vf + (("," + cap_bar) if cap_bar else "")
        cmd = ["ffmpeg", "-y", "-ss", f"{clip.start:.3f}", "-to", f"{clip.end:.3f}",
               "-i", str(source), "-vf", full_vf]
        if af:
            cmd += ["-af", af]
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(stage)]
        _run(cmd)

    try:
        _single_pass(safe=False)
    except Exception:  # noqa: BLE001
        # Second chance: if the split-screen compose was the problem, drop it too.
        if use_game:
            use_game = False
        _single_pass(safe=True)
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

    # ---- unified audio sweetening pass: SFX at keyword moments + music ----
    hits = sfx.plan(clip, opts.sfx)
    wants_music = opts.music_volume > 0 and music_path and Path(music_path).exists()
    if hits or wants_music:
        try:
            nxt = WORK_DIR / f"{job_id}_{clip.id}_stageM.mp4"
            sfx.mix(current, hits, music_path if wants_music else "", opts.music_volume, nxt)
            if nxt.exists():
                current = nxt
        except Exception:  # noqa: BLE001
            pass

    Path(current).replace(out_path)
    return out_path


def extract_keyframe(source: Path, t: float, out: Path) -> Path:
    _run(["ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", str(source),
          "-frames:v", "1", "-q:v", "3", str(out)])
    return out


def render_faceless(
    clip: ClipCandidate,
    voiceover: Path,
    style: StylePreset,
    job_id: str,
    opts,                       # CreateOptions
    background: Path | None,
    music_path: str = "",
) -> Path:
    """Compose a faceless short: background + voiceover + synced captions (+ music)."""
    tw, th = ratio_dims(opts.aspect_ratio)
    dur = max(clip.end - clip.start, 0.5)
    out_path = OUTPUT_DIR / f"{job_id}_faceless_{style.id}_{opts.aspect_ratio.replace(':', 'x')}.mp4"

    # ---- inputs: [0]=background, [1]=voiceover, [2]=music? ----
    inputs: list[str] = []
    bg = opts.background
    if bg == "video" and background and background.exists():
        inputs += ["-stream_loop", "-1", "-i", str(background)]
    elif bg == "pexels" and background and background.exists():
        inputs += ["-stream_loop", "-1", "-i", str(background)]
    elif bg == "color":
        inputs += ["-f", "lavfi", "-i", f"color=c=0x{opts.background_color}:s={tw}x{th}:d={dur:.2f}"]
    else:  # gradient (default, offline)
        inputs += ["-f", "lavfi", "-i",
                   f"gradients=s={tw}x{th}:c0=0x{opts.background_color}:c1=0x{opts.background_color2}"
                   f":x0=0:y0=0:x1={tw}:y1={th}:d={dur:.2f}:speed=0.015"]
    inputs += ["-i", str(voiceover)]
    has_music = opts.music_volume > 0 and music_path and Path(music_path).exists()
    if has_music:
        inputs += ["-stream_loop", "-1", "-i", str(music_path)]

    # ---- captions ASS (word timing from the voiceover) ----
    vchain = f"[0:v]scale={tw}:{th}:force_original_aspect_ratio=increase,crop={tw}:{th},setsar=1"
    grade = effects.color_grade(opts.color_grade)
    if grade:
        vchain += "," + grade
    if opts.zoom_punch:
        zp = effects.zoom_punch(_keyword_times(clip), tw, th)
        if zp:
            vchain += "," + zp
    if opts.auto_zoom:
        frames = max(1, int(dur * 30))
        vchain += (f",zoompan=z='min(1.0+0.08*on/{frames},1.08)':d=1"
                   f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={tw}x{th}:fps=30")
    if opts.burn_captions and clip.words:
        ass_path = WORK_DIR / f"{job_id}_faceless.ass"
        captions.write_ass(
            ass_path, clip.words, 0.0, dur, style, play_w=tw, play_h=th,
            keyword_set=set(clip.keywords) if opts.highlight_keywords else set(),
            add_emojis=opts.add_emojis, remove_fillers=False,
            hook_text=(clip.title if opts.hook_title else None),
            position_override=opts.caption_position, scale=opts.caption_scale,
            offset=opts.caption_offset, cta_text=opts.cta_text or None,
            progressive=getattr(opts, "caption_reveal", True),
            emoji_font=settings.emoji_font,
        )
        fonts_arg = f":fontsdir='{_escape_ass_path(FONTS_DIR)}'" if FONTS_DIR.exists() else ""
        vchain += f",subtitles='{_escape_ass_path(ass_path)}'{fonts_arg}"
    if opts.progress_bar:
        bar_h = max(6, th // 240)
        vchain += f",drawbox=x=0:y=ih-{bar_h}:w='iw*t/{dur:.3f}':h={bar_h}:color=white@0.92:t=fill"
    vchain += "[v]"

    # ---- audio: voiceover (+ music) ----
    vo_idx = 1
    if has_music:
        achain = (f"[{vo_idx}:a]volume=1.0[vo];[{vo_idx+1}:a]volume={min(1.0, opts.music_volume):.2f}[mu];"
                  f"[vo][mu]amix=inputs=2:duration=first:dropout_transition=0[a]")
        amap = "[a]"
    else:
        achain = ""
        amap = f"{vo_idx}:a"
    filter_complex = vchain + ((";" + achain) if achain else "")

    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", filter_complex,
           "-map", "[v]", "-map", amap, "-t", f"{dur:.3f}",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-shortest",
           str(out_path)]
    _run(cmd)

    # SFX post-pass (music is already mixed above, so don't re-add it)
    hits = sfx.plan(clip, opts.sfx)
    if hits:
        try:
            sweetened = WORK_DIR / f"{job_id}_faceless_sfx.mp4"
            sfx.mix(out_path, hits, "", 0.0, sweetened)
            if sweetened.exists():
                sweetened.replace(out_path)
        except Exception:  # noqa: BLE001
            pass
    return out_path
