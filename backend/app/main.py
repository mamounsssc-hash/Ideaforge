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

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import UPLOAD_DIR, OUTPUT_DIR, settings
from .jobs import store
from .models import RenderRequest
from .pipeline import orchestrator, render
from .styles import all_styles, get_style

app = FastAPI(title="IdeaForge Clipper", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

_executor = ThreadPoolExecutor(max_workers=2)
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


# ----------------------------- API models -----------------------------
class UrlRequest(BaseModel):
    url: str
    language: str | None = None


# ----------------------------- Analysis -------------------------------
@app.post("/api/upload")
async def upload(file: UploadFile = File(...), language: str | None = None):
    job = store.create()
    suffix = Path(file.filename or "video.mp4").suffix or ".mp4"
    dest = UPLOAD_DIR / f"{job.id}{suffix}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    threading.Thread(
        target=orchestrator.analyze,
        args=(job.id, str(dest), False, language),
        daemon=True,
    ).start()
    return {"job_id": job.id}


@app.post("/api/url")
async def from_url(req: UrlRequest):
    if not req.url.strip():
        raise HTTPException(400, "url is required")
    job = store.create()
    threading.Thread(
        target=orchestrator.analyze,
        args=(job.id, req.url.strip(), True, req.language),
        daemon=True,
    ).start()
    return {"job_id": job.id}


@app.get("/api/jobs/{job_id}")
async def job_status(job_id: str):
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return job.to_public()


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


# ----------------------------- Render ---------------------------------
@app.post("/api/render")
async def render_clip(req: RenderRequest):
    job = store.get(req.job_id)
    if not job:
        raise HTTPException(404, "job not found")
    clip = next((c for c in job.clips if c.id == req.clip_id), None)
    if not clip:
        raise HTTPException(404, "clip not found")
    style = get_style(req.style_id)
    source = Path(job.source_path)
    if not source.exists():
        raise HTTPException(410, "source media no longer available")

    loop = asyncio.get_event_loop()
    try:
        out_path: Path = await loop.run_in_executor(
            _executor,
            render.render_clip,
            source, clip, style, job.id, req.reframe, req.burn_captions,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"render failed: {type(e).__name__}: {e}")
    return {"file": out_path.name, "url": f"/api/file/{out_path.name}"}


@app.get("/api/file/{name}")
async def get_file(name: str):
    path = OUTPUT_DIR / name
    if not path.exists() or path.parent != OUTPUT_DIR:
        raise HTTPException(404, "file not found")
    return FileResponse(path, media_type="video/mp4", filename=name)


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
