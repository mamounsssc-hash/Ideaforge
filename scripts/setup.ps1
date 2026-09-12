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

Write-Host "> Pre-downloading the two Whisper models (large-v3, medium)..."
& ".\.venv\Scripts\python.exe" scripts\fetch_models.py

Write-Host ""
Write-Host "+ Setup complete. Start the app with:  .\scripts\run.ps1" -ForegroundColor Green
