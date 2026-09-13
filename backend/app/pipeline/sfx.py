"""Sound effects that make clips feel professionally edited (CapCut-style).

Effects are SYNTHESIZED locally with ffmpeg (no external asset files), then mixed
onto the clip at keyword moments. This single audio pass also folds in optional
background music, so there is one clean place for all audio sweetening.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from ..config import WORK_DIR
from ..models import ClipCandidate

_SFX_DIR = WORK_DIR / "sfx"

# name -> ffmpeg lavfi source + shaping for a short one-shot
_RECIPES = {
    "pop":    "sine=frequency=760:duration=0.10,afade=t=out:st=0.02:d=0.08,volume=0.55",
    "ding":   "sine=frequency=1180:duration=0.42,afade=t=out:st=0.05:d=0.37,volume=0.5",
    "boom":   "sine=frequency=72:duration=0.5,afade=t=out:st=0.05:d=0.45,volume=0.8",
    "whoosh": "anoisesrc=d=0.34:color=brown,highpass=f=280,lowpass=f=3200,"
              "afade=t=in:st=0:d=0.12,afade=t=out:st=0.16:d=0.18,volume=0.6",
}


def _ensure(name: str) -> Path:
    _SFX_DIR.mkdir(parents=True, exist_ok=True)
    path = _SFX_DIR / f"{name}.wav"
    if path.exists():
        return path
    recipe = _RECIPES.get(name, _RECIPES["pop"])
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", recipe, "-ar", "44100", "-ac", "2", str(path)],
        check=True, capture_output=True, text=True,
    )
    return path


def plan(clip: ClipCandidate, which: str) -> list[tuple[float, str]]:
    """Return (time, sfx_name) hits at keyword moments (clip-relative seconds)."""
    if which == "none":
        return []
    kws = {k.lower() for k in clip.keywords}
    hits: list[tuple[float, str]] = []
    cycle = ["pop", "whoosh", "ding", "boom"]
    i = 0
    for w in clip.words:
        norm = "".join(ch for ch in w.text.lower() if ch.isalnum())
        if norm in kws:
            name = which if which != "mixed" else cycle[i % len(cycle)]
            hits.append((round(w.start - clip.start, 3), name))
            i += 1
        if len(hits) >= 8:
            break
    return hits


def mix(video: Path, hits: list[tuple[float, str]], music_path: str, music_vol: float, out: Path) -> Path:
    """Mix synthesized SFX (at `hits`) and optional music under the video's audio."""
    inputs = ["-i", str(video)]
    labels: list[str] = []
    parts: list[str] = []

    idx = 1
    for t, name in hits:
        sfx = _ensure(name)
        inputs += ["-i", str(sfx)]
        ms = int(max(0.0, t) * 1000)
        parts.append(f"[{idx}:a]adelay={ms}|{ms}[s{idx}]")
        labels.append(f"[s{idx}]")
        idx += 1

    has_music = music_vol > 0 and music_path and Path(music_path).exists()
    if has_music:
        inputs += ["-stream_loop", "-1", "-i", str(music_path)]
        parts.append(f"[{idx}:a]volume={min(1.0, music_vol):.2f}[mu]")
        labels.append("[mu]")
        idx += 1

    if not labels:
        return video  # nothing to do

    n = len(labels) + 1
    fc = ";".join(parts) + f";[0:a]{''.join(labels)}amix=inputs={n}:duration=first:dropout_transition=0[a]"
    cmd = [
        "ffmpeg", "-y", *inputs, "-filter_complex", fc,
        "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", str(out),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return out
