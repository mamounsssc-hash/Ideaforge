"""Download the Whisper speech model from inside the app (one button in the UI).

Keeps a tiny in-memory state so the browser can poll progress. The model lands in
backend/models/faster-whisper-<name>/ where config.find_local_whisper_model() picks
it up automatically — no restart, no env vars, no terminal.
"""
from __future__ import annotations

import threading
from pathlib import Path

from ..config import (
    ALLOWED_WHISPER_MODELS,
    MODELS_DIR,
    WHISPER_REPO,
    find_local_whisper_model,
    settings,
)

# Rough total download sizes, just for a friendly progress bar (not exact).
_APPROX_BYTES = {"large-v3": 3_100_000_000, "medium": 1_530_000_000}

_state = {
    "status": "idle",     # idle | downloading | done | error
    "model": "",
    "message": "",
    "error": "",
}
_lock = threading.Lock()


def _dir_size(p: Path) -> int:
    total = 0
    if not p.exists():
        return 0
    for f in p.rglob("*"):
        try:
            if f.is_file():
                total += f.stat().st_size
        except OSError:
            pass
    return total


def _run_download(name: str) -> None:
    dest = MODELS_DIR / f"faster-whisper-{name}"
    try:
        from huggingface_hub import snapshot_download
        snapshot_download(
            repo_id=WHISPER_REPO[name],
            local_dir=str(dest),
            local_dir_use_symlinks=False,
            allow_patterns=["*.bin", "*.json", "*.txt"],
        )
        if find_local_whisper_model(name):
            with _lock:
                _state.update(status="done", message="Model ready.", error="")
        else:
            with _lock:
                _state.update(status="error", error="Downloaded but model.bin missing.")
    except Exception as e:  # noqa: BLE001
        with _lock:
            _state.update(status="error",
                          error=f"{type(e).__name__}: {e}. Check your internet and try again.")


def start_download(name: str | None = None) -> dict:
    name = (name or settings.whisper_model)
    name = name if name in ALLOWED_WHISPER_MODELS else "large-v3"
    with _lock:
        if _state["status"] == "downloading":
            return status()
        if find_local_whisper_model(name):
            _state.update(status="done", model=name, message="Model already present.", error="")
            return status()
        _state.update(status="downloading", model=name, message="Starting download…", error="")
    threading.Thread(target=_run_download, args=(name,), daemon=True).start()
    return status()


def status() -> dict:
    with _lock:
        st = dict(_state)
    name = st.get("model") or (settings.whisper_model if settings.whisper_model in ALLOWED_WHISPER_MODELS else "large-v3")
    present = find_local_whisper_model(name) is not None

    # If a model is already on disk and we're not mid-download, report ready.
    if present and st["status"] != "downloading":
        st["status"] = "done"

    progress = 0.0
    if st["status"] == "downloading":
        got = _dir_size(MODELS_DIR / f"faster-whisper-{name}")
        total = _APPROX_BYTES.get(name, 3_100_000_000)
        progress = max(0.01, min(0.99, got / total))
    elif st["status"] == "done":
        progress = 1.0

    return {
        "selected": settings.whisper_model,
        "model": name,
        "present": present,
        "status": st["status"],
        "progress": round(progress, 3),
        "message": st.get("message", ""),
        "error": st.get("error", ""),
        "size_hint": "≈3 GB" if name == "large-v3" else "≈1.5 GB",
        "allowed": list(ALLOWED_WHISPER_MODELS),
    }
