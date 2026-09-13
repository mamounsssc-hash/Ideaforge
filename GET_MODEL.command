#!/usr/bin/env bash
# Double-click on macOS to download the speech model into backend/models/.
cd "$(dirname "$0")"
VPY=".venv/bin/python"

echo "=========================================="
echo "   Download the speech model (Whisper)"
echo "=========================================="

if ! command -v python3 >/dev/null 2>&1; then
  echo "[X] Python 3 is not installed. Install it first, then run this again."
  read -r -p "Press Enter to close."; exit 1
fi

[ -x "$VPY" ] || { echo "First time: preparing environment..."; python3 -m venv .venv; }

if ! "$VPY" -c "import huggingface_hub, faster_whisper" >/dev/null 2>&1; then
  echo "Installing what's needed to download (first time only)..."
  "$VPY" -m pip install --upgrade pip >/dev/null
  "$VPY" -m pip install faster-whisper huggingface_hub
fi

echo ""
echo "Which model do you want?"
echo "   1 = large-v3   (BEST quality, ~3 GB)   [recommended]"
echo "   2 = medium     (lighter/faster, ~1.5 GB)"
echo ""
read -r -p "Type 1 or 2 then Enter (or just Enter for 1): " CHOICE
MODEL="large-v3"; [ "$CHOICE" = "2" ] && MODEL="medium"

echo ""
echo "Downloading \"$MODEL\"... this can take a while. Please wait."
"$VPY" scripts/fetch_models.py "$MODEL"

echo ""
echo "Checking what the app can see:"
"$VPY" scripts/check_models.py

echo ""
echo "Done. If you saw [FOUND] above, you're ready. Start the app with START_MAC.command"
read -r -p "Press Enter to close."
