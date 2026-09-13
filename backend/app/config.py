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

# Drop a manually-downloaded Whisper model here and the app finds it instantly,
# with no internet needed. See MODELS_AR.md for exactly what to put inside.
MODELS_DIR = ROOT / "models"

for _d in (DATA_DIR, UPLOAD_DIR, OUTPUT_DIR, WORK_DIR, MODELS_DIR):
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
    # Optional: absolute path to a folder that contains a model.bin (a CTranslate2
    # faster-whisper model). If set and valid, it wins over everything else — use
    # it when your model lives outside the project. Empty => auto-detect (below).
    whisper_model_dir: str = ""

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

    # ---- Optional B-roll (Pexels free API; empty => B-roll disabled) ----
    pexels_api_key: str = ""

    # ---- Text-to-speech (faceless generator) ----
    tts_engine: str = "auto"             # auto | piper | edge
    piper_bin: str = ""                  # path to piper binary (offline TTS)
    piper_voice: str = ""                # path to a piper voice .onnx

    # ---- Server ----
    host: str = "127.0.0.1"
    port: int = 8000


settings = Settings()

# The only two Whisper models this app supports. Anything else falls back.
ALLOWED_WHISPER_MODELS = ("large-v3", "medium")

# The exact Hugging Face repositories the models come from (faster-whisper / CT2).
# You can download these by hand and drop the files into backend/models/.
WHISPER_REPO = {
    "large-v3": "Systran/faster-whisper-large-v3",
    "medium": "Systran/faster-whisper-medium",
}


def _is_ct2_model_dir(p: Path) -> bool:
    """A folder is a usable faster-whisper model if it contains a model.bin."""
    try:
        return p.is_dir() and (p / "model.bin").is_file()
    except OSError:
        return False


def find_local_whisper_model(name: str) -> Path | None:
    """Return a local folder holding this model, or None. No network, instant.

    Search order:
      1. IDEAFORGE_WHISPER_MODEL_DIR (explicit override), if it has a model.bin.
      2. backend/models/<various common folder names>, incl. a Hugging Face
         snapshot layout (…/snapshots/<hash>/model.bin) if you copied a cache folder.
    """
    if settings.whisper_model_dir.strip():
        p = Path(settings.whisper_model_dir).expanduser()
        if _is_ct2_model_dir(p):
            return p

    candidates = [
        f"faster-whisper-{name}",                      # our downloader uses this
        name,                                          # e.g. models/large-v3
        f"whisper-{name}",
        f"models--Systran--faster-whisper-{name}",     # a copied HF cache folder
    ]
    for c in candidates:
        p = MODELS_DIR / c
        if _is_ct2_model_dir(p):
            return p
        snaps = p / "snapshots"                        # HF cache layout
        if snaps.is_dir():
            for s in sorted(snaps.iterdir()):
                if _is_ct2_model_dir(s):
                    return s
    return None


def resolve_whisper_model(name: str) -> str:
    """What to hand faster-whisper: a local folder path if we have one, else the
    model name (faster-whisper then uses its own cache, or downloads once)."""
    name = name if name in ALLOWED_WHISPER_MODELS else "large-v3"
    local = find_local_whisper_model(name)
    return str(local) if local else name


def describe_whisper_model(name: str | None = None) -> dict:
    """Human-readable status of a model: is it local, and where. Used for logs
    and the check_models.py helper so you can confirm the app 'sees' your files."""
    name = name or settings.whisper_model
    name = name if name in ALLOWED_WHISPER_MODELS else "large-v3"
    local = find_local_whisper_model(name)
    return {
        "name": name,
        "repo": WHISPER_REPO.get(name, ""),
        "local_found": local is not None,
        "path": str(local) if local else "",
        "models_dir": str(MODELS_DIR),
    }
