#!/usr/bin/env python3
"""Work mail + calendar via Microsoft Graph (M365, delegated, read-only).

Uses Microsoft's public "Graph Command Line Tools" client with the device-code
flow — no app registration in the tenant. Scopes are Mail.Read and
Calendars.Read only: this tool cannot send, move, or delete anything.

  work.py auth    one-time sign-in: prints a code, Simon enters it at
                  microsoft.com/devicelogin with the work account
  work.py         fetch unread mail + next events -> workdata.js

The refresh token lives in the Keychain (jarvis-mirror / msgraph-refresh) and is
rotated there on every refresh. Access tokens are never persisted.
"""
import json, os, subprocess, sys, time, urllib.parse, urllib.request
import vault

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT = '14d82eec-204b-4c2f-b7e8-296a70dab67e'   # Microsoft Graph Command Line Tools
AUTH = 'https://login.microsoftonline.com/organizations/oauth2/v2.0'
SCOPE = ('https://graph.microsoft.com/Mail.Read '
         'https://graph.microsoft.com/Calendars.Read offline_access')
GRAPH = 'https://graph.microsoft.com/v1.0'
KC = ('jarvis-mirror', 'msgraph-refresh')


def kc_get():
    return vault.get(KC[0], KC[1])


def kc_set(v):
    vault.put(KC[0], KC[1], v)


def post(url, data):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(),
                                 headers={'User-Agent': 'jarvis-mirror/0.1'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r), None
    except urllib.error.HTTPError as e:
        try:
            return None, json.loads(e.read())
        except Exception:
            return None, {'error': f'http_{e.code}'}


def auth():
    d, err = post(f'{AUTH}/devicecode', {'client_id': CLIENT, 'scope': SCOPE})
    if err:
        sys.exit(f"device code request failed: {err.get('error_description', err)}")
    print(f"\n  1. Open   {d['verification_uri']}")
    print(f"  2. Enter  {d['user_code']}")
    print(f"  3. Sign in with your WORK Microsoft 365 account\n")
    print(f"  waiting (expires in {d['expires_in']//60} min)...", flush=True)
    while True:
        time.sleep(d.get('interval', 5))
        tok, err = post(f'{AUTH}/token', {
            'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
            'client_id': CLIENT, 'device_code': d['device_code']})
        if tok:
            kc_set(tok['refresh_token'])
            print('  SIGNED IN — refresh token stored in Keychain.')
            return
        code = err.get('error', '')
        if code == 'authorization_pending':
            continue
        sys.exit(f"  FAILED: {code} — {err.get('error_description','')[:200]}")


def access_token():
    rt = kc_get()
    if not rt:
        sys.exit('not signed in — run: tools/work.py auth')
    tok, err = post(f'{AUTH}/token', {
        'grant_type': 'refresh_token', 'client_id': CLIENT,
        'scope': SCOPE, 'refresh_token': rt})
    if err:
        sys.exit(f"token refresh failed ({err.get('error','?')}) — rerun: tools/work.py auth")
    if tok.get('refresh_token'):
        kc_set(tok['refresh_token'])          # rotate
    return tok['access_token']


def get(tok, path):
    req = urllib.request.Request(GRAPH + path, headers={
        'Authorization': f'Bearer {tok}', 'User-Agent': 'jarvis-mirror/0.1',
        'Prefer': 'outlook.timezone="America/New_York"'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch(quiet):
    from datetime import datetime, timedelta
    tok = access_token()
    inbox = get(tok, '/me/mailFolders/inbox?$select=unreadItemCount,totalItemCount')
    msgs = get(tok, '/me/mailFolders/inbox/messages'
               '?$top=6&$orderby=receivedDateTime desc'
               '&$select=subject,from,receivedDateTime,isRead')
    now = datetime.now()
    end = (now + timedelta(days=14)).strftime('%Y-%m-%dT%H:%M:%S')
    cal = get(tok, f"/me/calendarView?startDateTime={now.strftime('%Y-%m-%dT%H:%M:%S')}"
              f"&endDateTime={end}&$top=8&$orderby=start/dateTime"
              f"&$select=subject,start,end,isAllDay,location")

    out = {
        'unread': inbox.get('unreadItemCount', 0),
        'total': inbox.get('totalItemCount', 0),
        'items': [{'from': (m.get('from') or {}).get('emailAddress', {}).get('name', '?')[:30],
                   'subject': (m.get('subject') or '(no subject)')[:70],
                   'date': (m.get('receivedDateTime') or '')[:16],
                   'unread': not m.get('isRead', True)}
                  for m in msgs.get('value', [])],
        'events': [{'title': (e.get('subject') or '(untitled)')[:60],
                    'start': (e.get('start') or {}).get('dateTime', '')[:16],
                    'allDay': bool(e.get('isAllDay')),
                    'loc': ((e.get('location') or {}).get('displayName') or '')[:30]}
                   for e in cal.get('value', [])],
        'fetched': now.strftime('%H:%M')}
    open(os.path.join(ROOT, 'workdata.js'), 'w').write(
        'const WORK=' + json.dumps(out, separators=(',', ':')) + ';\n')
    print(f"  work: {out['unread']} unread / {out['total']} inbox, "
          f"{len(out['events'])} events in 14d")
    if not quiet:
        for m in out['items'][:4]:
            print(f"    {'*' if m['unread'] else ' '} {m['from']:26s} {m['subject'][:44]}")
        for e in out['events'][:5]:
            print(f"    {e['start'][5:16]:14s} {e['title'][:46]}")
    print('  workdata.js updated')


if __name__ == '__main__':
    if 'auth' in sys.argv:
        auth()
    else:
        fetch('--quiet' in sys.argv)
