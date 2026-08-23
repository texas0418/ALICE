# A.L.I.C.E. — Hardware

Software is in SETUP.md. This is the physical build. Two form factors, one HUD:

- **Wall display** — a monitor on the wall showing the HUD directly. Simplest, brightest,
  cheapest. Everything below except the glass applies.
- **Smart mirror** — the same monitor behind two-way mirror glass, so the HUD floats
  inside your reflection. The glass eats most of the light, which drives several
  choices below.

The HUD was designed for the mirror case (pure-black ground, bright line-work, no
grey fills, a BOOST brightness mode) and therefore also looks right on a plain panel.

## 1. The computer

A.L.I.C.E. is macOS-first (EventKit, Keychain, the `say` voice, launchd). The reference
build runs on a MacBook — a laptop you're retiring is ideal, and anything from the last
several years is more than enough. Whisper transcription runs in well under a second
on an Intel i7; Apple Silicon is faster still.

- Run it in **clamshell** driving the external panel, on **permanent power**.
- **Do not seal a laptop inside the frame.** It needs airflow; mount it behind or below
  the panel with a gap, or in an adjacent cabinet with the cables run through.
- Auto-login, no sleep, kiosk on boot: `tools/install-kiosk.sh --full` (see SETUP.md).
- A cheap second screen (an N100 mini PC, a Pi, a tablet) can *display* the HUD over the
  LAN later, but the Mac stays the brain — the data and voice pipeline live there.

### No Mac, or want it cheaper? (other builders)

The reference build is macOS and that is what's tested. But roughly 80% of A.L.I.C.E. is
already portable — the HUD is a web page, the data tools are plain Python, and the
voice pipeline (openWakeWord, faster-whisper, the brain) runs on Linux unchanged. The
macOS-only glue and its Linux stand-ins:

| macOS piece | Linux equivalent | Status |
|---|---|---|
| EventKit calendar | CalDAV / ICS feeds (Outlook.com publishes ICS; iCloud speaks CalDAV) | not yet written |
| Apple Reminders | iCloud CalDAV (VTODO) | not yet written |
| Keychain | libsecret / systemd credentials | not yet written |
| `say` voice | **Piper** local neural TTS (arguably better) | drop-in; one function |
| launchd agents | systemd units | mechanical |

Machine options, cheapest viable first:

- **Intel N100 mini PC, 16 GB, Linux (~$130–180)** — the smart non-Mac brain. Silent,
  6–10 W, runs 24/7; Whisper `base.en` transcribes a command in ~1 s. This is the
  target for the Linux port.
- **Raspberry Pi 5, 8 GB (~$80)** — HUD and wake word are fine; Whisper takes 3–5 s per
  command on its CPU, which hurts the "alive" feeling. Pair it with cloud transcription
  (streaming Deepgram/Whisper API) or accept the pause.
- **Any Linux laptop you already own** — free, and usually faster than either.
- **Mac mini (~$600)** — zero porting, everything works today; the premium is for effort
  saved, not capability.
- **Display-only box + a Mac elsewhere** — an N100, Pi, or tablet can *show* the HUD over
  the LAN while the Mac stays the brain; see §1.

If you build the Linux path before it lands here, the contract to preserve is small:
data tools write `*data.js` files the HUD reads; `voice/brain.py` → `ask(text)` returns
`{speech, focus}`; secrets are read at runtime from a store, never from files in the repo.
Pull requests welcome.

## 2. The panel

- **Size** — whatever fits the wall. The HUD is resolution-independent (one 1600×1000
  design canvas scaled to any display); a 24–32" landscape panel is the sweet spot.
  Portrait needs a layout pass; the HUD is landscape today.
- **Panel type matters for the mirror case.** IPS blacks glow dark-grey behind glass.
  **VA** is noticeably better; **OLED** is spectacular — true black vanishes into the
  mirror and the line-work floats with no backlight halo. For a plain wall display any
  panel is fine.
- **Brightness** — for glass, buy bright (400+ nits helps) and run the panel at max;
  press B on the HUD for BOOST (150% drive + saturation) when glass is in front of it.
- Thin bezels, and a panel whose controls/power survive a power cut and come back on
  (most do; check "last state" behaviour). VESA mount if possible.

## 3. The glass (mirror build only)

- **Two-way (one-way) mirror glass** transmits roughly 10–15% of light — classic look,
  heavy, fragile, and dim; the HUD must be bright.
- **Dielectric / "smart mirror" acrylic or glass** transmits ~30%+ with a good
  reflection — lighter, safer, and the HUD reads far better. This is the sensible pick.
- Order it cut to the panel's outer size plus the frame rebate. Matte black tape or
  card around the panel's bezel behind the glass so nothing but the HUD shows through.
- Test before framing: hold the sheet in front of the running HUD in the room's real
  light. If it looks dim, the fix is the glass spec or panel brightness, not software.

## 4. Microphone and speakers

- Any decent USB microphone works for testing; the built-in MacBook mic is enough at
  a desk. On a wall you want a **far-field USB mic array** (conference-style), mounted
  at the frame edge, not behind glass.
- Speakers: a small powered pair or a soundbar; keep them a little away from the mic.
  If you add music playback, duck the volume on wake (the software's job) — music
  into the mic will otherwise trip the wake word.

## 5. Presence sensor (wake on approach)

The reference is the **DFRobot SEN0395 24 GHz mmWave** presence sensor (~$25 from
DigiKey/Mouser/DFRobot): detects a person entering from ~9 m and even a sleeping
person — no camera, works in the dark. It's a bare board with serial pins, so add a
**USB-to-TTL serial adapter (3.3 V/5 V, FTDI or CP2102, ~$8)** and four jumper wires.

Wiring (sensor → adapter):
    VCC/5V → 5V     GND → GND     TX → RX     RX → TX
Plug the adapter into the Mac; it appears as `/dev/cu.usbserial-*` (or `cu.SLAB*`,
`cu.wchusbserial*`). Then:
    ~/.venvs/jarvis/bin/python voice/presence.py
It auto-detects the port (or `--port /dev/cu.usbserial-XXXX`), and the HUD sleeps when
the room empties and sweeps awake on approach. Mount the sensor at the frame edge facing
the room; it sees through plastic and thin wood, not through the mirror's metal coating.

## 6. Phone remote

Nothing to buy. Open the URL in `phone-remote-url.txt` on any device on your wifi for
brightness, palette, privacy mode, demo loop, and summoning cards.

## 7. Putting it on the wall

- Frame: a picture frame or a simple wood box deep enough for panel + Mac + cabling,
  open at the back or vented. Black interior.
- Cables: power for the panel and the Mac, the mic, the sensor's USB, speaker wire. Run
  them inside the wall or a cable raceway; one power strip behind the frame.
- Mount at standing eye height; the compass ring should sit roughly at chest-to-face
  level so the cards land where you look.

## Shopping list (wall display)
    monitor (24–32", bright), VESA mount or frame, USB far-field mic, small speakers,
    power strip, SEN0395 + USB-TTL adapter + jumpers (optional)

## Shopping list (mirror)
    everything above, plus dielectric mirror acrylic cut to size, black bezel tape,
    a frame with a rebate for the glass
