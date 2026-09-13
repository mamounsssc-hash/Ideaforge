#!/usr/bin/env bash
# One-time setup for macOS / Linux.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "▶ Checking ffmpeg…"
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "  ✗ ffmpeg not found. Install it first:"
  echo "     macOS:  brew install ffmpeg"
  echo "     Ubuntu: sudo apt install -y ffmpeg"
  exit 1
fi
echo "  ✓ ffmpeg found"

echo "▶ Creating Python virtual env (.venv)…"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
echo "▶ Installing Python dependencies (this pulls faster-whisper, mediapipe, etc.)…"
pip install -r backend/requirements.txt

echo "▶ Whisper model: downloading the default (large-v3) into backend/models/ …"
echo "  (Optional — the app also downloads it automatically on first use, and will"
echo "   instantly detect any model you drop into backend/models/. See MODELS_AR.md.)"
python scripts/fetch_models.py || echo "  (skipped — run 'python scripts/fetch_models.py' later, or add it by hand)"

echo ""
echo "✓ Setup complete. Start the app with:  ./scripts/run.sh"
echo "  Check which models the app sees:     python scripts/check_models.py"
echo "  (Optional) better fonts:             ./scripts/fetch_fonts.sh"
