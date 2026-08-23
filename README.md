# A.L.I.C.E. — Attentive Local Intelligence & Concierge Engine

A voice-driven HUD for the wall — a smart mirror behind two-way glass, or an
interactive display on a plain monitor; same interface either way. Iron Man idiom:
pure-black ground, glowing line-work, a rolodex of live cards, a timeline of your next 24 hours, real aircraft on
the compass ring, precipitation radar, and a pluggable AI brain that answers from the
mirror's own data. macOS-first (tested); a Linux path for N100 / Pi / any Linux box is charted in
HARDWARE.md and ~80% of the code already runs there. **Start with [SETUP.md](SETUP.md)**
for the software and **[HARDWARE.md](HARDWARE.md)** for the panel, glass, sensor, wall,
and the no-Mac / cheaper options.

Bring your own keys and your own AI: everything private lives in `config.local.json`
and the Keychain. The brain speaks Anthropic by default or any OpenAI-compatible
endpoint (Ollama for fully local). MIT licensed.

---

Renamed from JARVIS on 2026-08-21. Persona is Alice: British, female, composed.
Stand-in voice is macOS `Flo` (en_GB); the keeper is `Kate (Enhanced)`, a ~300MB
download via System Settings > Accessibility > Spoken Content > System Voice >
Manage Voices — do it on land. The WAKE WORD is still "hey jarvis" (openWakeWord has
no pretrained "alice" model); a custom "hey alice" model is an on-land task —
either openWakeWord's training notebook or a Picovoice Porcupine custom keyword.
Paths, repo name and launchd labels keep "jarvis" — renaming those buys nothing.


Look-and-feel prototype. No audio, no network, no APIs. Everything on screen is
either real (clock, date) or a scripted stand-in for something Phase 1 will make real.

## Run it
Open `index.html` in Chrome. For the real effect:
  Chrome > View > Enter Full Screen, or launch kiosk:
  /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --kiosk --app=file://$PWD/index.html

## Controls
  SPACE or click .... run one fake voice turn (wake -> listen -> think -> respond)
  C ................. toggle cyan (ambient JARVIS) / red (helmet targeting)

## What's real vs. faked
  REAL   clock, date, the whole render/animation pipeline, state machine
  FAKED  the spoken question, the answer text, weather, telemetry meters,
         the response-latency figure

## Design notes
  - Pure black background is mandatory: a two-way mirror only shows emitted light,
    so any grey fill reads as a glowing rectangle. All structure is drawn as lines.
  - The radial spoke burst is the voice. It idles low and blooms on LISTENING.
    In Phase 1 it gets driven by real mic amplitude, then by TTS output amplitude.
  - Layout is landscape. Portrait needs a separate pass.

## Focus mode
A query can summon a corner panel to the centre. The inner rings and core readout
fade, the spoke burst migrates outward into a corona, and the panel flies from its
corner and unpacks into a fuller readout. Declared per turn as `f:'weather'`.

Add a new focusable domain in the `FOCUS` map: `src` (which corner panel it flies
from), `build()` (the expanded card HTML), `targets` (named data points -> selectors).

## Spoken-datum highlighting
Answers are authored with `[phrase|target]` markers:

  "[Eighty-four|temp] and humid in [Atlanta|loc]. Rain likely after [four|hour]."

When the phrase finishes, the matching element in the focus card pulses (brightness
surge + slight scale, ~1s) and then holds at raised brightness until the card leaves.
The phrase in the spoken line lights up at the same moment, so the eye connects the
two. In Phase 0 the cue fires off typing position. In Phase 1 it fires off real TTS
alignment timestamps - same markers, different clock.

### Surging targets
A target can be declared as `{sel:'...', surge:true}` instead of a bare selector.
A surging target doesn't just pulse — it redraws itself. The precip bar rebuilds
from zero with an overshoot, its percentage surfaces above it, and the surrounding
hours dim back. Use it wherever the spoken figure IS the graphic.

## Traffic / route map
Real road geometry from OpenStreetMap (Overpass) + real routes from OSRM. Deliberately
NOT map tiles — a raster tile is a photograph, and a photograph behind two-way glass is
a glowing grey rectangle. Coordinates in, glowing lines out.

Rendering is split for performance:
  - the CITY is static, so it rasterises once to a <canvas>. ~14k road ways as SVG
    <path> elements stalls the compositor outright; canvas draws them in a few ms.
  - the ROUTE stays in SVG, where it needs to be for the stroke-dash draw-in and for
    per-segment congestion colouring.

Nothing on the focus path may depend on requestAnimationFrame — a hidden or backgrounded
tab never fires it and the card silently never appears. Use timers.

## PRIVACY — read before pushing this repo
`config.local.js` and `mapdata.js` are gitignored and MUST stay that way. Both identify
where the mirror lives: config holds the home coordinates, and mapdata holds a road
network and routes centred on the house. `config.example.js` is the safe placeholder.

Regenerate map data with tools/build-map.py (see git history) after editing destinations.

## Live traffic (Mapbox)
    python3 tools/refresh-traffic.py

Reads the token from the macOS Keychain (`jarvis-mirror` / `mapbox-token`) at runtime.
The token is never stored on disk, never passed as an argument, and every error path is
scrubbed — Mapbox carries the token in the query string, so one unhandled traceback would
otherwise leak it into a log.

`freeMin` is Mapbox's `duration_typical` (typical for this time of day), NOT free-flow,
so "vs usual" means what it says. Congestion phrasing is derived from the real per-segment
annotation — never invent a highway name, since step-level data isn't being requested.

3 requests per refresh against a 100k/month free tier. Currently baked at fetch time;
Phase 1 moves it to on-demand when asked.

## Reminders (local, no network)
    ~/.venvs/jarvis/bin/python tools/reminders.py [--quiet]
EventKit against whatever macOS has already synced. Needs the one-time Reminders
permission, granted per-process — your terminal now, the launchd agent separately.

## Weather (Open-Meteo, no key)
    ~/.venvs/jarvis/bin/python tools/refresh-weather.py
No account, no key, no meaningful rate limit. Coordinates come from config.local.json
so home never appears in committed source.

## Keeping data current
    ~/.venvs/jarvis/bin/python tools/refresh.py            # refresh what's stale
    ~/.venvs/jarvis/bin/python tools/refresh.py --status   # ages only
Each source has its own interval (mail 5m, traffic 10m, weather 15m, reminders 15m);
one launchd job on a 5-minute timer gives all four sensible cadences.

    cp launchd/com.simonbuilds.jarvis.refresh.plist ~/Library/LaunchAgents/
    launchctl load ~/Library/LaunchAgents/com.simonbuilds.jarvis.refresh.plist

## Outlook calendar — DEAD END, do not retry
The Mac Outlook profile holds a calendar that stopped being modified in 2023. Dates
there are stored as MINUTES SINCE 1601, not Mac absolute time. The current M365
calendar never syncs to this machine; it needs Microsoft Graph, same as work email.

## Kiosk boot (appliance mode)
Three launchd agents make the mirror a self-starting appliance:
  server   com.simonbuilds.jarvis.server   http.server on 127.0.0.1:8777, KeepAlive
  refresh  com.simonbuilds.jarvis.refresh  data refresh every 5 min
  kiosk    com.simonbuilds.jarvis.kiosk    tools/kiosk.sh -> caffeinate + Chrome --kiosk

Install:  tools/install-kiosk.sh          (server + refresh — safe on a work laptop)
          tools/install-kiosk.sh --full   (adds the fullscreen kiosk; DEDICATED machine only)

kiosk.sh waits for the server, then execs Chrome under `caffeinate -dis` so sleep is
held off only while the mirror is actually running. Chrome uses its own profile dir
(.chrome-kiosk/, gitignored) so it never collides with a normal Chrome session. If
Chrome exits, launchd restarts it: the mirror self-heals.

Manual, one-time, on the dedicated machine (these need the user's password):
  1. Users & Groups -> automatic login
  2. Full Disk Access for ~/.venvs/jarvis/bin/python  (the launchd TCC trap)
  3. Reminders/Calendars grants for that same binary on first daemon run
Escape hatch on a live kiosk: Cmd-Q quits Chrome (launchd relaunches in ~2s);
`launchctl unload ~/Library/LaunchAgents/com.simonbuilds.jarvis.kiosk.plist` stops it.

## Phone remote (port 8778)
A SEPARATE server from the mirror: the mirror's data stays on 127.0.0.1, while
tools/control-server.py listens on the LAN serving ONLY a control page and a
health summary — none of the data files (mail, routes, home coords) are reachable.
Every request needs ?t=<controlToken> from config.local.json; anything else is a
bare 403. Commands land in controldata.js, which the page polls every 3s.

Phone URL is in phone-remote-url.txt (gitignored — it embeds the token).
Controls: brightness (full/boost/night/auto), show any card, palette, demo loop.
launchd agent: com.simonbuilds.jarvis.control (loaded; in install-kiosk.sh too).

## Live flight status (AeroDataBox / RapidAPI)
tools/flights.py polls status for calendar-detected flights, but only inside 48h
of departure, on a proximity cadence (12h -> 2h -> 20min), with a hard self-cap of
250 calls/month persisted in .flights-state.json — the free tier can't be exceeded.
Key: Keychain jarvis-mirror/rapidapi-key. Cloudflare requires a browser User-Agent.
Status merges into the flights card (gate, delay) and the brain's snapshot.
