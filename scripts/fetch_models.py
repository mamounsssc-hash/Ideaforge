"""Pre-download only the two supported Whisper models so the app works offline.

  large-v3  = highest accuracy (default)
  medium    = lighter / faster alternative

Downloads the CTranslate2 weights into the faster-whisper cache. Safe to re-run.
"""
from __future__ import annotations

MODELS = ("large-v3", "medium")


def main() -> None:
    try:
        from faster_whisper.utils import download_model
    except Exception:  # pragma: no cover
        download_model = None

    for name in MODELS:
        print(f"> fetching Whisper '{name}' …")
        try:
            if download_model:
                download_model(name)
            else:
                from faster_whisper import WhisperModel
                WhisperModel(name, device="cpu", compute_type="int8")
            print(f"  + {name} ready")
        except Exception as e:  # noqa: BLE001
            print(f"  x could not fetch {name}: {e}")
    print("Done. Models are cached for offline use.")


if __name__ == "__main__":
    main()
