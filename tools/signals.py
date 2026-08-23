#!/usr/bin/env python3
"""Surface Breakout Scout's output on the mirror.

Reads the CSVs that breakout-scout's own cron jobs already write — this adds no
scraping, no API calls and no schedule of its own. If the scout hasn't run, the
card says so rather than showing stale rows as if they were today's.
"""
import csv, json, os, re, sys
from datetime import datetime, date

SCOUT = os.path.expanduser('~/Documents/GitHub/breakout-scout/data')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOP = 6

# the five event strategies share one schema; signals.csv has its own
STRATS = [('fda', 'FDA'), ('pead', 'EARNINGS'), ('insider', 'INSIDER'),
          ('filing', 'FILINGS'), ('steady', 'STEADY')]


def rows(path):
    if not os.path.exists(path):
        return []
    with open(path, newline='') as f:
        return list(csv.DictReader(f))


def latest(rs):
    """Only the most recent run — these files accumulate history."""
    if not rs:
        return '', []
    d = max(r.get('run_date', '') for r in rs)
    return d, [r for r in rs if r.get('run_date') == d]


def clean(v):
    """Verdicts carry emoji, which look wrong in a thin-line HUD."""
    return re.sub(r'[^\x20-\x7E]', '', v or '').strip().upper()


def num(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def main():
    quiet = '--quiet' in sys.argv
    run_date, main_rows = latest(rows(os.path.join(SCOUT, 'signals.csv')))
    main_rows.sort(key=lambda r: num(r.get('prob_a')), reverse=True)

    picks = [{
        'ticker': r.get('ticker', '?'),
        'close': round(num(r.get('close')), 2),
        'resistance': round(num(r.get('resistance')), 2),
        'stop': round(num(r.get('stop')), 2),
        'prob': round(num(r.get('prob_a')) * 100),
        'verdict': clean(r.get('verdict')),
        'watch': 'WATCH' in clean(r.get('verdict')),
    } for r in main_rows[:TOP]]

    strats = []
    for key, label in STRATS:
        d, rs = latest(rows(os.path.join(SCOUT, f'{key}_signals.csv')))
        pending = sum(1 for r in rs if (r.get('status') or '').lower() == 'pending')
        strats.append({'label': label, 'date': d, 'n': len(rs), 'pending': pending})

    # how stale is the newest thing the scout produced?
    newest = max((s['date'] for s in strats if s['date']), default=run_date)
    try:
        age = (date.today() - datetime.strptime(newest, '%Y-%m-%d').date()).days
    except ValueError:
        age = None

    out = {'runDate': run_date, 'picks': picks, 'strategies': strats,
           'watching': sum(1 for p in picks if p['watch']),
           'total': len(main_rows), 'newest': newest, 'ageDays': age,
           'fetched': datetime.now().strftime('%H:%M')}
    open(os.path.join(ROOT, 'signalsdata.js'), 'w').write(
        'const SIGNALS=' + json.dumps(out, separators=(',', ':')) + ';\n')

    print(f"  run {run_date}: {len(main_rows)} signals, {out['watching']} on watch"
          f"   (newest strategy data {newest}, {age}d old)")
    if not quiet:
        for p in picks:
            print(f"    {p['ticker']:6s} {p['close']:8.2f}  prob {p['prob']:3d}%  "
                  f"stop {p['stop']:7.2f}  {p['verdict']}")
        for s in strats:
            print(f"    {s['label']:9s} {s['n']:3d} rows, {s['pending']:3d} pending  ({s['date']})")
    print('  signalsdata.js updated')


if __name__ == '__main__':
    main()
