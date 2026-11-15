#!/bin/bash
# Stops automatic AI Companion updates on macOS. Settings and logs are kept.
HERE="$(cd "$(dirname "$0")" && pwd)"
VENV="${AIC_AUTO_HOME:-$HOME/Library/Application Support/AICompanion/auto}/venv"
if [ -x "$VENV/bin/python" ]; then
  "$VENV/bin/python" "$HERE/aic_auto.py" uninstall
else
  launchctl bootout "gui/$(id -u)/local.aicompanion.auto" 2>/dev/null
  rm -f "$HOME/Library/LaunchAgents/local.aicompanion.auto.plist"
  echo "Stopped watching."
fi
read -r -p "Press Return to close." _
