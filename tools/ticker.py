#!/usr/bin/env python3
"""Quote strip: the market indices plus whatever Breakout Scout is watching.

Symbols come from signalsdata.js, so the tape always tracks the current picks —
no separate watchlist to maintain. Yahoo's chart endpoint is unofficial but needs
no key; each symbol fails independently so one delisting never blanks the tape.
"""
import json, os, re, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
INDICES = [('^GSPC', 'S&P'), ('^IXIC', 'NASDAQ'), ('^DJI', 'DOW')]


def picks():
    try:
        raw = open(os.path.join(ROOT, 'signalsdata.js')).read()
        d = json.loads(raw[raw.index('=') + 1:].rstrip().rstrip(';'))
        return [p['ticker'] for p in d.get('picks', [])][:8]
    except Exception:
        return []


def quote(args):
    sym, label = args
    url = (f'https://query1.finance.yahoo.com/v8/finance/chart/'
           f'{urllib.request.quote(sym)}?interval=1d&range=2d')
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=15) as r:
            meta = json.load(r)['chart']['result'][0]['meta']
        price = meta.get('regularMarketPrice')
        prev = meta.get('chartPreviousClose') or meta.get('previousClose')
        if price is None or not prev:
            return None
        return {'sym': label or sym, 'px': round(price, 2),
                'chg': round(100 * (price - prev) / prev, 2)}
    except Exception:
        return None


def main():
    quiet = '--quiet' in sys.argv
    want = INDICES + [(t, t) for t in picks()]
    with ThreadPoolExecutor(max_workers=6) as ex:
        rows = [q for q in ex.map(quote, want) if q]

    out = {'rows': rows, 'fetched': datetime.now().strftime('%H:%M')}
    open(os.path.join(ROOT, 'tickerdata.js'), 'w').write(
        'const TICKER=' + json.dumps(out, separators=(',', ':')) + ';\n')
    print(f"  {len(rows)}/{len(want)} quotes")
    if not quiet:
        for r in rows:
            print(f"    {r['sym']:8s} {r['px']:>10,.2f}  {r['chg']:+.2f}%")
    print('  tickerdata.js updated')


if __name__ == '__main__':
    main()
