#!/bin/bash
# Installs automatic AI Companion updates on macOS. Double-click to run.
HERE="$(cd "$(dirname "$0")" && pwd)"
HOME_DIR="${AIC_AUTO_HOME:-$HOME/Library/Application Support/AICompanion/auto}"
VENV="$HOME_DIR/venv"
echo "AI Companion: setting up automatic updates..."
echo
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is not installed. Install it from https://www.python.org/downloads/ and run this again."
  read -r -p "Press Return to close." _; exit 1
fi
mkdir -p "$HOME_DIR"
if [ ! -x "$VENV/bin/python" ]; then
  echo "Creating a private Python environment in $VENV"
  python3 -m venv "$VENV" || { echo "Could not create it."; read -r -p "Press Return to close." _; exit 1; }
fi
"$VENV/bin/python" -m pip install --quiet --disable-pip-version-check lupa || {
  echo "Could not install lupa."; read -r -p "Press Return to close." _; exit 1; }
"$VENV/bin/python" "$HERE/aic_auto.py" install
echo
echo "To check it any time: double-click Check-Mac.command"
read -r -p "Press Return to close." _
