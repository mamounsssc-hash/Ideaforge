#!/bin/bash
# Double-click this file on macOS to set up (first time) and run the app.
cd "$(dirname "$0")"
echo "=== IdeaForge Clipper ==="

if ! command -v python3 >/dev/null 2>&1; then
  echo "[X] Python 3 not found. Install from https://www.python.org/downloads/ then run again."
  read -n1 -r -p "Press any key to close..."; exit 1
fi
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "[!] ffmpeg not found. Install with:  brew install ffmpeg   (continuing anyway)"
fi

VPY=".venv/bin/python"
[ -x "$VPY" ] || python3 -m venv .venv

if ! "$VPY" -c "import uvicorn, fastapi, numpy, httpx" >/dev/null 2>&1; then
  echo "=== Installing packages (first time only, a few minutes)... ==="
  "$VPY" -m pip install --upgrade pip
  "$VPY" -m pip install fastapi "uvicorn[standard]" python-multipart pydantic pydantic-settings numpy httpx websockets || { echo "[X] core install failed. Check internet."; read -n1 -r; exit 1; }
  "$VPY" -m pip install faster-whisper yt-dlp opencv-python-headless edge-tts
  "$VPY" -m pip install mediapipe || true
fi

echo "=== Starting. Opening http://127.0.0.1:8000 (keep this window open) ==="
( sleep 2; open "http://127.0.0.1:8000" ) &
cd backend
../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
