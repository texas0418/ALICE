#!/usr/bin/env python3
"""Read unread-mail summaries over IMAP for every account in config.local.json.

Passwords come from the macOS Keychain at runtime (service `jarvis-mail`, account =
the email address). They are never written to disk, never passed as arguments, and
every error path is scrubbed before printing.

READ-ONLY BY DESIGN: mailboxes are selected with readonly=True so that looking at
your inbox on the mirror never marks anything as read. Getting this wrong once would
mean the mirror silently eats your unread flags, which you would notice far too late.
"""
import email, imaplib, json, os, re, ssl, subprocess, sys, time
from email.header import decode_header, make_header
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PER_ACCOUNT = 6          # newest messages to summarise
ATTEMPTS    = 3          # a slow link is not a failure
imaplib._MAXLINE = 400000


def keychain(address):
    r = subprocess.run(['security', 'find-generic-password',
                        '-a', address, '-s', 'jarvis-mail', '-w'],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def clean(raw):
    if not raw:
        return ''
    try:
        s = str(make_header(decode_header(raw)))
    except Exception:
        s = str(raw)
    return re.sub(r'\s+', ' ', s).strip()


def sender(msg):
    name, addr = email.utils.parseaddr(msg.get('From', ''))
    name = clean(name)
    return name or addr or 'unknown'


def when(msg):
    try:
        d = email.utils.parsedate_to_datetime(msg.get('Date'))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone().isoformat(timespec='minutes')
    except Exception:
        return ''


def fetch(acct):
    pw = keychain(acct['address'])
    if not pw:
        return {'error': 'no Keychain entry'}
    M, last = None, None
    for attempt in range(ATTEMPTS):
        try:
            M = imaplib.IMAP4_SSL(acct['host'], acct.get('port', 993),
                                  ssl_context=ssl.create_default_context(), timeout=25)
            break
        except Exception as e:
            last = type(e).__name__
            if attempt < ATTEMPTS - 1:
                time.sleep(2 * (attempt + 1))
    if M is None:
        hint = (' — port 993 looks blocked on this network; try ethernet'
                if last == 'TimeoutError' else '')
        return {'error': f'connect failed after {ATTEMPTS} tries: {last}{hint}'}
    try:
        M.login(acct['address'], pw)
    except Exception as e:
        M.logout()
        return {'error': 'login rejected: ' + re.sub(re.escape(pw), '<redacted>', str(e))}
    try:
        # readonly: looking must never mutate the mailbox
        M.select('INBOX', readonly=True)
        ok, d = M.search(None, 'UNSEEN')
        unseen = set(d[0].split()) if ok == 'OK' else set()
        ok, d = M.search(None, 'ALL')
        allids = d[0].split() if ok == 'OK' else []

        # Summarise the newest messages whether read or not. A low-volume address
        # that only ever reports "0 unread" is a dead panel; recent mail is the
        # thing actually worth showing on the glass.
        items = []
        for i in reversed(allids[-PER_ACCOUNT:]):
            ok, d = M.fetch(i, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])')
            if ok != 'OK' or not d or not isinstance(d[0], tuple):
                continue
            m = email.message_from_bytes(d[0][1])
            items.append({'from': sender(m),
                          'subject': clean(m.get('Subject')) or '(no subject)',
                          'date': when(m),
                          'unread': i in unseen})
        return {'unread': len(unseen), 'total': len(allids), 'items': items}
    except Exception as e:
        return {'error': f'{type(e).__name__}: {e}'}
    finally:
        try:
            M.close()
        except Exception:
            pass
        M.logout()


def main():
    # --quiet prints connection status and counts only, never senders or subjects,
    # so output can be pasted into a chat or a log without leaking mail contents.
    quiet = '--quiet' in sys.argv
    cfg = json.load(open(os.path.join(ROOT, 'config.local.json')))
    out = {'accounts': [], 'fetched': datetime.now().strftime('%H:%M')}
    for acct in cfg['mail']:
        r = fetch(acct)
        r.update(label=acct['label'], address=acct['address'])
        out['accounts'].append(r)
        if 'error' in r:
            print(f'  {acct["label"]:14s} ERROR  {r["error"]}')
        else:
            print(f'  {acct["label"]:14s} {r["unread"]:3d} unread / '
                  f'{r.get("total",0):4d} in inbox, {len(r["items"])} summarised')
            if not quiet:
                for it in r['items'][:3]:
                    print(f'      {it["from"][:26]:28s} {it["subject"][:52]}')
    total = sum(a.get('unread', 0) for a in out['accounts'])
    out['total'] = total
    open(os.path.join(ROOT, 'maildata.js'), 'w').write(
        'const MAILDATA=' + json.dumps(out, separators=(',', ':')) + ';\n')
    print(f'  total {total} unread -> maildata.js')


if __name__ == '__main__':
    main()
