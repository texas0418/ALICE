#!/usr/bin/env python3
"""Precipitation radar frames for the area around home (RainViewer, free).

Downloads the latest radar frames as map tiles, stitches the 3x3 around home at
zoom 8 (~300km view), and writes small composite PNGs to radar/ plus an index the
HUD can animate. Grayscale color scheme on purpose: the page tints the echoes
cyan-through-red itself, so the radar obeys the same palette as everything else.
"""
import json, math, os, sys, urllib.request
from datetime import datetime
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'radar')
Z, N = 7, 3            # zoom 7 is RainViewer's max for this product (z8 returns
                       # an error tile); 3x3 at z7 spans ~780km
CROP = 400             # px window cut from the stitch, centred on home (~400km)
FRAMES = 7             # most recent past frames to keep


def tile_of(lat, lng, z):
    n = 2 ** z
    x = (lng + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'jarvis-mirror/0.1'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def main():
    quiet = '--quiet' in sys.argv
    os.makedirs(OUT, exist_ok=True)
    home = json.load(open(os.path.join(ROOT, 'config.local.json')))['home']
    idx = json.loads(fetch('https://api.rainviewer.com/public/weather-maps.json'))
    host = idx['host']
    frames = (idx['radar']['past'] + idx['radar'].get('nowcast', []))[-FRAMES:]

    fx, fy = tile_of(home['lat'], home['lng'], Z)
    cx, cy = int(fx), int(fy)
    # home's pixel position inside the stitched image, so the page can centre it
    px = (fx - (cx - N // 2)) * 256
    py = (fy - (cy - N // 2)) * 256

    kept, wet = [], 0
    for f in frames:
        name = f'frame-{f["time"]}.png'
        path = os.path.join(OUT, name)
        if not os.path.exists(path):
            img = Image.new('L', (256 * N, 256 * N), 0)
            for dx in range(N):
                for dy in range(N):
                    u = (f'{host}{f["path"]}/256/{Z}/{cx - N//2 + dx}/'
                         f'{cy - N//2 + dy}/0/0_0.png')
                    try:
                        raw = Image.open(__import__('io').BytesIO(fetch(u))).convert('RGBA')
                        black = Image.new('RGBA', raw.size, (0, 0, 0, 255))
                        black.alpha_composite(raw)      # transparent = truly no echo
                        img.paste(black.convert('L'), (dx * 256, dy * 256))
                    except Exception:
                        pass
            # crop the wide stitch to a window centred on home
            l = max(0, min(256 * N - CROP, int(px - CROP / 2)))
            t = max(0, min(256 * N - CROP, int(py - CROP / 2)))
            img = img.crop((l, t, l + CROP, t + CROP))
            img.save(path, optimize=True)
        ext = Image.open(path).getextrema()
        if ext[1] > 8:
            wet += 1
        kept.append({'file': f'radar/{name}', 'time': f['time'],
                     'nowcast': f in idx['radar'].get('nowcast', [])})

    # prune frames no longer in the index
    keep_names = {os.path.basename(k['file']) for k in kept}
    for f in os.listdir(OUT):
        if f.startswith('frame-') and f not in keep_names:
            os.remove(os.path.join(OUT, f))

    l = max(0, min(256 * N - CROP, int(px - CROP / 2)))
    t = max(0, min(256 * N - CROP, int(py - CROP / 2)))
    km_px = 40075 / (2 ** Z) / 256 * math.cos(math.radians(home['lat']))
    out = {'frames': kept, 'homePx': [round(px - l, 1), round(py - t, 1)],
           'size': CROP, 'kmAcross': round(km_px * CROP),
           'wet': wet, 'fetched': datetime.now().strftime('%H:%M')}
    open(os.path.join(ROOT, 'radardata.js'), 'w').write(
        'const RADAR=' + json.dumps(out, separators=(',', ':')) + ';\n')
    print(f"  {len(kept)} frames, {wet} with echoes, ~{out['kmAcross']}km across")
    print('  radardata.js updated')


if __name__ == '__main__':
    main()
