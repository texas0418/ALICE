#!/bin/zsh
# Launch the mirror display: wait for the local server, then run Chrome in kiosk
# mode wrapped in caffeinate so the machine can never sleep out from under it.
# Run by launchd (com.simonbuilds.jarvis.kiosk); if Chrome exits, launchd
# restarts this script and the mirror comes back on its own.

URL="http://localhost:8777"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE="$HOME/Documents/GitHub/jarvis-mirror/.chrome-kiosk"

# The server is a separate launchd agent; wait for it rather than racing it.
for i in {1..60}; do
  curl -sf -o /dev/null "$URL/index.html" && break
  sleep 2
done

# caffeinate -d display  -i idle-sleep  -s system-sleep : held only while Chrome runs.
# Dedicated profile dir so the kiosk never collides with a normal Chrome session.
exec /usr/bin/caffeinate -dis "$CHROME" \
  --kiosk \
  --app="$URL/?kiosk" \
  --user-data-dir="$PROFILE" \
  --no-first-run \
  --noerrdialogs \
  --disable-session-crashed-bubble \
  --disable-features=TranslateUI \
  --autoplay-policy=no-user-gesture-required \
  --force-device-scale-factor=1
