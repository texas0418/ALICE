#!/usr/bin/env python3
"""Headlines from the RSS feeds named in config.local.json.

Feeds are config, not code — swap sources by editing the "news" list, no code
change. Each feed fails independently and parsing is stdlib-only (RSS and Atom),
so one dead source or malformed entry never blanks the card.
"""
import email.utils, json, os, sys, urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {'User-Agent': 'Mozilla/5.0 (jarvis-mirror rss reader)'}
PER_FEED, TOTAL = 4, 10
ATOM = '{http://www.w3.org/2005/Atom}'


def when(node):
    for tag in ('pubDate', f'{ATOM}published', f'{ATOM}updated'):
        v = node.findtext(tag)
        if not v:
            continue
        try:
            return email.utils.parsedate_to_datetime(v)
        except (TypeError, ValueError):
            pass
        try:
            return datetime.fromisoformat(v.replace('Z', '+00:00'))
        except ValueError:
            pass
    return None


def fetch(feed):
    try:
        req = urllib.request.Request(feed['url'], headers=UA)
        with urllib.request.urlopen(req, timeout=15) as r:
            root = ET.fromstring(r.read())
        nodes = root.findall('.//item') or root.findall(f'.//{ATOM}entry')
        out = []
        for n in nodes[:PER_FEED]:
            title = (n.findtext('title') or n.findtext(f'{ATOM}title') or '').strip()
            if not title:
                continue
            d = when(n)
            if d and d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            out.append({'src': feed['label'], 'title': title[:90],
                        'ts': d.astimezone().isoformat(timespec='minutes') if d else None})
        return out
    except Exception:
        return []


def main():
    quiet = '--quiet' in sys.argv
    feeds = json.load(open(os.path.join(ROOT, 'config.local.json'))).get('news', [])
    with ThreadPoolExecutor(max_workers=5) as ex:
        batches = list(ex.map(fetch, feeds))

    # newest first across all sources, then round-robin dedupe so one chatty
    # feed can't monopolise the card
    rows, per = [], {}
    for b in batches:
        for it in b:
            per.setdefault(it['src'], []).append(it)
    while len(rows) < TOTAL and any(per.values()):
        for src in list(per):
            if per[src]:
                rows.append(per[src].pop(0))
    rows = rows[:TOTAL]

    ok = sum(1 for b in batches if b)
    out = {'rows': rows, 'feeds': len(feeds), 'ok': ok,
           'fetched': datetime.now().strftime('%H:%M')}
    open(os.path.join(ROOT, 'newsdata.js'), 'w').write(
        'const NEWS=' + json.dumps(out, separators=(',', ':')) + ';\n')
    print(f"  {len(rows)} headlines from {ok}/{len(feeds)} feeds")
    if not quiet:
        for r in rows[:8]:
            print(f"    [{r['src']:8s}] {r['title'][:64]}")
    print('  newsdata.js updated')


if __name__ == '__main__':
    main()
