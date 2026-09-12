"""In-memory job store with progress tracking (simple, dependency-free).

Good enough for a local single-user app. Swap for Redis/Celery later if you want
multi-user or persistence — the orchestrator only touches Job through this API.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Literal

from .models import ClipCandidate

Status = Literal["queued", "downloading", "transcribing", "analyzing", "ranking", "ready", "error"]


@dataclass
class Job:
    id: str
    status: Status = "queued"
    progress: float = 0.0
    message: str = "Queued"
    source_path: str = ""
    music_path: str = ""
    language: str = ""
    duration: float = 0.0
    clips: list[ClipCandidate] = field(default_factory=list)
    output_url: str = ""      # faceless generator: the finished video
    kind: str = "clip"        # "clip" | "create"
    error: str = ""
    created: float = field(default_factory=time.time)

    def to_public(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "progress": round(self.progress, 3),
            "message": self.message,
            "language": self.language,
            "duration": self.duration,
            "output_url": self.output_url,
            "kind": self.kind,
            "error": self.error,
            "clips": [
                {
                    "id": c.id,
                    "start": c.start,
                    "end": c.end,
                    "duration": c.duration,
                    "title": c.title,
                    "text": c.text,
                    "score": c.score.model_dump(),
                    "reason": c.reason,
                    "keywords": c.keywords,
                    "hashtags": c.hashtags,
                    "social_caption": c.social_caption,
                }
                for c in self.clips
            ],
        }


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self) -> Job:
        job = Job(id=uuid.uuid4().hex[:12])
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def update(self, job_id: str, **kw) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            for k, v in kw.items():
                setattr(job, k, v)

    def set_progress(self, job_id: str, status: Status, progress: float, message: str) -> None:
        self.update(job_id, status=status, progress=progress, message=message)


store = JobStore()
