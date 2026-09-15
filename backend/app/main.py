"""FastAPI application: upload/URL -> analyze -> pick style -> render -> download.

Runs fully locally. Serves the web UI from ../frontend so a user just opens
http://127.0.0.1:8000 after `run`.
"""
from __future__ import annotations

import asyncio
import shutil
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import zipfile

from .config import UPLOAD_DIR, OUTPUT_DIR, WORK_DIR, settings, APP_VERSION
from .jobs import store
from .models import RenderRequest, BatchRenderRequest, AnalyzeOptions, WordsUpdate, CreateOptions
from .pipeline import orchestrator, render, create as create_pipeline
from .pipeline import tts
from .styles import all_styles, get_style

print(f"[IdeaForge] backend build v{APP_VERSION} ready — up to 100 clips, gameplay, frame picker",
      flush=True)

app = FastAPI(title="IdeaForge Clipper", version=APP_VERSION)


@app.get("/api/version")
async def version():
    return {"version": APP_VERSION}
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

_executor = ThreadPoolExecutor(max_workers=2)
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


# ----------------------------- API models -----------------------------
class UrlRequest(AnalyzeOptions):
    url: str


class LocalRequest(AnalyzeOptions):
    path: str


# ----------------------------- Analysis -------------------------------
@app.post("/api/upload")
async def upload(
    file: UploadFile = File(...),
    language: str | None = None,
    caption_language: str = "original",
    topic: str = "",
    min_seconds: float | None = None,
    max_seconds: float | None = None,
    target_count: int | None = None,
):
    job = store.create()
    suffix = Path(file.filename or "video.mp4").suffix or ".mp4"
    dest = UPLOAD_DIR / f"{job.id}{suffix}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    opts = AnalyzeOptions(
        language=language, caption_language=caption_language, topic=topic,
        min_seconds=min_seconds, max_seconds=max_seconds, target_count=target_count,
    )
    threading.Thread(
        target=orchestrator.analyze, args=(job.id, str(dest), False, opts), daemon=True,
    ).start()
    return {"job_id": job.id}


@app.post("/api/url")
async def from_url(req: UrlRequest):
    if not req.url.strip():
        raise HTTPException(400, "url is required")
    job = store.create()
    opts = AnalyzeOptions(**req.model_dump(exclude={"url"}))
    threading.Thread(
        target=orchestrator.analyze, args=(job.id, req.url.strip(), True, opts), daemon=True,
    ).start()
    return {"job_id": job.id}


@app.post("/api/local")
async def from_local(req: LocalRequest):
    """Analyze a file already on disk (no upload) — ideal for huge 4–5 GB videos.

    The user downloads the video (e.g. from Google Drive) and just pastes its
    path; we read it in place, so there's no slow browser upload and no second
    copy eating disk space.
    """
    raw = req.path.strip().strip('"').strip("'")
    if not raw:
        raise HTTPException(400, "path is required")
    p = Path(raw).expanduser()
    if not p.exists() or not p.is_file():
        raise HTTPException(400, f"file not found: {p}")
    job = store.create()
    opts = AnalyzeOptions(**req.model_dump(exclude={"path"}))
    threading.Thread(
        target=orchestrator.analyze, args=(job.id, str(p), False, opts), daemon=True,
    ).start()
    return {"job_id": job.id}


@app.get("/api/jobs/{job_id}/source")
async def job_source(job_id: str):
    """Stream the original video (range-enabled) so the browser can preview clips."""
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    src = Path(job.source_path)
    if not src.exists():
        raise HTTPException(410, "source media no longer available")
    ext = src.suffix.lower()
    media = {".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm",
             ".mkv": "video/x-matroska", ".m4v": "video/mp4"}.get(ext, "video/mp4")
    return FileResponse(src, media_type=media)   # Starlette handles HTTP Range


@app.post("/api/jobs/{job_id}/music")
async def upload_music(job_id: str, file: UploadFile = File(...)):
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    suffix = Path(file.filename or "music.mp3").suffix or ".mp3"
    dest = UPLOAD_DIR / f"{job_id}_music{suffix}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    store.update(job_id, music_path=str(dest))
    return {"ok": True, "music": dest.name}


@app.post("/api/jobs/{job_id}/gameplay")
async def upload_gameplay(job_id: str, file: UploadFile = File(...)):
    """Upload a looping gameplay video (e.g. Subway Surfers) for split-screen."""
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    suffix = Path(file.filename or "game.mp4").suffix or ".mp4"
    dest = UPLOAD_DIR / f"{job_id}_gameplay{suffix}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    store.update(job_id, gameplay_path=str(dest))
    return {"ok": True, "gameplay": dest.name}


@app.get("/api/jobs/{job_id}")
async def job_status(job_id: str):
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return job.to_public()


# ---- In-browser transcript editing ----
@app.get("/api/jobs/{job_id}/clips/{clip_id}/words")
async def get_words(job_id: str, clip_id: str):
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    clip = next((c for c in job.clips if c.id == clip_id), None)
    if not clip:
        raise HTTPException(404, "clip not found")
    return {"words": [{"start": w.start, "end": w.end, "text": w.text} for w in clip.words]}


@app.get("/api/jobs/{job_id}/clips/{clip_id}/thumb")
async def clip_thumb(job_id: str, clip_id: str):
    """A single downscaled frame from the middle of the clip, for the frame picker."""
    import subprocess
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    clip = next((c for c in job.clips if c.id == clip_id), None)
    if not clip:
        raise HTTPException(404, "clip not found")
    source = Path(job.source_path)
    if not source.exists():
        raise HTTPException(410, "source media no longer available")
    t = max(0.0, (clip.start + clip.end) / 2.0)
    out = WORK_DIR / f"{job_id}_{clip_id}_thumb.jpg"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", str(source),
             "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "4", str(out)],
            check=True, capture_output=True, text=True,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"thumb failed: {type(e).__name__}")
    return FileResponse(out, media_type="image/jpeg")


@app.post("/api/jobs/{job_id}/clips/{clip_id}/words")
async def set_words(job_id: str, clip_id: str, body: WordsUpdate):
    from .models import Word
    from .pipeline import keywords as kw
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    clip = next((c for c in job.clips if c.id == clip_id), None)
    if not clip:
        raise HTTPException(404, "clip not found")
    new_words = [Word(start=w.start, end=w.end, text=w.text) for w in body.words if w.text.strip()]
    clip.words = new_words
    clip.text = " ".join(w.text for w in new_words).strip()
    clip.keywords = kw.extract_keywords(clip.text, top_n=6)
    clip.hashtags = kw.hashtags(clip.text, extra=clip.keywords)
    return {"ok": True, "text": clip.text}


@app.websocket("/ws/{job_id}")
async def ws_progress(ws: WebSocket, job_id: str):
    await ws.accept()
    try:
        while True:
            job = store.get(job_id)
            if not job:
                await ws.send_json({"error": "job not found"})
                break
            await ws.send_json(job.to_public())
            if job.status in ("ready", "error"):
                break
            await asyncio.sleep(0.6)
    except WebSocketDisconnect:
        pass


# ----------------------------- Styles ---------------------------------
@app.get("/api/styles")
async def styles():
    return [s.model_dump() for s in all_styles()]


# ----------------------------- Faceless generator (Crayo-style) --------
@app.get("/api/voices")
async def voices():
    return tts.VOICES


@app.post("/api/create")
async def create_video(
    options: str = Form(...),
    background: UploadFile | None = File(None),
    music: UploadFile | None = File(None),
):
    try:
        opts = CreateOptions.model_validate_json(options)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"invalid options: {e}")
    if not opts.script.strip() and not opts.topic.strip():
        raise HTTPException(400, "provide a script or a topic")

    job = store.create()
    bg_path = None
    if background is not None:
        bg_path = str(UPLOAD_DIR / f"{job.id}_bg{Path(background.filename or '.mp4').suffix or '.mp4'}")
        with open(bg_path, "wb") as f:
            shutil.copyfileobj(background.file, f)
    music_path = ""
    if music is not None:
        music_path = str(UPLOAD_DIR / f"{job.id}_music{Path(music.filename or '.mp3').suffix or '.mp3'}")
        with open(music_path, "wb") as f:
            shutil.copyfileobj(music.file, f)

    threading.Thread(
        target=create_pipeline.create_faceless,
        args=(job.id, opts, bg_path, music_path), daemon=True,
    ).start()
    return {"job_id": job.id}


# ----------------------------- Render ---------------------------------
@app.post("/api/render")
async def render_clip(req: RenderRequest):
    job = store.get(req.job_id)
    if not job:
        raise HTTPException(404, "job not found")
    clip = next((c for c in job.clips if c.id == req.clip_id), None)
    if not clip:
        raise HTTPException(404, "clip not found")
    clip = _apply_overrides(clip, req)
    style = get_style(req.style_id)
    source = Path(job.source_path)
    if not source.exists():
        raise HTTPException(410, "source media no longer available")

    loop = asyncio.get_event_loop()
    try:
        out_path: Path = await loop.run_in_executor(
            _executor, render.render_clip, source, clip, style, job.id, req,
            job.music_path, job.gameplay_path,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"render failed: {type(e).__name__}: {e}")
    return {"file": out_path.name, "url": f"/api/file/{out_path.name}"}


def _apply_overrides(clip, req):
    """Return a copy of the clip with UI trim / title edits applied."""
    from copy import deepcopy
    c = deepcopy(clip)
    if req.title_override is not None:
        c.title = req.title_override[:80]
    s = req.start_override if req.start_override is not None else c.start
    e = req.end_override if req.end_override is not None else c.end
    if e > s:
        c.start, c.end = float(s), float(e)
        c.words = [w for w in c.words if w.start >= c.start - 0.05 and w.start < c.end]
    return c


# Background batch tracker: batch_id -> progress dict. Renders run in a worker
# thread so exporting 100 clips never blocks (or times out) the HTTP request.
_batches: dict[str, dict] = {}


@app.post("/api/render_batch")
async def render_batch(req: BatchRenderRequest):
    """Start rendering several clips in one style; poll /api/render_batch/{id}."""
    job = store.get(req.job_id)
    if not job:
        raise HTTPException(404, "job not found")
    source = Path(job.source_path)
    if not source.exists():
        raise HTTPException(410, "source media no longer available")
    style = get_style(req.style_id)
    clips = job.clips if not req.clip_ids else [c for c in job.clips if c.id in req.clip_ids]
    if not clips:
        raise HTTPException(400, "no clips to render")

    batch_id = uuid.uuid4().hex[:12]
    _batches[batch_id] = {"status": "running", "done": 0, "failed": 0,
                          "total": len(clips), "url": "", "file": "", "error": ""}

    def _work() -> None:
        outputs: list[tuple] = []
        for c in clips:
            try:
                p = render.render_clip(source, c, style, job.id, req,
                                       job.music_path, job.gameplay_path)
                outputs.append((c, p))
            except Exception:  # noqa: BLE001 — one bad clip never stops the batch
                _batches[batch_id]["failed"] += 1
            _batches[batch_id]["done"] += 1
        if not outputs:
            _batches[batch_id].update(status="error", error="all clips failed to render")
            return
        try:
            zip_path = OUTPUT_DIR / f"{job.id}_{req.style_id}_{req.aspect_ratio.replace(':', 'x')}_batch.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:
                for i, (c, p) in enumerate(outputs, start=1):
                    safe = "".join(ch for ch in (c.title or f"clip{i}") if ch.isalnum() or ch in " -_")[:40].strip()
                    zf.write(p, arcname=f"{i:02d}_{safe or 'clip'}.mp4")
            _batches[batch_id].update(status="ready", url=f"/api/file/{zip_path.name}", file=zip_path.name)
        except Exception as e:  # noqa: BLE001
            _batches[batch_id].update(status="error", error=f"{type(e).__name__}: {e}")

    threading.Thread(target=_work, daemon=True).start()
    return {"batch_id": batch_id, "total": len(clips)}


@app.get("/api/render_batch/{batch_id}")
async def render_batch_status(batch_id: str):
    b = _batches.get(batch_id)
    if not b:
        raise HTTPException(404, "batch not found")
    return b


@app.get("/api/file/{name}")
async def get_file(name: str):
    path = OUTPUT_DIR / name
    if not path.exists() or path.parent != OUTPUT_DIR:
        raise HTTPException(404, "file not found")
    media = "application/zip" if name.endswith(".zip") else "video/mp4"
    return FileResponse(path, media_type=media, filename=name)


@app.get("/api/health")
async def health():
    return {"ok": True, "llm": settings.llm_enabled, "styles": len(all_styles())}


# ----------------------------- Frontend -------------------------------
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
else:
    @app.get("/")
    async def root():
        return JSONResponse({"msg": "IdeaForge Clipper API. Frontend not found."})
