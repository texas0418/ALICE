#!/bin/zsh
# Install the mirror as a self-starting appliance. Run ON THE MIRROR MACHINE.
#   ./install-kiosk.sh            server + refresh only (safe on a work laptop)
#   ./install-kiosk.sh --full     also the fullscreen kiosk (dedicated machine)
set -e
SRC="$HOME/Documents/GitHub/jarvis-mirror/launchd"
DST="$HOME/Library/LaunchAgents"
load(){
  cp "$SRC/$1" "$DST/"
  launchctl unload "$DST/$1" 2>/dev/null || true
  launchctl load "$DST/$1"
  echo "  loaded $1"
}
load com.simonbuilds.jarvis.server.plist
load com.simonbuilds.jarvis.refresh.plist
load com.simonbuilds.jarvis.control.plist
if [[ "$1" == "--full" ]]; then
  load com.simonbuilds.jarvis.kiosk.plist
  echo
  echo "Kiosk is live. Remaining MANUAL steps (need your password, one time):"
  echo "  1. System Settings > Users & Groups > Automatically log in as: your user"
  echo "  2. System Settings > Privacy & Security > Full Disk Access:"
  echo "     add ~/.venvs/jarvis/bin/python  (refresh daemon reads Documents)"
  echo "  3. System Settings > Privacy & Security > Reminders + Calendars:"
  echo "     allow the python binary when prompted on first daemon run"
else
  echo
  echo "Server + refresh installed. Kiosk NOT enabled (would take over this screen)."
  echo "On the dedicated machine run:  tools/install-kiosk.sh --full"
fi
