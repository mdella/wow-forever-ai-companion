@echo off
rem Stops automatic AI Companion updates on Windows. Settings and logs are kept.
set "VENV=%APPDATA%\AICompanion\auto\venv"
if exist "%VENV%\Scripts\python.exe" (
  "%VENV%\Scripts\python.exe" "%~dp0aic_auto.py" uninstall
) else (
  powershell -NoProfile -Command "Unregister-ScheduledTask -TaskName 'AICompanionAuto' -Confirm:$false -ErrorAction SilentlyContinue"
  echo Stopped watching.
)
pause
