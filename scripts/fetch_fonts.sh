#!/usr/bin/env bash
# Optional: download free fonts used by the caption styles (Anton, Bebas Neue,
# Archivo Black, Montserrat, Poppins) into assets/fonts. If skipped, libass falls
# back to a system sans-serif — captions still render, just with a different face.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p assets/fonts
cd assets/fonts

base="https://github.com/google/fonts/raw/main"
declare -A fonts=(
  ["Anton-Regular.ttf"]="$base/ofl/anton/Anton-Regular.ttf"
  ["BebasNeue-Regular.ttf"]="$base/ofl/bebasneue/BebasNeue-Regular.ttf"
  ["ArchivoBlack-Regular.ttf"]="$base/ofl/archivoblack/ArchivoBlack-Regular.ttf"
  ["Montserrat-Bold.ttf"]="$base/ofl/montserrat/Montserrat%5Bwght%5D.ttf"
  ["Poppins-Bold.ttf"]="$base/ofl/poppins/Poppins-Bold.ttf"
)
for name in "${!fonts[@]}"; do
  echo "▶ ${name}"
  curl -fsSL "${fonts[$name]}" -o "$name" || echo "  (skip: could not fetch $name)"
done
echo "✓ Fonts in assets/fonts (restart the app to pick them up)."
