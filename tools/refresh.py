#!/usr/bin/env python3
"""Refresh whichever data sources have gone stale.

Run often (every few minutes); each source has its own interval and is skipped
until its data file is older than that. So one launchd job on a short timer gives
every source a sensible cadence without four separate agents.

    tools/refresh.py            # refresh what's stale
    tools/refresh.py --force    # refresh everything
    tools/refresh.py --status   # show ages, change nothing
"""
import os, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.expanduser('~/.venvs/jarvis/bin/python')

# launchd gives agents a bare PATH (/usr/bin:/bin:...), so subprocess tools like
# `gh` silently vanish and ci/appstore fail only when run by the daemon. Widen it
# here once instead of in every tool.
os.environ['PATH'] = '/usr/local/bin:/opt/homebrew/bin:' + os.environ.get('PATH', '')

# (name, output file, script, seconds before it is considered stale)
SOURCES = [
    ('mail',      'maildata.js',      'tools/mail.py',            300),
    ('traffic',   'mapdata.js',       'tools/refresh-traffic.py', 600),
    ('weather',   'weatherdata.js',   'tools/refresh-weather.py', 900),
    ('reminders', 'remindersdata.js', 'tools/reminders.py',       900),
    ('signals',   'signalsdata.js',   'tools/signals.py',        1800),
    ('scouts',    'scoutsdata.js',    'tools/scouts.py',         3600),
    ('ci',        'cidata.js',        'tools/ci.py',             1800),
    ('appstore',  'appstoredata.js',  'tools/appstore.py',       3600),
    ('calendar',  'calendardata.js',  'tools/events.py',        900),
    ('ticker',    'tickerdata.js',    'tools/ticker.py',          900),
    ('queues',    'queuedata.js',     'tools/queues.py',         1800),
    ('news',      'newsdata.js',      'tools/news.py',           1800),
    ('flights',   'flightdata.js',    'tools/flights.py',         900),
    ('aircraft',  'aircraftdata.js',  'tools/aircraft.py',        600),
    ('radar',     'radardata.js',     'tools/radar.py',           600),
    ('sky',       'skydata.js',       'tools/sky.py',           21600),
    ('onthisday', 'onthisdaydata.js', 'tools/onthisday.py',     21600),
]


def age(path):
    p = os.path.join(ROOT, path)
    return time.time() - os.path.getmtime(p) if os.path.exists(p) else float('inf')


def write_status():
    # One place that knows every source's real age. Individual data files carry
    # only an HH:MM stamp, which cannot distinguish "20 minutes ago" from
    # "yesterday at the same time" — exactly the failure that makes a mirror
    # show four-day-old numbers as if they were current.
    import json as _json
    srcs, stale = [], 0
    for name, out, _s, every in SOURCES:
        a = age(out)
        bad = a > every * 2.5
        stale += 1 if bad else 0
        srcs.append({'name': name,
                     'mins': None if a == float('inf') else round(a / 60, 1),
                     'every': every // 60, 'stale': bool(bad),
                     'missing': a == float('inf')})
    open(os.path.join(ROOT, 'statusdata.js'), 'w').write(
        'const STATUS=' + _json.dumps(
            {'sources': srcs, 'stale': stale,
             'checked': time.strftime('%H:%M')}, separators=(',', ':')) + ';\n')
    return stale


def enabled():
    """Only the sources named in config.local.json 'sources' run; a newcomer
    without Simon's local projects simply leaves those off the list."""
    try:
        import json
        cfg = json.load(open(os.path.join(ROOT, 'config.local.json')))
        want = set(cfg.get('sources') or [])
        # the HUD needs the persona too, via a public-safe file
        per = cfg.get('persona', {})
        home = cfg.get('home', {})
        open(os.path.join(ROOT, 'personadata.js'), 'w').write(
            'const PERSONA=' + json.dumps({'name': per.get('name', 'ALICE'),
                'acronym': per.get('acronym', ''), 'place': home.get('place', ''),
                'wake': per.get('wake_model', 'hey_jarvis').replace('_', ' ').upper()}) + ';\n')
    except Exception:
        want = set()
    return [s for s in SOURCES if not want or s[0] in want]


def main():
    force = '--force' in sys.argv
    stamp = time.strftime('%Y-%m-%d %H:%M:%S')

    if '--status' in sys.argv:
        write_status()
        print(f'{stamp}  data ages')
        for name, out, _, every in enabled():
            a = age(out)
            txt = 'missing' if a == float('inf') else f'{a/60:.1f} min'
            print(f'  {name:10s} {txt:>10s}   (refresh every {every//60} min)'
                  f'{"   STALE" if a > every else ""}')
        return

    ran = []
    for name, out, script, every in enabled():
        if not force and age(out) < every:
            continue
        r = subprocess.run([PY, os.path.join(ROOT, script), '--quiet'],
                           capture_output=True, text=True, timeout=180, cwd=ROOT)
        ok = r.returncode == 0
        ran.append(f'{name}{"" if ok else " FAILED"}')
        if not ok:
            # keep the tail only: these logs run unattended for weeks
            print(f'{stamp}  {name} failed rc={r.returncode}: '
                  f'{(r.stderr or r.stdout).strip().splitlines()[-1:]}')
    stale = write_status()
    if ran:
        print(f'{stamp}  refreshed: {", ".join(ran)}')
    if stale:
        print(f'{stamp}  WARNING: {stale} source(s) stale')


if __name__ == '__main__':
    main()
