#!/usr/bin/env python3
"""Parse the digests Auction Scout and Acquisition Scout already produce.

Both write logs/digest_preview.html — the same HTML they email. Reading that adds
no scraping and no second schedule; the mirror shows whatever the last run found,
and says how old it is rather than implying it is today's.
"""
import html, json, os, re, sys
from datetime import date, datetime

GH = os.path.expanduser('~/Documents/GitHub')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOP = 6


def txt(x):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html.unescape(x))).strip()


def load(project):
    p = os.path.join(GH, project, 'logs', 'digest_preview.html')
    if not os.path.exists(p):
        return None, None
    s = open(p, encoding='utf-8', errors='replace').read()
    return s, datetime.fromtimestamp(os.path.getmtime(p))


def age_of(d):
    return (date.today() - d.date()).days if d else None


def money(s):
    m = re.search(r'\$([\d,]+)', s or '')
    return int(m.group(1).replace(',', '')) if m else None


def parse_auction():
    s, mtime = load('auction-scout')
    if not s:
        return {'error': 'no digest'}
    run = (re.search(r'Auction Scout\s*[—-]\s*(\d{4}-\d{2}-\d{2})', txt(s)) or [None, ''])[1]
    total = (re.search(r'([\d,]+)\s+tracts', txt(s)) or [None, '0'])[1]

    items = []
    for r in re.findall(r'<tr[^>]*>(.*?)</tr>', s, re.S):
        c = [txt(x) for x in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', r, re.S)]
        if len(c) < 6 or not c[0].isdigit():
            continue
        prop = c[1]
        area = re.search(r'·\s*([A-Za-z ]+area)\s*\(([\d.]+)\s*mi\)', prop)
        items.append({
            'rank': int(c[0]),
            'address': re.split(r'\s*·\s*', prop)[0][:52],
            'area': (area.group(1).replace(' area', '').upper() if area else '—'),
            'miles': float(area.group(2)) if area else None,
            'date': c[2] if re.match(r'\d{4}-\d{2}-\d{2}', c[2]) else '—',
            'allIn': money(re.search(r'=\s*(\$[\d,]+)\s*all-in', c[3]).group(1))
                     if re.search(r'=\s*\$[\d,]+\s*all-in', c[3]) else money(c[3]),
            'value': money(c[4]),
        })

    # County sales list many tracts under one name; collapse them.
    seen, uniq = set(), []
    for i in items:
        k = i['address']
        if k in seen:
            continue
        seen.add(k)
        uniq.append(i)
    items = uniq

    for i in items:
        i['upside'] = (round(100 * (i['value'] - i['allIn']) / i['allIn'])
                       if i['value'] and i['allIn'] else None)

    # Lead with what's actionable — priced, valued, and close to home. A tract with
    # no cost figure is not a lead, however near it is.
    items.sort(key=lambda i: (i['upside'] is None,
                              i['miles'] is None,
                              i['miles'] if i['miles'] is not None else 9e9))
    return {'run': run, 'total': int(total.replace(',', '')), 'items': items[:TOP],
            'nearby': sum(1 for i in items if (i['miles'] or 999) < 60),
            'ageDays': age_of(mtime)}


def parse_acquisition():
    s, mtime = load('acquisition-scout')
    if not s:
        return {'error': 'no digest'}
    t = txt(s)
    total = (re.search(r'(\d+)\s+candidates', t) or [None, '0'])[1]
    tiers = {k: int(v) for v, k in
             re.findall(r'(?:Look now|Worth a look|Long shots)\s*\((\d+)\)', t) and
             zip(re.findall(r'(?:Look now|Worth a look|Long shots)\s*\((\d+)\)', t),
                 ['lookNow', 'worthLook', 'longShots'])}

    items = []
    for r in re.findall(r'<tr[^>]*>(.*?)</tr>', s, re.S):
        b = txt(r)
        m = re.search(r'OFF-MARKET SCORE\s+(\d+)\s+([A-Za-z &]+?)\s*·\s*(.+?)\s+'
                      r'([\d,]+)\s+ratings at\s+([\d.]+)★\s*·\s*no update in\s+(\d+)\s+months', b)
        if not m:
            continue
        items.append({'score': int(m.group(1)), 'cat': m.group(2).strip().upper(),
                      'name': m.group(3).strip()[:46], 'ratings': int(m.group(4).replace(',', '')),
                      'stars': float(m.group(5)), 'months': int(m.group(6))})
    items.sort(key=lambda i: -i['score'])
    return {'total': int(total), 'tiers': tiers, 'items': items[:TOP],
            'ageDays': age_of(mtime)}


def main():
    quiet = '--quiet' in sys.argv
    out = {'auction': parse_auction(), 'acquisition': parse_acquisition(),
           'fetched': datetime.now().strftime('%H:%M')}
    open(os.path.join(ROOT, 'scoutsdata.js'), 'w').write(
        'const SCOUTS=' + json.dumps(out, separators=(',', ':')) + ';\n')

    a, q = out['auction'], out['acquisition']
    print(f"  auction     {a.get('total','?')} tracts, {a.get('nearby','?')} within 60mi"
          f"   ({a.get('ageDays','?')}d old)")
    print(f"  acquisition {q.get('total','?')} candidates, {q.get('tiers',{}).get('lookNow','?')} to look at now"
          f"   ({q.get('ageDays','?')}d old)")
    if not quiet:
        for i in a.get('items', []):
            print(f"    {i['area']:9s} {str(i['miles']):>6}mi  {str(i['allIn']):>9}  {i['address'][:40]}")
        for i in q.get('items', []):
            print(f"    {i['score']:3d}  {i['cat'][:12]:14s} {i['name'][:34]:36s} "
                  f"{i['ratings']:>7,} @ {i['stars']}  {i['months']}mo")
    print('  scoutsdata.js updated')


if __name__ == '__main__':
    main()
