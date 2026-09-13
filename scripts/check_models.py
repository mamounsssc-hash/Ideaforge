"""Show exactly what the app sees for each Whisper model — a 5-second sanity check.

Run it any time you drop files into backend/models/ to confirm they're detected:
    python scripts/check_models.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.config import ALLOWED_WHISPER_MODELS, MODELS_DIR, describe_whisper_model, settings  # noqa: E402


def main() -> None:
    print(f"Models folder : {MODELS_DIR}")
    print(f"Selected model: {settings.whisper_model}")
    if settings.whisper_model_dir.strip():
        print(f"Override path : {settings.whisper_model_dir}")
    print("-" * 60)
    any_found = False
    for name in ALLOWED_WHISPER_MODELS:
        d = describe_whisper_model(name)
        if d["local_found"]:
            any_found = True
            print(f"  [FOUND]   {name:9s} -> {d['path']}")
        else:
            print(f"  [missing] {name:9s} -> not local (will download when first used)")
    print("-" * 60)
    if any_found:
        print("At least one model is local. The app will use it instantly, offline.")
    else:
        print("No local model yet. Either run:  python scripts/fetch_models.py")
        print("or drop the files in by hand — see MODELS_AR.md.")


if __name__ == "__main__":
    main()
