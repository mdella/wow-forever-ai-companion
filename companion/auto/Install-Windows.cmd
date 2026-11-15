@echo off
rem Installs automatic AI Companion updates on Windows. Double-click to run.
setlocal
set "HERE=%~dp0"
set "HOME_DIR=%APPDATA%\AICompanion\auto"
set "VENV=%HOME_DIR%\venv"

echo AI Companion: setting up automatic updates...
echo.
where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")
%PY% --version >nul 2>nul || (
  echo Python 3 is not installed. Install it from https://www.python.org/downloads/
  echo ^(tick "Add python.exe to PATH"^), then run this again.
  pause
  exit /b 1
)
if not exist "%VENV%\Scripts\python.exe" (
  echo Creating a private Python environment in %VENV%
  %PY% -m venv "%VENV%" || (echo Could not create it. & pause & exit /b 1)
)
"%VENV%\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check lupa || (
  echo Could not install lupa. & pause & exit /b 1
)
"%VENV%\Scripts\python.exe" "%HERE%aic_auto.py" install
echo.
echo To check it any time: double-click Check-Windows.cmd
pause
