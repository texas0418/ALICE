# A.L.I.C.E. — Setup

A voice-driven, Iron-Man-style HUD for a wall — behind mirror glass or on a plain
monitor, your call. Everything private (where you live,
your keys, your mail) lives in `config.local.json` and the macOS Keychain — never in
code. **macOS-first**: reminders/calendar use EventKit, the stand-in voice is `say`,
keys use Keychain. The HUD itself is a plain web page and will run anywhere.

## 0. What you need
- A Mac (Intel or Apple Silicon), Python 3.11, Chrome.
- Optional accounts, each enables one feature: Mapbox (traffic), RapidAPI/AeroDataBox
  (live flight status), an LLM (the brain — Anthropic, or any OpenAI-compatible
  server such as Ollama for fully local).

## 1. Clone and make the environment
    git clone https://github.com/texas0418/ALICE ~/ALICE
    cd ~/ALICE
    python3.11 -m venv ~/.venvs/jarvis
    ~/.venvs/jarvis/bin/pip install numpy sounddevice websockets openwakeword onnxruntime \
        faster-whisper anthropic pyobjc-framework-EventKit pillow sgp4 pyserial cryptography
(The venv path `~/.venvs/jarvis` is baked into the launchd agents; keep it.)

## 2. Configure
    cp config.example.json config.local.json
Edit it: your coordinates, a place label, destinations for traffic, IMAP mail accounts,
RSS feeds, the persona (name, acronym, a `say -v ?` voice), the brain provider, and the
`sources` list — enable only what you have.

## 3. Keys (Keychain, never files)
Each prompts twice; nothing touches disk or shell history:
    security add-generic-password -U -a jarvis-mirror -s mapbox-token  -w   # traffic
    security add-generic-password -U -a jarvis-mirror -s anthropic-key -w   # brain (anthropic)
    security add-generic-password -U -a jarvis-mirror -s openai-key    -w   # brain (openai provider; optional for local servers)
    security add-generic-password -U -a jarvis-mirror -s rapidapi-key  -w   # flight status
    security add-generic-password -U -a you@example.com -s jarvis-mail -w   # one per IMAP account

## 4. First data
    ~/.venvs/jarvis/bin/python tools/refresh-weather.py
    ~/.venvs/jarvis/bin/python tools/refresh.py --force
Traffic needs a one-time road-network build around your home (OpenStreetMap + OSRM) —
see the README "Traffic" section and tools/refresh-traffic.py.

## 5. Run it
    ~/.venvs/jarvis/bin/python -m http.server 8777 --bind 127.0.0.1
Open http://localhost:8777 in Chrome, ⌃⌘F for full screen. Number keys jump to cards,
B brightness, C palette, H hides the helper line, D demo loop.

## 6. Make it an appliance
    tools/install-kiosk.sh          # server + refresh daemon + phone remote (safe anywhere)
    tools/install-kiosk.sh --full   # also fullscreen Chrome kiosk — dedicated machine only
Then grant Full Disk Access + Calendar + Reminders to `~/.venvs/jarvis/bin/python`
(System Settings → Privacy & Security) so the daemon can read your data.

## 7. Voice
    ~/.venvs/jarvis/bin/python voice/service.py
Wake word (openWakeWord, local) → Whisper (local) → your brain → `say`. Without a brain
key it still listens and transcribes, and says so honestly.

## Make it yours (name, voice, personality)
Everything about the persona is in `config.local.json` → `persona`, no code changes:
- `name` — what shows on the glass and what the brain calls itself (A.L.I.C.E. is just the default)
- `acronym` — the subtitle under the name; leave empty for none
- `description` — the personality the brain plays, in a sentence or two
- `voice` — any `say -v ?` voice on macOS, or a Piper `.onnx` model path on Linux
- `tts` — `say` | `piper` | `none` | `auto`
- `wake_model` — any openWakeWord pretrained phrase (`hey_jarvis`, `alexa`, `hey_mycroft`,
  `hey_rhasspy`) or a path to a model you trained for your own phrase. A custom phrase is
  the one thing that needs more than config: train a model with openWakeWord's tooling,
  or use a Picovoice Porcupine custom keyword.
Restart the voice service and the daemon after editing; the HUD picks the name up on reload.

## Linux (partial today — see HARDWARE.md for the plan)
What runs unchanged: the HUD, every data tool except calendar/reminders, the wake word,
Whisper, the brain, the phone remote. The portable layer is in:
- `tools/vault.py` — secrets via macOS Keychain, Linux `secret-tool` (libsecret), or
  `JARVIS_<SERVICE>` env vars. `vault.py put jarvis-mirror anthropic-key` prompts and stores.
- `voice/tts.py` — `say` on macOS, **Piper** on Linux (`persona.tts`, `persona.voice` =
  path to a `.onnx` model), or `none`.
- `voice/presence.py` — finds `/dev/ttyUSB*` / `/dev/ttyACM*` as well as macOS ports.
Not yet: calendar/reminders providers (CalDAV/ICS), systemd units, a Linux kiosk script.
Run `tools/doctor.py` first on any new box — it reports exactly what's present.

## The brain contract
`voice/brain.py` → `ask(text)` returns `{"speech": str, "focus": card|None}`; speech may
carry `[phrase|target]` pulse markers. `provider: anthropic` uses the Claude API with a
cached system prompt; `provider: openai` posts to any OpenAI-compatible
`/chat/completions` (Ollama: `http://localhost:11434/v1`). Swap providers in config.

## Privacy model
- The data server binds 127.0.0.1 only. The phone remote (port 8778) is a separate,
  token-gated server that exposes no data files.
- `.gitignore` keeps every data file and config.local.* out of git. Keep its pattern
  lines bare — git ignores nothing on a line that carries a trailing comment.
- Privacy mode (phone remote) hides personal cards for guests.
