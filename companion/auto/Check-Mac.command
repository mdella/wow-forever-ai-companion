#!/bin/bash
# Shows whether automatic AI Companion updates are set up, and what to fix.
HERE="$(cd "$(dirname "$0")" && pwd)"
VENV="${AIC_AUTO_HOME:-$HOME/Library/Application Support/AICompanion/auto}/venv"
if [ ! -x "$VENV/bin/python" ]; then
  echo "Not installed yet. Double-click Install-Mac.command first."
  read -r -p "Press Return to close." _; exit 1
fi
"$VENV/bin/python" "$HERE/aic_auto.py" check
echo
"$VENV/bin/python" "$HERE/aic_auto.py" status
echo
"$VENV/bin/python" "$HERE/aic_auto.py" log 10
read -r -p "Press Return to close." _
