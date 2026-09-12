"""Central configuration for the clipping engine.

All settings are overridable via environment variables (prefix IDEAFORGE_) or a
.env file, so the app stays fully local and free by default but can be pointed at
Qwen3-VL / Hermes / any OpenAI-compatible endpoint when you want smarter picks.
"""
from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parent.parent          # backend/
DATA_DIR = ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"
WORK_DIR = DATA_DIR / "work"
STYLES_DIR = Path(__file__).resolve().parent / "styles"
FONTS_DIR = ROOT.parent / "assets" / "fonts"

for _d in (DATA_DIR, UPLOAD_DIR, OUTPUT_DIR, WORK_DIR):
    _d.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IDEAFORGE_", env_file=".env", extra="ignore")

    # ---- Transcription ----
    whisper_model: str = "base"          # tiny/base/small/medium/large-v3
    whisper_device: str = "auto"         # auto/cpu/cuda
    whisper_compute_type: str = "auto"   # auto/int8/float16
    default_language: str | None = "en"  # None => auto-detect

    # ---- Clip selection ----
    min_clip_seconds: float = 15.0
    max_clip_seconds: float = 60.0
    target_clip_count: int = 10
    # Silence gap (seconds) that is allowed to end a clip on a natural boundary.
    boundary_silence: float = 0.35

    # ---- LLM layer (optional; empty base_url => layer is skipped, heuristics win) ----
    llm_enabled: bool = False
    llm_base_url: str = ""               # e.g. http://localhost:11434/v1 (Ollama) or Qwen3-VL server
    llm_model: str = "qwen2.5:7b"
    llm_api_key: str = "not-needed"      # local servers ignore this
    llm_timeout: float = 45.0
    llm_vision: bool = False             # True when pointing at Qwen3-VL (sends keyframes)

    # ---- Reframe ----
    reframe_enabled: bool = True
    target_width: int = 1080
    target_height: int = 1920            # 9:16

    # ---- Server ----
    host: str = "127.0.0.1"
    port: int = 8000


settings = Settings()
