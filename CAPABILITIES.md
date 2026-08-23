# What A.L.I.C.E. Can Do

A.L.I.C.E. — Attentive Local Intelligence & Concierge Engine — is a voice-driven HUD for
the wall: behind two-way mirror glass as a smart mirror, or straight on a wall-mounted
monitor as an interactive display — the same interface either way. Iron Man-style
line-work on pure black (which is what lets it read through glass), fed by live data,
answered by an AI brain, spoken aloud.
Everything below is built and running unless marked otherwise.

## The face (always on)

- **Core** — a rotating compass/ring assembly with a radial spoke burst that breathes
  with the room's sound when the microphone is live, and shows state: STANDBY,
  ATTENTION, LISTENING, PROCESSING, RESPONDING.
- **Wordmark** — the name and acronym top centre; a boot sequence prints her full name
  and system checks on every power-up.
- **Rolodex (left rail)** — every card she can show, as a reel. When a command lands
  the reel spins, blurs, decelerates and locks on the matching card, which then flies
  out of the highlighted row into the centre. Unbuilt capabilities sit in the reel
  dimmed, so the menu is also an honest inventory.
- **Timeline (right rail, "NEXT 24H")** — sunrise/sunset, timed calendar events,
  flights, visible ISS passes, launches and the forecast rain peak as nodes on a
  vertical rail; the next one up glows, and the rail is only as tall as its contents.
- **Airspace contacts** — real aircraft within ~30 km drawn as blips on the compass
  ring, positioned by true bearing from home, brighter when nearer, callsign attached.
- **Ticker tape (bottom edge)** — market indices plus whatever the stock scanner is
  watching, scrolling, gainers cyan / losers red.
- **Corner panels** — system (data freshness, uplink, audio, wake word, response
  latency, display mode), telemetry meters, clock/date/place, and local conditions
  (temp, feels-like, sky, air quality, rain chance, sunset).
- **Pulse markers** — when she speaks a figure, the matching number on the card surges
  (brightness + 18% scale), and a figure that *is* a graphic (the rain bar) redraws
  itself from zero. The spoken line lights the same phrase in sync.

## The cards (summoned by voice, key, or phone)

| Card | What it shows | Source |
|---|---|---|
| Weather | Temp, feels-like, sky, humidity, wind, pressure, AQI, 8-hour precip strip, sun times, hi/lo | Open-Meteo (no key) |
| Daylight | Sun arc with current position, daylight remaining, day length | computed |
| Radar | Precipitation radar loop ~400 km around home, tinted by intensity (cyan/amber/red), range rings, home reticle | RainViewer (no key) |
| Traffic | Live drive time vs typical to saved places, on a wireframe map of real roads with the route coloured by congestion and a dot running your direction | Mapbox driving-traffic + OpenStreetMap/OSRM |
| Schedule | Today's count, next 14 days across chosen calendars (a source can be excluded), today first | EventKit (local) |
| Flights | Upcoming flights parsed from airline emails on the calendar — number, destination, legs grouped into trips by confirmation code — plus live status/gate/delay inside 48 h of departure | calendar + AeroDataBox |
| Mail | Unread and recent per IMAP account, headers only, read-only | IMAP |
| To Do | Open / overdue / due-today reminders across lists | EventKit Reminders (local) |
| Airspace | Aircraft nearby with distance, bearing, altitude, speed, heading | OpenSky (anon) |
| Sky | Visible ISS passes computed locally from orbital elements; upcoming launches | Celestrak TLE + sgp4; Launch Library |
| News | Headlines round-robined across configured RSS feeds | RSS |
| On This Day | Monthly anniversaries from the owner's own git history — repos born, tags shipped, busy days | local git |
| Signals | Stock-scanner picks with probability bars and pending event strategies | owner's scanner output |
| Auctions / Apps | Weekly government-auction and app-acquisition digests, parsed and ranked | owner's scouts |
| Builds | Latest CI run per repo, red first | gh CLI |
| App Store | Every app's review state — awaiting release, in review, draft, live | App Store Connect API |
| Pipelines | Content queues: runway, items awaiting approval, and pipelines that are silently broken | on-disk queue state |

## The voice

- **Wake word** — runs locally (openWakeWord), ~3% of one core to listen all day.
- **Transcription** — local Whisper (`base.en`), ~0.6 s per command; nothing leaves
  the machine. The heard phrase is shown under the core so a mishearing is obvious.
- **Brain** — one AI call per question with the *current snapshot of every data source*
  attached, so she answers only from what the mirror actually knows and says plainly
  when a source is stale or missing. Returns speech + which card to summon, with pulse
  markers on the key figures. Pluggable: Anthropic (default, cached system prompt) or
  any OpenAI-compatible endpoint (OpenAI, Ollama for fully local).
- **Speech** — spoken aloud in a configurable system voice (British female by default)
  while the card types out; a premium voice is a config swap.
- Without a brain key she still listens, transcribes, and says honestly that reasoning
  isn't connected.

## Behaviour

- **Display modes** — FULL, BOOST (over-driven brightness for behind-glass use, 150% +
  saturation), NIGHT, and AUTO (dims through twilight using real sunset/sunrise).
- **Burn-in protection** — the whole stage drifts a few pixels on a slow cycle.
- **Palettes** — ambient cyan or red helmet-targeting.
- **Idle demo loop** — cycles cards unattended so the glass is never a dark rectangle.
- **Privacy / guest mode** — one tap hides mail, calendar, flights, money and work
  cards (they refuse to open and dim in the reel) while the mirror stays impressive.
- **Presence** — with an mmWave radar on USB, sleeps when the room empties and sweeps
  awake when someone approaches (daemon written; hardware pending).

## Running as an appliance

- **Self-starting** — launchd agents for the data server, the refresh daemon and the
  phone remote; a kiosk agent runs fullscreen Chrome under `caffeinate` so the
  machine never sleeps, and relaunches it if it exits. Survives reboots untouched.
- **Self-refreshing** — every source on its own cadence (5–360 min) from one daemon.
- **Self-aware** — a staleness watchdog flags any source whose data stops updating
  (DATA: CURRENT / N STALE), and the Pipelines card catches jobs that report success
  while producing nothing.
- **Phone remote** — a separate token-gated LAN server: brightness, palette, summon any
  card, demo loop, privacy mode, and a health strip. It exposes no data files.
- **Resolution-independent** — one 1600×1000 design canvas scaled to any display.

## Privacy model

- The data server binds to localhost only; the remote is separate and token-gated.
- Keys live in the macOS Keychain, never in files; credentials are read at runtime.
- All generated data and `config.local.json` are git-ignored; the public repo carries
  code and docs only.
- Mail is headers-only and mailboxes are opened read-only — looking never marks read.

## Not yet (deliberately)

- Wake word is still the library's pretrained phrase until a custom "hey Alice" model
  is trained.
- Music playback (service choice pending), live flight status arms only inside 48 h,
  work mail/calendar via Microsoft Graph requires tenant consent.
