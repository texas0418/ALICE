#!/usr/bin/env python3
"""Build status across every repo that has CI, via the gh CLI.

Uses the already-authenticated gh login — no token handling here. Repos are
discovered by looking for .github/workflows plus a GitHub remote, so adding a
repo needs no config change.
"""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

GH = os.path.expanduser('~/Documents/GitHub')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKERS = 8
TIMEOUT = 25


def repos():
    out = []
    for name in sorted(os.listdir(GH)):
        d = os.path.join(GH, name)
        if not os.path.isdir(os.path.join(d, '.github', 'workflows')):
            continue
        r = subprocess.run(['git', '-C', d, 'remote', 'get-url', 'origin'],
                           capture_output=True, text=True)
        if r.returncode != 0:
            continue
        url = r.stdout.strip()
        if 'github.com' not in url:
            continue
        slug = url.split('github.com')[-1].lstrip(':/').removesuffix('.git')
        out.append(slug)
    return sorted(set(out))


def latest(slug):
    try:
        r = subprocess.run(
            ['gh', 'run', 'list', '--repo', slug, '--limit', '1', '--json',
             'conclusion,status,displayTitle,workflowName,updatedAt,headBranch'],
            capture_output=True, text=True, timeout=TIMEOUT)
        if r.returncode != 0:
            return {'repo': slug, 'state': 'error', 'note': 'gh failed'}
        runs = json.loads(r.stdout or '[]')
        if not runs:
            return {'repo': slug, 'state': 'none', 'note': 'no runs'}
        x = runs[0]
        status, concl = x.get('status'), x.get('conclusion')
        state = ('running' if status != 'completed'
                 else 'pass' if concl == 'success'
                 else 'fail' if concl in ('failure', 'timed_out', 'startup_failure')
                 else 'other')
        days = None
        try:
            t = datetime.fromisoformat(x['updatedAt'].replace('Z', '+00:00'))
            days = (datetime.now(timezone.utc) - t).days
        except Exception:
            pass
        return {'repo': slug.split('/')[-1], 'state': state,
                'workflow': (x.get('workflowName') or '')[:24],
                'title': (x.get('displayTitle') or '')[:52],
                'branch': x.get('headBranch') or '', 'days': days,
                'concl': concl or status}
    except subprocess.TimeoutExpired:
        return {'repo': slug.split('/')[-1], 'state': 'error', 'note': 'timeout'}


def main():
    quiet = '--quiet' in sys.argv
    slugs = repos()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        rows = list(ex.map(latest, slugs))

    # red first, then anything mid-flight, then stalest — a mirror should lead
    # with what is broken, not with whatever sorted alphabetically
    order = {'fail': 0, 'error': 1, 'running': 2, 'other': 3, 'none': 4, 'pass': 5}
    rows.sort(key=lambda r: (order.get(r['state'], 9), -(r.get('days') or 0)))

    counts = {}
    for r in rows:
        counts[r['state']] = counts.get(r['state'], 0) + 1

    out = {'rows': rows[:8], 'all': len(rows), 'counts': counts,
           'failing': counts.get('fail', 0) + counts.get('error', 0),
           'running': counts.get('running', 0),
           'passing': counts.get('pass', 0),
           'fetched': datetime.now().strftime('%H:%M')}
    open(os.path.join(ROOT, 'cidata.js'), 'w').write(
        'const CI=' + json.dumps(out, separators=(',', ':')) + ';\n')

    print(f"  {len(rows)} repos: {out['passing']} green, {out['failing']} red, "
          f"{out['running']} running")
    if not quiet:
        for r in rows[:10]:
            print(f"    {r['state']:8s} {r['repo'][:26]:28s} "
                  f"{str(r.get('days','?')):>3}d  {r.get('workflow','')}")
    print('  cidata.js updated')


if __name__ == '__main__':
    main()
