"""Local speech-to-text with word-level timestamps (faster-whisper).

This is the free replacement for the paid AssemblyAI used by supoclip. Word-level
timestamps are what make word-by-word captions and clean cut boundaries possible.
The model is lazy-loaded once and cached.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from ..config import settings, resolve_whisper_model, find_local_whisper_model, WHISPER_REPO
from ..models import Segment, Word


class WhisperModelMissing(RuntimeError):
    """Raised when no model is available locally and it can't be downloaded."""


@lru_cache(maxsize=1)
def _get_model():
    from faster_whisper import WhisperModel  # imported lazily so the app boots without it

    device = settings.whisper_device
    compute = settings.whisper_compute_type
    if device == "auto":
        try:
            import torch  # noqa

            device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            device = "cpu"
    if compute == "auto":
        compute = "float16" if device == "cuda" else "int8"

    name = settings.whisper_model
    model = resolve_whisper_model(name)               # a local folder path, or the name
    is_local = find_local_whisper_model(name) is not None
    print(f"[whisper] loading '{name}' from "
          f"{'local folder: ' + model if is_local else 'name (cache/download)'} "
          f"on {device}/{compute}", flush=True)

    try:
        return WhisperModel(model, device=device, compute_type=compute)
    except Exception as e:  # noqa: BLE001
        # Most common cause: no model locally AND no internet to download it.
        repo = WHISPER_REPO.get(resolve_whisper_model(name) if is_local else name, "the model")
        raise WhisperModelMissing(
            f"Could not load the Whisper model '{name}'.\n"
            f"Nothing was found in backend/models/ and it could not be downloaded "
            f"(you may be offline).\n\n"
            f"Fix it in ONE of these ways:\n"
            f"  1) Run the downloader:   python scripts/fetch_models.py {name}\n"
            f"  2) Or download it by hand from https://huggingface.co/{repo} and put its\n"
            f"     files inside:  backend/models/faster-whisper-{name}/  (must include model.bin)\n"
            f"See MODELS_AR.md for step-by-step instructions.\n\n"
            f"Original error: {e}"
        ) from e


def transcribe(media_path: Path, language: str | None = None, progress=None,
               task: str = "transcribe") -> tuple[list[Segment], str]:
    """Return (segments, detected_language). `progress` is an optional callback(pct, msg).

    task="translate" makes Whisper output English regardless of the spoken language,
    keeping word-level timing — free multi-language -> English captions.
    """
    model = _get_model()
    lang = language if language is not None else settings.default_language
    seg_iter, info = model.transcribe(
        str(media_path),
        language=lang,
        task=task,
        word_timestamps=True,
        vad_filter=True,                    # skip long silences => tighter timestamps
        vad_parameters={"min_silence_duration_ms": 300},
        beam_size=5,
    )

    total = max(info.duration, 0.01)
    segments: list[Segment] = []
    for s in seg_iter:
        words = [
            Word(start=w.start, end=w.end, text=w.word.strip(), prob=getattr(w, "probability", 1.0) or 1.0)
            for w in (s.words or [])
            if w.word.strip()
        ]
        segments.append(Segment(start=s.start, end=s.end, text=s.text.strip(), words=words))
        if progress:
            progress(min(0.99, s.end / total), f"Transcribing… {int(s.end)}s")

    return segments, info.language
