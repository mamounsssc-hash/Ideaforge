@echo off
setlocal
cd /d "%~dp0"
title IdeaForge Clipper

echo ============================================
echo    IdeaForge Clipper - one-click launcher
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [X] Python was not found.
  echo     Install "Python 3.11" from the Microsoft Store, then double-click this file again.
  echo.
  pause
  exit /b 1
)

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo [!] ffmpeg was not found. Rendering may fail without it.
  echo     To install it, open PowerShell and run:  winget install Gyan.FFmpeg
  echo     Then close PowerShell and double-click this file again.
  echo     ^(Continuing anyway in case it is installed elsewhere...^)
  echo.
)

if not exist ".venv\Scripts\python.exe" (
  echo === First-time setup: installing everything once. This takes a few minutes. ===
  echo === Please leave this window open until it finishes.                       ===
  echo.
  python -m venv .venv
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\pip.exe" install -r "backend\requirements.txt"
  if errorlevel 1 (
    echo.
    echo [X] Setup failed while downloading packages. Check your internet and run this file again.
    pause
    exit /b 1
  )
  echo.
  echo === Setup done. ===
  echo.
)

echo === Starting the app. Your browser will open at http://127.0.0.1:8000 ===
echo === Keep THIS window open while using the app. Close it to stop.      ===
echo.
echo Note: the FIRST time you press "Find clips", it downloads the speech model
echo       (this needs normal internet, NOT a VPN). Later runs are offline.
echo.
start "" "http://127.0.0.1:8000"
cd backend
"..\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

echo.
echo The app has stopped. You can close this window.
pause
