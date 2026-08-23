#!/usr/bin/env python3
"""Live status for the flights already on the calendar (AeroDataBox via RapidAPI).

Input comes from calendardata.js — flight numbers and dates the calendar reader
extracted from airline emails. Only flights in the next 48 hours are polled, on a
cadence that tightens as departure approaches, and a persistent monthly counter
refuses to exceed the free tier. The free plan has a hard cap, so the worst
failure mode is stale status, never a bill.
"""
import json, os, subprocess, sys, urllib.request
from datetime import datetime, date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = 'aerodatabox.p.rapidapi.com'
MONTH_BUDGET = 250          # free tier is ~300; leave headroom
STATE = os.path.join(ROOT, '.flights-state.json')


def keychain():
    r = subprocess.run(['security', 'find-generic-password', '-a', 'jarvis-mirror',
                        '-s', 'rapidapi-key', '-w'], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def load_json(path, default):
    try:
        return json.load(open(path))
    except Exception:
        return default


def calendar_flights():
    try:
        raw = open(os.path.join(ROOT, 'calendardata.js')).read()
        d = json.loads(raw[raw.index('=') + 1:].rstrip().rstrip(';'))
        return d.get('flights', [])
    except Exception:
        return []


def refresh_due(state_entry, hours_out):
    """Poll cadence tightens as departure nears."""
    if not state_entry:
        return True
    age_min = (datetime.now() - datetime.fromisoformat(state_entry['at'])).total_seconds() / 60
    if hours_out > 24:
        return age_min > 720        # twice a day
    if hours_out > 4:
        return age_min > 120
    return age_min > 20             # final approach to departure


def fetch(key, fnum, day):
    url = f'https://{HOST}/flights/number/{fnum}/{day}?withAircraftImage=false&withLocation=false'
    # Cloudflare fronts RapidAPI and bans python-urllib's default signature
    # outright (error 1010) — a browser UA is required, not cosmetic.
    req = urllib.request.Request(url, headers={
        'X-RapidAPI-Key': key, 'X-RapidAPI-Host': HOST,
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def pick_leg(legs, sched_local):
    """The same number can fly several legs a day; match on departure time."""
    if not isinstance(legs, list) or not legs:
        return None
    if len(legs) == 1 or not sched_local:
        return legs[0]
    want = sched_local[11:16]
    for leg in legs:
        t = ((leg.get('departure') or {}).get('scheduledTime') or {}).get('local', '')
        if want and want in t:
            return leg
    return legs[0]


def summarise(leg):
    dep, arr = leg.get('departure') or {}, leg.get('arrival') or {}
    def t(side, k):
        return ((side.get(k) or {}).get('local') or '')[11:16] or None
    sched, revised = t(dep, 'scheduledTime'), t(dep, 'revisedTime')
    delay = None
    if sched and revised and revised != sched:
        d0 = int(sched[:2]) * 60 + int(sched[3:])
        d1 = int(revised[:2]) * 60 + int(revised[3:])
        delay = d1 - d0
    return {'status': leg.get('status') or 'Unknown',
            'gate': dep.get('gate'), 'terminal': dep.get('terminal'),
            'sched': sched, 'revised': revised, 'delayMin': delay,
            'arrGate': arr.get('gate'), 'arrSched': t(arr, 'scheduledTime')}


def main():
    quiet = '--quiet' in sys.argv
    key = keychain()
    if not key:
        print('  no rapidapi-key in Keychain yet — writing empty status')
        open(os.path.join(ROOT, 'flightdata.js'), 'w').write(
            'const FLIGHTSTATUS={"statuses":{},"note":"no API key"};\n')
        return

    state = load_json(STATE, {'month': '', 'calls': 0, 'flights': {}})
    month = date.today().strftime('%Y-%m')
    if state['month'] != month:
        state.update(month=month, calls=0)

    now = datetime.now()
    statuses, polled = {}, 0
    for f in calendar_flights():
        fnum, start = f.get('fnum'), f.get('start')
        if not fnum or not start:
            continue
        dep = datetime.fromisoformat(start)
        hours = (dep - now).total_seconds() / 3600
        k = f'{fnum}_{start[:10]}'
        prev = state['flights'].get(k)
        if hours < -6 or hours > 48:
            continue                     # long gone, or too far out to poll
        if not refresh_due(prev, hours) or state['calls'] >= MONTH_BUDGET:
            if prev:
                statuses[k] = prev['data']
            continue
        try:
            legs = fetch(key, fnum, start[:10])
            info = pick_leg(legs, start)
            if info:
                data = summarise(info)
                statuses[k] = data
                state['flights'][k] = {'at': now.isoformat(), 'data': data}
            state['calls'] += 1
            polled += 1
        except Exception as e:
            if prev:
                statuses[k] = prev['data']
            print(f'  {fnum}: {type(e).__name__}')

    json.dump(state, open(STATE, 'w'))
    out = {'statuses': statuses, 'calls': state['calls'],
           'budget': MONTH_BUDGET, 'fetched': now.strftime('%H:%M')}
    open(os.path.join(ROOT, 'flightdata.js'), 'w').write(
        'const FLIGHTSTATUS=' + json.dumps(out, separators=(',', ':')) + ';\n')
    print(f"  {len(statuses)} statuses ({polled} polled now, "
          f"{state['calls']}/{MONTH_BUDGET} calls this month)")
    if not quiet:
        for k, v in statuses.items():
            print(f"    {k}: {v['status']}  gate {v.get('gate') or '—'}"
                  f"  delay {v.get('delayMin') or 0}min")
    print('  flightdata.js updated')


if __name__ == '__main__':
    main()
