#!/usr/bin/env python3
"""Content pipeline status: what's queued, what's waiting on approval, what's broken.

Reads the four pipelines' own on-disk state — no APIs, no posting, strictly
read-only. The point is the failure modes: a queue whose dated posts are in the
past means the poster is silently down, and a cron that exits 0 while its output
stops appearing is broken in the way that never gets noticed.
"""
import json, os, re, sys
from datetime import date, datetime

GH = os.path.expanduser('~/Documents/GitHub')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATE_RE = re.compile(r'(\d{4}-\d{2}-\d{2})')


def d_of(name):
    m = DATE_RE.search(name)
    try:
        return datetime.strptime(m.group(1), '%Y-%m-%d').date() if m else None
    except ValueError:
        return None


def listdir(*p):
    try:
        return sorted(x for x in os.listdir(os.path.join(GH, *p))
                      if not x.startswith('.'))
    except OSError:
        return []


def night_signal(today):
    q = listdir('night-signal-ig', 'queue')
    posted = listdir('night-signal-ig', 'posted')
    dates = [d for d in (d_of(x) for x in q) if d]
    overdue = sum(1 for d in dates if d < today)
    runway = max(((d - today).days for d in dates), default=-1)
    last = max((d for d in (d_of(x) for x in posted) if d), default=None)
    state = 'broken' if overdue else ('low' if runway <= 2 else 'ok')
    note = (f'{overdue} POSTS OVERDUE — POSTER DOWN' if overdue
            else f'{runway}d of queue left')
    return {'name': 'NIGHT SIGNAL', 'queued': len(q), 'posted': len(posted),
            'last': str(last) if last else None, 'state': state, 'note': note}


def paint_town(today):
    q = listdir('paint-the-town-ig', 'queue')
    posted = listdir('paint-the-town-ig', 'posted')
    approved = unapproved = 0
    for item in q:
        p = os.path.join(GH, 'paint-the-town-ig', 'queue', item, 'approved')
        approved += os.path.exists(p)
        unapproved += not os.path.exists(p)
    last = max((d for d in (d_of(x) for x in posted) if d), default=None)
    state = 'ok' if approved >= 3 else 'low'
    note = (f'{unapproved} AWAITING YOUR APPROVAL' if unapproved
            else f'{approved} approved and ready')
    return {'name': 'PAINT THE TOWN', 'queued': len(q), 'approved': approved,
            'waiting': unapproved, 'posted': len(posted),
            'last': str(last) if last else None, 'state': state, 'note': note}


def page4films(today):
    backlog = sum(len(listdir('page4films-ig', d))
                  for d in ('backlog-posts', 'backlog-carousels', 'backlog-reels'))
    posted = listdir('page4films-ig', 'posted')
    last = max((d for d in (d_of(x) for x in posted) if d), default=None)
    runway = round(backlog / 3 * 7)          # MWF cadence
    stale = last and (today - last).days > 4  # >1 missed MWF slot
    state = 'broken' if stale else ('low' if runway < 7 else 'ok')
    note = (f'LAST POST {last} — CADENCE SLIPPED' if stale
            else f'~{runway}d of backlog at MWF')
    return {'name': 'PAGE 4 FILMS', 'queued': backlog, 'posted': len(posted),
            'last': str(last) if last else None, 'state': state, 'note': note}


def growth_scan(today):
    digests = [d for d in (d_of(x) for x in listdir('growth-scan', 'outbox')) if d]
    last = max(digests, default=None)
    days = (today - last).days if last else 999
    # Mon/Thu cadence: anything older than 5 days means runs are failing —
    # even though its own runs.log happily records exit=0.
    state = 'broken' if days > 5 else 'ok'
    note = (f'NO DIGEST IN {days}d — CRON EXITS 0 BUT FAILS (EPERM)'
            if state == 'broken' else 'digests current')
    return {'name': 'GROWTH SCAN', 'queued': 0, 'posted': len(digests),
            'last': str(last) if last else None, 'state': state, 'note': note}


def main():
    quiet = '--quiet' in sys.argv
    today = date.today()
    rows = [f(today) for f in (night_signal, paint_town, page4films, growth_scan)]
    order = {'broken': 0, 'low': 1, 'ok': 2}
    rows.sort(key=lambda r: order.get(r['state'], 9))
    broken = sum(1 for r in rows if r['state'] == 'broken')
    waiting = sum(r.get('waiting', 0) for r in rows)

    out = {'rows': rows, 'broken': broken, 'waiting': waiting,
           'fetched': datetime.now().strftime('%H:%M')}
    open(os.path.join(ROOT, 'queuedata.js'), 'w').write(
        'const QUEUES=' + json.dumps(out, separators=(',', ':')) + ';\n')

    print(f"  {len(rows)} pipelines: {broken} broken, {waiting} items awaiting approval")
    if not quiet:
        for r in rows:
            print(f"    {r['state']:7s} {r['name']:15s} q={r['queued']:<3} "
                  f"last={r['last'] or '—'}  {r['note']}")
    print('  queuedata.js updated')


if __name__ == '__main__':
    main()
