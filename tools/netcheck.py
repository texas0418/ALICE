#!/usr/bin/env python3
"""Is IMAP reachable from this network at all? Distinguishes a blocked network
from a wrong mail host — the two produce identical timeouts."""
import socket
HOSTS = ['imap.gmail.com', 'outlook.office365.com',
         'mail.simonbuilds.app', 'mail.page4films.com']
for h in HOSTS:
    row = []
    for p in (993, 443):
        try:
            socket.create_connection((h, p), timeout=8).close()
            row.append(f'{p}:OPEN')
        except Exception as e:
            row.append(f'{p}:{type(e).__name__}')
    print(f'  {h:26s} ' + '  '.join(row))
print('\n  If gmail/outlook 993 are also blocked, it is this network, not your mail host.')
