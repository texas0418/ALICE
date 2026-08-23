#!/usr/bin/env python3
"""Pull traffic-aware routes from Mapbox and fold them into mapdata.js.

The token is read from the macOS Keychain at runtime and never written to disk,
never passed as a command argument, and never printed. Every code path that could
echo a URL is scrubbed, because Mapbox carries the token in the query string and
one unhandled traceback would otherwise leak it into a log.
"""
import json, os, re, subprocess, sys, urllib.request, urllib.error
import vault

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONG = {'low': 0, 'moderate': 1, 'heavy': 2, 'severe': 3, 'unknown': 0}
SCRUB = re.compile(r'pk\.[A-Za-z0-9._\-]+')


def scrub(s):
    return SCRUB.sub('pk.<REDACTED>', str(s))


def token():
    t = vault.get('jarvis-mirror', 'mapbox-token')
    if not t:
        sys.exit('No mapbox-token stored. Run:\n  '
                 + vault.hint('jarvis-mirror', 'mapbox-token'))
    if not t.startswith('pk.'):
        sys.exit('Keychain entry does not look like a Mapbox public token.')
    return t


def route(tok, o, d):
    url = ('https://api.mapbox.com/directions/v5/mapbox/driving-traffic/'
           f'{o[1]},{o[0]};{d[1]},{d[0]}'
           '?geometries=geojson&overview=full&steps=false'
           '&annotations=congestion,duration,distance&access_token=' + tok)
    try:
        with urllib.request.urlopen(url, timeout=45) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = ''
        try:
            body = e.read().decode()[:200]
        except Exception:
            pass
        sys.exit(f'Mapbox HTTP {e.code}: {scrub(body)}')
    except Exception as e:
        sys.exit('Mapbox request failed: ' + scrub(type(e).__name__ + ': ' + str(e)))


def main():
    tok = token()
    path = os.path.join(ROOT, 'mapdata.js')
    raw = open(path).read()
    data = json.loads(raw[raw.index('=') + 1:].rstrip().rstrip(';'))
    home = data['home']

    for key, R in data['routes'].items():
        j = route(tok, home, R['d'])
        if j.get('code') != 'Ok' or not j.get('routes'):
            print(f'  {R["label"]:9s} no route ({scrub(j.get("code"))})')
            continue
        rt = j['routes'][0]
        pts = [[round(c[1], 5), round(c[0], 5)]
               for c in rt['geometry']['coordinates']]
        cong = [CONG.get(c, 0)
                for c in rt['legs'][0]['annotation'].get('congestion', [])]
        if not cong:
            cong = [0] * max(0, len(pts) - 1)

        live = round(rt['duration'] / 60)
        typical = rt.get('duration_typical')
        free = round(typical / 60) if typical else R.get('freeMin', live)

        worst = max(cong) if cong else 0
        share = round(100 * sum(1 for c in cong if c >= 2) / max(1, len(cong)))
        R.update(pts=pts, cong=cong, liveMin=live, freeMin=free,
                 mi=round(rt['distance'] / 1609.34, 1),
                 worst=worst, heavyShare=share)
        print(f'  {R["label"]:9s} {R["mi"]:5.1f} mi  live {live:3d} min  '
              f'typical {free:3d} min  delay {live-free:+3d}  '
              f'heavy/severe on {share:2d}% of segments')

    import time
    data['fetched'] = time.strftime('%H:%M')
    open(path, 'w').write('const MAPDATA=' +
                          json.dumps(data, separators=(',', ':')) + ';\n')
    print('mapdata.js updated:', round(os.path.getsize(path) / 1024), 'KB')


if __name__ == '__main__':
    main()
