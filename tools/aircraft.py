#!/usr/bin/env python3
"""Aircraft near home, from OpenSky's anonymous API.

Feeds the HUD's compass-ring contacts and the AIRSPACE card. Anonymous access is
rate-limited (~400 credits/day); the daemon polls every 10 minutes, well inside
it. Each contact gets distance and bearing from home so the ring can place blips
where the aircraft actually are.
"""
import json, math, os, sys, urllib.request
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOX = 0.28          # degrees ~ 30km around home


def main():
    quiet = '--quiet' in sys.argv
    home = json.load(open(os.path.join(ROOT, 'config.local.json')))['home']
    lat, lng = home['lat'], home['lng']
    url = ('https://opensky-network.org/api/states/all'
           f'?lamin={lat-BOX}&lomin={lng-BOX*1.2}&lamax={lat+BOX}&lomax={lng+BOX*1.2}')
    req = urllib.request.Request(url, headers={'User-Agent': 'jarvis-mirror/0.1'})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            states = (json.load(r).get('states') or [])
    except Exception as e:
        print(f'  opensky: {type(e).__name__} — keeping previous data')
        return

    planes = []
    for s in states:
        plat, plng = s[6], s[5]
        if plat is None or plng is None:
            continue
        dx = (plng - lng) * 92.0        # km per degree at this latitude
        dy = (plat - lat) * 111.0
        planes.append({
            'call': (s[1] or '').strip() or s[0].upper(),
            'km': round(math.hypot(dx, dy), 1),
            'brg': round(math.degrees(math.atan2(dx, dy)) % 360),
            'alt': round(s[7]) if s[7] else None,        # metres, None = on ground
            'spd': round((s[9] or 0) * 1.944),            # m/s -> knots
            'hdg': round(s[10]) if s[10] is not None else None,
            'ground': bool(s[8]),
        })
    planes.sort(key=lambda p: p['km'])

    out = {'planes': planes[:10], 'total': len(planes),
           'airborne': sum(1 for p in planes if not p['ground']),
           'fetched': datetime.now().strftime('%H:%M')}
    open(os.path.join(ROOT, 'aircraftdata.js'), 'w').write(
        'const AIRCRAFT=' + json.dumps(out, separators=(',', ':')) + ';\n')
    print(f"  {out['total']} aircraft, {out['airborne']} airborne")
    if not quiet:
        for p in planes[:6]:
            print(f"    {p['call']:9s} {p['km']:5.1f}km brg {p['brg']:3d}  "
                  f"{'GROUND' if p['ground'] else str(p['alt'])+'m'}  {p['spd']}kt")
    print('  aircraftdata.js updated')


if __name__ == '__main__':
    main()
