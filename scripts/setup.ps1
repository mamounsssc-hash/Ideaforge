# One-time setup for Windows (PowerShell).
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "> Checking ffmpeg..."
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  Write-Host "  x ffmpeg not found. Install it first (any one of):" -ForegroundColor Yellow
  Write-Host "     winget install Gyan.FFmpeg"
  Write-Host "     choco install ffmpeg"
  Write-Host "   Then re-open PowerShell and run setup again."
  exit 1
}
Write-Host "  + ffmpeg found"

Write-Host "> Creating Python virtual env (.venv)..."
python -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
Write-Host "> Installing Python dependencies..."
& ".\.venv\Scripts\pip.exe" install -r backend\requirements.txt

Write-Host "> Whisper model: downloading the default (large-v3) into backend\models\ ..."
Write-Host "  (Optional - the app also downloads it automatically on first use, and will"
Write-Host "   instantly detect any model you drop into backend\models\. See MODELS_AR.md.)"
& ".\.venv\Scripts\python.exe" scripts\fetch_models.py

Write-Host ""
Write-Host "+ Setup complete. Start the app with:  .\scripts\run.ps1" -ForegroundColor Green
Write-Host "  Check which models the app sees:     .\.venv\Scripts\python.exe scripts\check_models.py"
