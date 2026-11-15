@echo off
rem Shows whether automatic AI Companion updates are set up, and what to fix.
set "VENV=%APPDATA%\AICompanion\auto\venv"
if not exist "%VENV%\Scripts\python.exe" (
  echo Not installed yet. Double-click Install-Windows.cmd first.
  pause
  exit /b 1
)
"%VENV%\Scripts\python.exe" "%~dp0aic_auto.py" check
echo.
"%VENV%\Scripts\python.exe" "%~dp0aic_auto.py" status
echo.
"%VENV%\Scripts\python.exe" "%~dp0aic_auto.py" log 10
pause
