"""Download a Whisper model the EASY way — straight into backend/models/ where the
app finds it instantly, offline, forever after.

Usage (from the project root, inside the .venv):
    python scripts/fetch_models.py                 # downloads the default: large-v3
    python scripts/fetch_models.py medium          # downloads the lighter model
    python scripts/fetch_models.py large-v3 medium # both

What it does:
  • If the model is ALREADY present (in backend/models/ or your machine's HF cache),
    it says so and skips — no re-download.
  • Otherwise it downloads the real files (model.bin + a few small text files) into
        backend/models/faster-whisper-<name>/
    which is exactly where the app looks first. No environment variables needed.

If this machine has no internet, don't use this script — download the files on any
other computer and copy that folder over. See MODELS_AR.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make backend importable so we reuse the SAME detection logic the app uses.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.config import (  # noqa: E402
    ALLOWED_WHISPER_MODELS,
    MODELS_DIR,
    WHISPER_REPO,
    find_local_whisper_model,
)


def fetch_one(name: str) -> bool:
    if name not in ALLOWED_WHISPER_MODELS:
        print(f"  x '{name}' is not supported. Use one of: {', '.join(ALLOWED_WHISPER_MODELS)}")
        return False

    existing = find_local_whisper_model(name)
    if existing:
        print(f"  = '{name}' is already here: {existing}  (skipping)")
        return True

    repo = WHISPER_REPO[name]
    dest = MODELS_DIR / f"faster-whisper-{name}"
    print(f"> downloading '{name}' from https://huggingface.co/{repo}")
    print(f"  into: {dest}")
    print("  (large-v3 is ~3 GB, medium is ~1.5 GB — this can take a while)")

    try:
        from huggingface_hub import snapshot_download
    except Exception:
        print("  ! huggingface_hub is missing. Install deps first: "
              "pip install -r backend/requirements.txt")
        return False

    try:
        snapshot_download(
            repo_id=repo,
            local_dir=str(dest),
            local_dir_use_symlinks=False,   # real files, easy to copy/move later
            allow_patterns=["*.bin", "*.json", "*.txt"],
        )
    except Exception as e:  # noqa: BLE001
        print(f"  x download failed: {e}")
        print("    You are probably offline. See MODELS_AR.md for the manual method.")
        return False

    if find_local_whisper_model(name):
        print(f"  + done. The app will now use '{name}' automatically.")
        return True
    print("  x downloaded, but model.bin was not found — check the folder above.")
    return False


def main() -> None:
    names = [a.strip() for a in sys.argv[1:] if a.strip()] or ["large-v3"]
    print(f"Target model folder: {MODELS_DIR}\n")
    ok = all(fetch_one(n) for n in names)
    print("\nDone." if ok else "\nFinished with problems — read the messages above.")


if __name__ == "__main__":
    main()
