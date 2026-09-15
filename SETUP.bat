@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title CliPro - One-time Setup
set "VPY=.venv\Scripts\python.exe"

echo ==========================================
echo    CliPro - One-time Setup
echo    Installs EVERYTHING in one place.
echo    Keep your INTERNET ON. Run this once.
echo ==========================================
echo.

REM ---------- 1) Python ----------
where python >nul 2>nul
if errorlevel 1 (
  echo [X] Python is not installed.
  echo     Install "Python 3.11" from the Microsoft Store, then run this file again.
  goto end
)

REM ---------- 2) Virtual environment + Python packages ----------
if not exist "%VPY%" (
  echo Creating Python environment...
  python -m venv .venv
)
echo Installing Python packages (a few minutes the first time)...
"%VPY%" -m pip install --upgrade pip
"%VPY%" -m pip install -r backend\requirements.txt
if errorlevel 1 (
  echo [!] Some packages failed. Check the internet and run SETUP.bat again.
)

REM ---------- 3) GPU acceleration libraries (NVIDIA, optional) ----------
echo.
echo Installing GPU acceleration libraries (safe to skip if you have no NVIDIA card)...
"%VPY%" -m pip install nvidia-cudnn-cu12 nvidia-cublas-cu12
echo.

REM ---------- 4) ffmpeg ----------
where ffmpeg >nul 2>nul
if not errorlevel 1 goto ffdone
if exist "ffmpeg\bin\ffmpeg.exe" goto ffdone
echo Downloading ffmpeg (about 100 MB, one time)...
curl -L -o ffmpeg.zip "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
if exist ffmpeg_tmp rmdir /s /q ffmpeg_tmp
mkdir ffmpeg_tmp
tar -xf ffmpeg.zip -C ffmpeg_tmp
for /d %%D in (ffmpeg_tmp\*) do set "FF=%%D"
if not exist ffmpeg mkdir ffmpeg
xcopy /e /i /y "!FF!\bin" "ffmpeg\bin" >nul
del ffmpeg.zip >nul 2>nul
rmdir /s /q ffmpeg_tmp >nul 2>nul
echo ffmpeg is ready.
:ffdone

REM ---------- 5) Caption Studio (Remotion) - optional, needs Node.js ----------
echo.
where node >nul 2>nul
if errorlevel 1 (
  echo [i] Node.js not found. The premium Caption Studio needs it.
  echo     To enable it later: install Node.js from https://nodejs.org , then
  echo     run:  cd caption-studio  ^&^&  npm install
) else (
  if exist "caption-studio\package.json" (
    echo Installing Caption Studio libraries...
    pushd caption-studio
    call npm install
    popd
  )
)

echo.
echo ==========================================
echo   Setup complete. Now double-click START.bat
echo ==========================================
:end
echo.
pause
