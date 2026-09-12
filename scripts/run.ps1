# Start the local server on Windows, then open http://127.0.0.1:8000
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path ".venv")) {
  Write-Host "x .venv missing. Run .\scripts\setup.ps1 first." -ForegroundColor Yellow
  exit 1
}

$env:IDEAFORGE_HOST = if ($env:IDEAFORGE_HOST) { $env:IDEAFORGE_HOST } else { "127.0.0.1" }
$env:IDEAFORGE_PORT = if ($env:IDEAFORGE_PORT) { $env:IDEAFORGE_PORT } else { "8000" }
Write-Host "> IdeaForge Clipper at http://$($env:IDEAFORGE_HOST):$($env:IDEAFORGE_PORT)" -ForegroundColor Cyan

Start-Process "http://$($env:IDEAFORGE_HOST):$($env:IDEAFORGE_PORT)"
Set-Location backend
& "..\.venv\Scripts\uvicorn.exe" app.main:app --host $env:IDEAFORGE_HOST --port $env:IDEAFORGE_PORT
