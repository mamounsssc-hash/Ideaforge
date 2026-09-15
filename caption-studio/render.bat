@echo off
REM ==== CliPro Caption Studio (Remotion) ====
REM Renders captions from input.json onto public\clip.mp4 -> out\captioned.mp4
if not exist out mkdir out
echo Rendering... (first run downloads a browser, be patient)
call npx remotion render Captioned out\captioned.mp4
echo.
echo Done. Your video is in the "out" folder: out\captioned.mp4
pause
