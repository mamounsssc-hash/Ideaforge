"""Central configuration for the clipping engine.

All settings are overridable via environment variables (prefix IDEAFORGE_) or a
.env file, so the app stays fully local and free by default but can be pointed at
Qwen3-VL / Hermes / any OpenAI-compatible endpoint when you want smarter picks.
"""
from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


APP_VERSION = "3.1"          # bump when shipping an update the user should verify

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
    # Only the two best models are supported/pre-downloaded:
    #   large-v3 = highest accuracy (default), medium = lighter/faster.
    whisper_model: str = "large-v3"
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

    # ---- Captions ----
    # Colour-emoji font used for emoji glyphs (Windows ships "Segoe UI Emoji").
    # Set IDEAFORGE_EMOJI_FONT="" to disable the override (fall back to the style font).
    emoji_font: str = "Segoe UI Emoji"

    # ---- Optional B-roll (Pexels free API; empty => B-roll disabled) ----
    pexels_api_key: str = ""

    # ---- Optional real speaker diarization (pyannote.audio) ----
    # Needs a free HuggingFace token (accept the model terms once) + the model
    # download (~1-2 GB). Empty => falls back to the fast pause heuristic.
    hf_token: str = ""

    # ---- Text-to-speech (faceless generator) ----
    tts_engine: str = "auto"             # auto | piper | edge
    piper_bin: str = ""                  # path to piper binary (offline TTS)
    piper_voice: str = ""                # path to a piper voice .onnx

    # ---- Server ----
    host: str = "127.0.0.1"
    port: int = 8000


settings = Settings()

# The only two Whisper models this app ships with. Anything else falls back.
ALLOWED_WHISPER_MODELS = ("large-v3", "medium")


def resolve_whisper_model(name: str) -> str:
    return name if name in ALLOWED_WHISPER_MODELS else "large-v3"
