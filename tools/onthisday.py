#!/usr/bin/env python3
"""On this day, from Simon's own git history.

Scans every repo under ~/Documents/GitHub for things that happened on today's
calendar date in an earlier month or year: a repo's very first commit (something
was born today), a tag (something shipped today), or an unusually busy day.
Nobody else's mirror can have this card, because it is literally his history.
"""
import json, os, subprocess, sys
from collections import defaultdict
from datetime import date, datetime

GH = os.path.expanduser('~/Documents/GitHub')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUSY = 12          # commits in one day worth remembering


def git(repo, *args):
    r = subprocess.run(['git', '-C', repo] + list(args),
                       capture_output=True, text=True, timeout=20)
    return r.stdout.strip() if r.returncode == 0 else ''


def ago(d, today):
    days = (today - d).days
    if days < 45:
        return f'{days} days ago'
    months = round(days / 30.4)
    if months < 12:
        return f'{months} months ago'
    years, rem = divmod(months, 12)
    return f'{years} year{"s" if years > 1 else ""} ago' + (
        f', {rem} months' if rem else '')


def main():
    quiet = '--quiet' in sys.argv
    today = date.today()
    md = today.strftime('%m-%d')
    dd = today.strftime('%d')
    events = []

    for name in sorted(os.listdir(GH)):
        repo = os.path.join(GH, name)
        if not os.path.isdir(os.path.join(repo, '.git')):
            continue

        first = git(repo, 'log', '--reverse', '--format=%as', '-1',
                    '--max-parents=0')
        if first and first[8:] == dd and first != str(today):
            d = date.fromisoformat(first)
            events.append({'kind': 'BORN', 'repo': name, 'when': first,
                           'ago': ago(d, today),
                           'text': f'{name} began — first commit {ago(d, today)}'})

        for line in git(repo, 'tag', '--format=%(creatordate:short) %(refname:short)'
                        ).splitlines():
            try:
                dstr, tag = line.split(' ', 1)
            except ValueError:
                continue
            if dstr[8:] == dd and dstr != str(today):
                d = date.fromisoformat(dstr)
                events.append({'kind': 'SHIPPED', 'repo': name, 'when': dstr,
                               'ago': ago(d, today),
                               'text': f'{name} tagged {tag} {ago(d, today)}'})

        counts = defaultdict(int)
        for dstr in git(repo, 'log', '--format=%as').splitlines():
            if dstr[5:] == md and dstr != str(today):
                counts[dstr] += 1
        for dstr, n in counts.items():
            if n >= BUSY:
                d = date.fromisoformat(dstr)
                events.append({'kind': 'BUSY', 'repo': name, 'when': dstr,
                               'ago': ago(d, today),
                               'text': f'{n} commits into {name} {ago(d, today)}'})

    order = {'BORN': 0, 'SHIPPED': 1, 'BUSY': 2}
    events.sort(key=lambda e: (order[e['kind']], e['when']))

    out = {'date': today.strftime('%B %-d').upper(), 'events': events[:6],
           'total': len(events), 'fetched': datetime.now().strftime('%H:%M')}
    open(os.path.join(ROOT, 'onthisdaydata.js'), 'w').write(
        'const OTD=' + json.dumps(out, separators=(',', ':')) + ';\n')
    print(f"  {len(events)} events on {md} across the repos")
    if not quiet:
        for e in events[:6]:
            print(f"    {e['kind']:7s} {e['text'][:64]}")
    print('  onthisdaydata.js updated')


if __name__ == '__main__':
    main()
