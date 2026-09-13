@echo off
setlocal
cd /d "%~dp0"
title IdeaForge Clipper
set "VPY=.venv\Scripts\python.exe"

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
  echo     Install it: open PowerShell and run  winget install Gyan.FFmpeg
  echo     ^(Continuing anyway...^)
  echo.
)

if not exist "%VPY%" (
  echo === Creating environment... ===
  python -m venv .venv
)

REM --- make sure the app's packages are actually installed ---
"%VPY%" -c "import uvicorn, fastapi, numpy, httpx" >nul 2>nul
if errorlevel 1 (
  echo === Installing packages. First time only - takes a few minutes. Please wait... ===
  echo.
  "%VPY%" -m pip install --upgrade pip
  echo --- core (required) ---
  "%VPY%" -m pip install fastapi "uvicorn[standard]" python-multipart pydantic pydantic-settings numpy httpx websockets
  if errorlevel 1 (
    echo.
    echo [X] Could not install the core packages. Check your internet, then run this file again.
    pause
    exit /b 1
  )
  echo --- media (for clipping) ---
  "%VPY%" -m pip install faster-whisper yt-dlp opencv-python-headless edge-tts
  echo --- optional extras ^(ok if this one warns/fails^) ---
  "%VPY%" -m pip install mediapipe
  echo.
  echo === Packages installed. ===
  echo.
)

REM --- final check ---
"%VPY%" -c "import uvicorn" >nul 2>nul
if errorlevel 1 (
  echo [X] uvicorn still missing. Run this file again, or ask for help.
  pause
  exit /b 1
)

echo === Starting the app. Your browser will open at http://127.0.0.1:8000 ===
echo === Keep THIS window open while using the app. Close it to stop.      ===
echo.
echo Note: the FIRST time you press "Find clips" it downloads the speech model
echo       (normal internet, NOT a VPN). Later runs work offline.
echo.
start "" "http://127.0.0.1:8000"
cd backend
"..\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

echo.
echo The app has stopped. You can close this window.
pause
