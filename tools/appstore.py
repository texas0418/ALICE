#!/usr/bin/env python3
"""App Store Connect status for every app on the account.

Reuses the existing signing key in ~/.appstoreconnect (asc_api.make_jwt), so there
are no new credentials. Reports REVIEW STATE rather than revenue: sales figures
need a vendor number that isn't in the API, and "what is stuck in review" is the
thing you'd actually act on from across a room.
"""
import json, os, socket, sys, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

sys.path.insert(0, os.path.expanduser('~/.appstoreconnect'))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = 'https://api.appstoreconnect.apple.com/v1'
socket.setdefaulttimeout(25)

# states worth pulling to the front, in order of how much they want your attention
ATTENTION = ['REJECTED', 'DEVELOPER_REJECTED', 'METADATA_REJECTED',
             'INVALID_BINARY', 'PENDING_DEVELOPER_RELEASE', 'IN_REVIEW',
             'WAITING_FOR_REVIEW', 'PREPARE_FOR_SUBMISSION']
SHORT = {'READY_FOR_SALE': 'LIVE', 'WAITING_FOR_REVIEW': 'WAITING',
         'IN_REVIEW': 'IN REVIEW', 'PENDING_DEVELOPER_RELEASE': 'AWAITING RELEASE',
         'PREPARE_FOR_SUBMISSION': 'DRAFT', 'REJECTED': 'REJECTED',
         'DEVELOPER_REJECTED': 'PULLED', 'METADATA_REJECTED': 'METADATA',
         'PROCESSING_FOR_APP_STORE': 'PROCESSING', 'REPLACED_WITH_NEW_VERSION': 'SUPERSEDED'}


def get(tok, path):
    req = urllib.request.Request(API + path, headers={'Authorization': 'Bearer ' + tok})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def version_of(args):
    tok, app = args
    aid, name = app['id'], app['attributes'].get('name', '?')
    try:
        d = get(tok, f'/apps/{aid}/appStoreVersions?limit=1')
        items = d.get('data', [])
        if not items:
            return {'name': name, 'state': 'NONE', 'version': '—', 'days': None}
        at = items[0]['attributes']
        raw = at.get('appStoreState') or at.get('appVersionState') or 'UNKNOWN'
        days = None
        try:
            t = datetime.fromisoformat(at['createdDate'].replace('Z', '+00:00'))
            days = (datetime.now(timezone.utc) - t).days
        except Exception:
            pass
        return {'name': name, 'raw': raw, 'state': SHORT.get(raw, raw.replace('_', ' ')),
                'version': at.get('versionString', '—'), 'days': days}
    except urllib.error.HTTPError as e:
        return {'name': name, 'state': f'HTTP {e.code}', 'version': '—', 'days': None}
    except Exception as e:
        return {'name': name, 'state': type(e).__name__, 'version': '—', 'days': None}


def main():
    quiet = '--quiet' in sys.argv
    import asc_api
    tok = asc_api.make_jwt()

    apps = get(tok, '/apps?limit=200&fields[apps]=name,bundleId').get('data', [])
    with ThreadPoolExecutor(max_workers=6) as ex:
        rows = list(ex.map(version_of, [(tok, a) for a in apps]))

    rank = {s: i for i, s in enumerate(ATTENTION)}
    rows.sort(key=lambda r: (rank.get(r.get('raw', ''), 99), r['name'].lower()))

    live = sum(1 for r in rows if r.get('raw') == 'READY_FOR_SALE')
    needs = [r for r in rows if r.get('raw') in ATTENTION]

    out = {'rows': rows[:8], 'total': len(rows), 'live': live,
           'attention': len(needs), 'fetched': datetime.now().strftime('%H:%M')}
    open(os.path.join(ROOT, 'appstoredata.js'), 'w').write(
        'const APPSTORE=' + json.dumps(out, separators=(',', ':')) + ';\n')

    print(f"  {len(rows)} apps: {live} live, {len(needs)} want attention")
    if not quiet:
        for r in rows[:12]:
            print(f"    {r['state'][:18]:20s} {r['name'][:34]:36s} v{r['version']:8s} "
                  f"{str(r.get('days','?')):>4}d")
    print('  appstoredata.js updated')


if __name__ == '__main__':
    main()
