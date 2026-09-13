@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title IdeaForge - Download Speech Model
set "VPY=.venv\Scripts\python.exe"

echo ==========================================
echo    Download the speech model (Whisper)
echo ==========================================
echo.

REM ---------- Python ----------
where python >nul 2>nul
if errorlevel 1 (
  echo [X] Python is not installed.
  echo     Install "Python 3.11" from the Microsoft Store, then run this file again.
  goto end
)

REM ---------- virtual environment ----------
if not exist "%VPY%" (
  echo First time: preparing environment...
  python -m venv .venv
)

REM ---------- make sure the downloader has what it needs ----------
"%VPY%" -c "import huggingface_hub, faster_whisper" >nul 2>nul
if errorlevel 1 (
  echo Installing what's needed to download (first time only)...
  "%VPY%" -m pip install --upgrade pip >nul
  "%VPY%" -m pip install faster-whisper huggingface_hub
)

echo.
echo Which model do you want?
echo    1 = large-v3   (BEST quality, about 3 GB)   [recommended]
echo    2 = medium     (lighter/faster, about 1.5 GB)
echo.
set "MODEL=large-v3"
set /p CHOICE=Type 1 or 2 then press Enter (or just press Enter for 1): 
if "%CHOICE%"=="2" set "MODEL=medium"

echo.
echo Downloading "%MODEL%"... this can take a while. Please wait.
echo.
"%VPY%" scripts\fetch_models.py %MODEL%

echo.
echo Checking what the app can see:
"%VPY%" scripts\check_models.py

echo.
echo ==========================================
echo  Done. If you saw [FOUND] above, you're ready.
echo  Now start the app with START.bat
echo ==========================================

:end
echo.
pause
