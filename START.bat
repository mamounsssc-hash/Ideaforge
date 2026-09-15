@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title IdeaForge Clipper
set "VPY=.venv\Scripts\python.exe"

echo ==========================================
echo    IdeaForge Clipper
echo ==========================================
echo.

REM ---------- Python ----------
where python >nul 2>nul
if errorlevel 1 (
  echo [X] Python is not installed.
  echo     Install "Python 3.11" from the Microsoft Store, then run this file again.
  goto end
)

REM ---------- ffmpeg: use system, local, or auto-download ----------
where ffmpeg >nul 2>nul
if not errorlevel 1 goto ffmpeg_ok
if exist "ffmpeg\bin\ffmpeg.exe" (
  set "PATH=%CD%\ffmpeg\bin;%PATH%"
  goto ffmpeg_ok
)
echo ffmpeg was not found. Downloading a local copy once ^(about 100 MB^)...
curl -L -o ffmpeg.zip "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
if errorlevel 1 (
  echo [!] Could not download ffmpeg. The app will still open, but rendering needs it.
  goto ffmpeg_ok
)
if exist ffmpeg_tmp rmdir /s /q ffmpeg_tmp
mkdir ffmpeg_tmp
tar -xf ffmpeg.zip -C ffmpeg_tmp
for /d %%D in (ffmpeg_tmp\*) do set "FF=%%D"
if not exist ffmpeg mkdir ffmpeg
xcopy /e /i /y "!FF!\bin" "ffmpeg\bin" >nul
del ffmpeg.zip >nul 2>nul
rmdir /s /q ffmpeg_tmp >nul 2>nul
set "PATH=%CD%\ffmpeg\bin;%PATH%"
echo ffmpeg is ready.
:ffmpeg_ok

REM ---------- virtual environment ----------
if not exist "%VPY%" (
  echo Creating environment...
  python -m venv .venv
)

REM ---------- packages ----------
"%VPY%" -c "import uvicorn, fastapi, numpy, httpx, pydantic_settings, multipart" >nul 2>nul
if not errorlevel 1 goto run
echo.
echo Installing packages. First time only - a few minutes. Please wait...
echo.
"%VPY%" -m pip install --upgrade pip
"%VPY%" -m pip install fastapi "uvicorn[standard]" python-multipart pydantic pydantic-settings numpy httpx websockets
if errorlevel 1 (
  echo.
  echo [X] Could not install the core packages. Check your internet, then run this file again.
  goto end
)
"%VPY%" -m pip install faster-whisper yt-dlp opencv-python-headless edge-tts
"%VPY%" -m pip install mediapipe
echo.
echo Packages installed.

:run
"%VPY%" -c "import uvicorn" >nul 2>nul
if errorlevel 1 (
  echo [X] Something is still missing. Please run this file once more.
  goto end
)

REM ---------- optional GPU acceleration (NVIDIA) ----------
REM If the CUDA libraries are installed (SETUP.bat installs them), use the GPU.
REM transcribe.py falls back to CPU automatically if CUDA is unavailable, so this is safe.
set "CUDNN=%CD%\.venv\Lib\site-packages\nvidia\cudnn\bin"
set "CUBLAS=%CD%\.venv\Lib\site-packages\nvidia\cublas\bin"
if exist "%CUDNN%" (
  set "PATH=%CUDNN%;%CUBLAS%;%PATH%"
  set "IDEAFORGE_WHISPER_DEVICE=cuda"
  echo GPU libraries found - using CUDA if possible.
)

REM ---------- AI clip selection via OpenRouter (works worldwide) ----------
REM Get a free key: openrouter.ai/keys (no VPN needed)
REM Primary model = Gemini. If it fails, auto-tries the free fallback models.
set "IDEAFORGE_LLM_ENABLED=true"
set "IDEAFORGE_LLM_BASE_URL=https://openrouter.ai/api/v1"
set "IDEAFORGE_LLM_MODEL=google/gemini-2.5-flash-preview-05-20:free"
set "IDEAFORGE_LLM_FALLBACK_MODELS=meta-llama/llama-3.3-70b-instruct:free,mistralai/mistral-small-3.1-24b-instruct:free"
set "IDEAFORGE_LLM_API_KEY=PASTE_YOUR_OPENROUTER_KEY"
set "IDEAFORGE_LLM_VISION=false"
echo.
echo ==========================================
echo  Starting. Your browser opens at:
echo    http://127.0.0.1:8000
echo  Keep THIS window open while using the app.
echo  Close it to stop.
echo ==========================================
echo.
echo Note: the FIRST "Find clips" downloads the speech model
echo       ^(normal internet, NOT a VPN^). Later runs are offline.
echo.
start "" "http://127.0.0.1:8000"
cd backend
"..\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

:end
echo.
echo The app has stopped. You can close this window.
pause
