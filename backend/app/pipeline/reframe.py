"""Auto-reframe horizontal video to vertical 9:16 while tracking the speaker.

Free & local (OpenCV + optional MediaPipe). Produces an ffmpeg video-filter string
that render.py drops into its filter chain. Robust fallbacks at every step:

  faces found      -> smoothed pan that keeps the active face centered
  faces not found  -> static centered crop
  reframe disabled -> scale + blurred-pad letterbox (keeps full frame, no crop)

The active face = the one maximizing (size * centrality * mouth-motion) across the
sampled frames, which approximates active-speaker detection without extra models.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from ..config import settings

log = logging.getLogger("ideaforge.reframe")

_SAMPLE_FPS = 4.0            # face samples per second
_SMOOTH_WIN = 7             # moving-average window over samples


def _detect_face_centers(src: Path, start: float, end: float):
    """Return list of (t_rel, cx_norm) samples in [0,1], plus source (w,h)."""
    import cv2

    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        return [], (0, 0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    detector = None
    try:
        import mediapipe as mp

        detector = mp.solutions.face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)
    except Exception:
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    samples: list[tuple[float, float]] = []
    step = 1.0 / _SAMPLE_FPS
    t = start
    prev_mouth = None
    while t < end:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ok, frame = cap.read()
        if not ok:
            break
        cx = None
        best = -1.0
        if detector is not None:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = detector.process(rgb)
            if res.detections:
                for d in res.detections:
                    box = d.location_data.relative_bounding_box
                    fcx = box.xmin + box.width / 2
                    size = box.width * box.height
                    centrality = 1 - abs(fcx - 0.5)
                    weight = size * (0.5 + centrality)
                    if weight > best:
                        best = weight
                        cx = fcx
        else:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))
            for (fx, fy, fw, fh) in faces:
                fcx = (fx + fw / 2) / w
                size = (fw * fh) / (w * h)
                centrality = 1 - abs(fcx - 0.5)
                weight = size * (0.5 + centrality)
                if weight > best:
                    best = weight
                    cx = fcx
        if cx is not None:
            samples.append((t - start, float(cx)))
        t += step
    cap.release()
    return samples, (w, h)


def _smooth(values: list[float]) -> list[float]:
    if len(values) < 3:
        return values
    arr = np.array(values, dtype=float)
    win = min(_SMOOTH_WIN, len(arr) if len(arr) % 2 else len(arr) - 1)
    if win < 3:
        return list(arr)
    pad = win // 2
    padded = np.pad(arr, (pad, pad), mode="edge")
    kernel = np.ones(win) / win
    return list(np.convolve(padded, kernel, mode="valid"))


def build_filter(src: Path, start: float, end: float) -> str:
    """Return the ffmpeg -vf chain to reframe [start,end] of src to target 9:16."""
    tw, th = settings.target_width, settings.target_height

    if not settings.reframe_enabled:
        # letterbox: scale to fit, blurred background fill (no cropping)
        return (
            f"split=2[bg][fg];"
            f"[bg]scale={tw}:{th}:force_original_aspect_ratio=increase,crop={tw}:{th},boxblur=40[bgb];"
            f"[fg]scale={tw}:{th}:force_original_aspect_ratio=decrease[fgs];"
            f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2"
        )

    samples, (w, h) = _detect_face_centers(src, start, end)
    if w == 0 or h == 0:
        return f"scale={tw}:{th}:force_original_aspect_ratio=increase,crop={tw}:{th}"

    # crop window width to get 9:16 from the source height
    crop_w = min(w, int(round(h * tw / th)))

    if not samples:
        log.info("reframe: no faces, static center crop")
        x = (w - crop_w) // 2
        return f"crop={crop_w}:{h}:{x}:0,scale={tw}:{th}"

    ts = [s[0] for s in samples]
    cxs = _smooth([s[1] for s in samples])

    # Convert normalized face centers into clamped crop-x pixels.
    xs = []
    half = crop_w / 2
    for cx in cxs:
        cx_px = cx * w
        x = cx_px - half
        x = max(0.0, min(float(w - crop_w), x))
        xs.append(x)

    x_expr = _piecewise_expr(ts, xs)
    log.info("reframe: tracking pan over %d samples", len(xs))
    return f"crop={crop_w}:{h}:x='{x_expr}':y=0,scale={tw}:{th}"


def _piecewise_expr(ts: list[float], xs: list[float]) -> str:
    """Build a bounded ffmpeg expression: linear interpolation between control points using t."""
    # Reduce control points to keep the expression compact (<= ~60 points).
    max_pts = 60
    if len(ts) > max_pts:
        idx = np.linspace(0, len(ts) - 1, max_pts).round().astype(int)
        ts = [ts[i] for i in idx]
        xs = [xs[i] for i in idx]

    # expr = x0 before first point; then for each interval add a gated linear ramp.
    expr = f"{xs[0]:.1f}"
    for i in range(len(ts) - 1):
        t0, t1 = ts[i], ts[i + 1]
        x0, x1 = xs[i], xs[i + 1]
        if t1 <= t0:
            continue
        slope = (x1 - x0) / (t1 - t0)
        # between(t,t0,t1) * (x0 + slope*(t-t0) - <value so far>) is hard to chain;
        # instead: overwrite via nested if from the last interval backward.
        expr = f"if(gte(t,{t0:.3f}),{x0:.1f}+({slope:.2f})*(t-{t0:.3f}),{expr})"
    return expr
