"""Visual polish that lifts retention: cinematic color grades and beat-style
zoom punches on keyword moments. Pure ffmpeg filter strings — free, offline.
"""
from __future__ import annotations

# Color-grade presets (applied to the footage, before captions).
GRADES: dict[str, str] = {
    "cinematic": "curves=preset=medium_contrast,eq=saturation=1.06:gamma=0.97,vignette=PI/5",
    "vibrant": "eq=contrast=1.12:saturation=1.4:brightness=0.02",
    "warm": "colorbalance=rm=0.06:gm=0.01:bm=-0.06,eq=saturation=1.08",
    "cold": "colorbalance=rm=-0.05:bm=0.07,eq=saturation=1.05",
    "mono": "hue=s=0,eq=contrast=1.18",
    "punchy": "eq=contrast=1.18:saturation=1.25:brightness=0.01,unsharp=5:5:0.6",
}


def color_grade(preset: str) -> str:
    return GRADES.get(preset, "")


def zoom_punch(times: list[float], tw: int, th: int, amp: float = 0.08, width: float = 0.11) -> str:
    """A quick scale 'beat' at each moment in `times` (clip-relative seconds).

    Scales the (already tw×th) footage up per frame with eval=frame, then centre-
    crops back to tw×th, so the picture pulses on emphasis while captions layered
    afterward stay perfectly still. Avoids the '^' operator (unsupported by some
    ffmpeg builds) by squaring via multiplication, and keeps the intermediate
    dimensions even.
    """
    times = [t for t in times if t is not None][:8]
    if not times:
        return ""
    # Gaussian bump per moment: amp * exp(-(( t - ti ) / width)^2)
    bumps = "+".join(
        f"{amp}*exp(-((t-{t:.2f})/{width})*((t-{t:.2f})/{width}))" for t in times
    )
    z = f"(1+{bumps})"
    return (
        f"scale=w='trunc(iw*{z}/2)*2':h='trunc(ih*{z}/2)*2':eval=frame,"
        f"crop={tw}:{th}"
    )
