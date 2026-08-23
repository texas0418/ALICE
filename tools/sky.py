#!/usr/bin/env python3
"""Sky tonight: visible ISS passes over home, plus upcoming rocket launches.

ISS passes are computed locally — TLE from Celestrak, propagated with sgp4 at
30-second steps over the next 48h. A pass is kept when the station rises above
20 degrees and the sky is dark enough to see it (within ~90 min of sunrise or
sunset, taken from weatherdata.js). Launches from Launch Library 2 (free).
"""
import json, math, os, sys, urllib.request
from datetime import datetime, timedelta, timezone

from sgp4.api import Satrec, jday

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {'User-Agent': 'jarvis-mirror/0.1'}
STEP, HOURS, MIN_ELEV = 30, 48, 20


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def observer_ecef(lat, lng, alt_km=0.3):
    a, e2 = 6378.137, 6.69437999e-3
    la, lo = math.radians(lat), math.radians(lng)
    n = a / math.sqrt(1 - e2 * math.sin(la) ** 2)
    return ((n + alt_km) * math.cos(la) * math.cos(lo),
            (n + alt_km) * math.cos(la) * math.sin(lo),
            (n * (1 - e2) + alt_km) * math.sin(la))


def elevation(sat, obs, lat, lng, t):
    jd, fr = jday(t.year, t.month, t.day, t.hour, t.minute, t.second)
    err, pos, _ = sat.sgp4(jd, fr)
    if err:
        return None
    # rotate TEME -> ECEF by GMST (good to a fraction of a degree; fine for passes)
    gmst = (280.46061837 + 360.98564736629 * (jd + fr - 2451545.0)) % 360
    g = math.radians(gmst)
    x = pos[0] * math.cos(g) + pos[1] * math.sin(g)
    y = -pos[0] * math.sin(g) + pos[1] * math.cos(g)
    z = pos[2]
    rx, ry, rz = x - obs[0], y - obs[1], z - obs[2]
    la, lo = math.radians(lat), math.radians(lng)
    # ENU up-component
    up = (math.cos(la) * math.cos(lo) * rx + math.cos(la) * math.sin(lo) * ry
          + math.sin(la) * rz)
    rng = math.sqrt(rx * rx + ry * ry + rz * rz)
    return math.degrees(math.asin(up / rng))


def dark_windows(w):
    """Rough visibility: within 95 min after sunset / before sunrise."""
    def mins(t):
        h, m = map(int, t.split(':'))
        return h * 60 + m
    if not w:
        return lambda t: True
    sr, ss = mins(w['sunrise']), mins(w['sunset'])
    def dark(t):
        m = t.hour * 60 + t.minute
        return (ss - 10 <= m <= ss + 95) or (sr - 95 <= m <= sr + 10)
    return dark


def main():
    quiet = '--quiet' in sys.argv
    home = json.load(open(os.path.join(ROOT, 'config.local.json')))['home']
    try:
        raw = open(os.path.join(ROOT, 'weatherdata.js')).read()
        w = json.loads(raw[raw.index('=') + 1:].rstrip().rstrip(';'))
    except Exception:
        w = None

    tle = fetch('https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE'
                ).decode().strip().splitlines()
    sat = Satrec.twoline2rv(tle[-2], tle[-1])
    obs = observer_ecef(home['lat'], home['lng'])
    is_dark = dark_windows(w)

    passes, cur = [], None
    t = datetime.now()
    for i in range(HOURS * 3600 // STEP):
        tt = t + timedelta(seconds=i * STEP)
        el = elevation(sat, obs, home['lat'], home['lng'], tt)
        if el is None:
            continue
        if el > MIN_ELEV:
            if cur is None:
                cur = {'start': tt, 'max': el, 'peak': tt}
            elif el > cur['max']:
                cur.update(max=el, peak=tt)
        elif cur:
            if is_dark(cur['peak']):
                passes.append({'start': cur['start'].isoformat(timespec='minutes'),
                               'peak': cur['peak'].strftime('%a %H:%M').upper(),
                               'maxElev': round(cur['max'])})
            cur = None

    launches = []
    try:
        d = json.loads(fetch('https://ll.thespacedevs.com/2.2.0/launch/upcoming/'
                             '?limit=3&hide_recent_previous=true'))
        for r in d.get('results', []):
            launches.append({'name': r['name'][:60], 'net': r['net'][:16],
                             'pad': ((r.get('pad') or {}).get('location') or {})
                                    .get('name', '')[:28],
                             'status': ((r.get('status') or {}).get('abbrev') or '')})
    except Exception as e:
        print(f'  launches: {type(e).__name__}')

    out = {'passes': passes[:3], 'launches': launches,
           'tleAge': tle[0][:40].strip() if tle else '',
           'fetched': datetime.now().strftime('%H:%M')}
    open(os.path.join(ROOT, 'skydata.js'), 'w').write(
        'const SKY=' + json.dumps(out, separators=(',', ':')) + ';\n')
    print(f"  {len(passes)} visible ISS passes in 48h, {len(launches)} launches")
    if not quiet:
        for p in passes[:3]:
            print(f"    ISS  {p['peak']}  max {p['maxElev']}°")
        for l in launches:
            print(f"    {l['net']}  {l['name'][:52]}")
    print('  skydata.js updated')


if __name__ == '__main__':
    main()
