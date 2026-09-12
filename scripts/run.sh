#!/usr/bin/env bash
# Start the local server, then open http://127.0.0.1:8000
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  echo "✗ .venv missing. Run ./scripts/setup.sh first."; exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate

HOST="${IDEAFORGE_HOST:-127.0.0.1}"
PORT="${IDEAFORGE_PORT:-8000}"
echo "▶ IdeaForge Clipper running at http://$HOST:$PORT"
cd backend
exec uvicorn app.main:app --host "$HOST" --port "$PORT"
