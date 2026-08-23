#!/usr/bin/env python3
"""Ten-second health check: platform, backends, stored secrets, data freshness.

Run this first on a new machine and whenever a card is unexpectedly empty — it says
which provider is missing instead of leaving you to guess.
"""
import importlib.util, json, os, platform, shutil, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.join(ROOT, 'voice'))
import vault

OK, NO, WARN = '  ok ', '  -- ', '  !! '


def have(mod):
    return importlib.util.find_spec(mod) is not None


def main():
    sysname = platform.system()
    print(f'A.L.I.C.E. doctor — {sysname} {platform.release()}  python {platform.python_version()}')

    print('\nsecrets')
    print(f'{OK}backend: {vault.backend()}')
    for svc, what in [('mapbox-token', 'traffic'), ('anthropic-key', 'brain (anthropic)'),
                      ('openai-key', 'brain (openai provider; optional for local)'),
                      ('rapidapi-key', 'live flight status')]:
        v = vault.get('jarvis-mirror', svc)
        print(f'{OK if v else NO}{svc:16s} {what}' + ('' if v else f'   -> {vault.hint("jarvis-mirror", svc)}'))

    print('\nconfig')
    cfgp = os.path.join(ROOT, 'config.local.json')
    if os.path.exists(cfgp):
        cfg = json.load(open(cfgp))
        home = cfg.get('home', {})
        print(f'{OK}config.local.json  place={home.get("place","?")}  sources={len(cfg.get("sources",[]))}  '
              f'brain={cfg.get("brain",{}).get("provider","anthropic")}')
    else:
        print(f'{NO}config.local.json missing -> cp config.example.json config.local.json')
        cfg = {}

    print('\nvoice')
    for mod, what in [('openwakeword', 'wake word'), ('faster_whisper', 'transcription'),
                      ('sounddevice', 'microphone'), ('anthropic', 'brain sdk')]:
        print(f'{OK if have(mod) else NO}{mod:16s} {what}')
    import tts
    print(f'{OK if tts.choose() != "none" else WARN}tts backend: {tts.choose()}'
          + ('' if tts.choose() != 'none' else '  (install piper, or set persona.tts)'))

    print('\nplatform providers')
    if sysname == 'Darwin':
        print(f'{OK if have("EventKit") else NO}EventKit        calendar + reminders')
    else:
        print(f'{WARN}EventKit        n/a on {sysname} — calendar/reminders need the CalDAV/ICS '
              f'providers (not yet written; see HARDWARE.md)')
        print(f'{OK if shutil.which("secret-tool") else WARN}secret-tool     '
              + ('libsecret present' if shutil.which('secret-tool') else 'missing -> apt install libsecret-tools (or use env vars)'))
        print(f'{OK if shutil.which("piper") else NO}piper           local TTS')
    for exe, what in [('gh', 'builds card'), ('chromium', 'kiosk (linux)'), ('google-chrome', 'kiosk')]:
        if shutil.which(exe):
            print(f'{OK}{exe:16s}{what}')

    print('\ndata files')
    now = time.time()
    for name in ['weatherdata', 'mapdata', 'maildata', 'calendardata', 'remindersdata',
                 'newsdata', 'tickerdata', 'flightdata', 'aircraftdata', 'radardata', 'skydata']:
        p = os.path.join(ROOT, name + '.js')
        if os.path.exists(p):
            age = (now - os.path.getmtime(p)) / 60
            print(f'{OK if age < 180 else WARN}{name:16s} {age:6.0f} min old')
        else:
            print(f'{NO}{name:16s} missing')


if __name__ == '__main__':
    main()
