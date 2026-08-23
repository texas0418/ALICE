#!/usr/bin/env python3
"""Read upcoming events via EventKit and pull flights out of them.

The [iCloud] source is excluded entirely per Simon — only the hotmail (Exchange)
calendars, subscribed holidays, and local birthdays are read. Flights are detected
from event titles (airline names / IATA flight numbers) so the mirror knows about
a flight the moment the airline email lands on the calendar — no flight API needed
for the schedule itself.
"""
import json, os, re, sys, threading
from datetime import datetime, timedelta

from EventKit import EKEventStore, EKEntityTypeEvent
from Foundation import NSDate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCLUDE_SOURCES = {'icloud'}          # per Simon: never read the iCloud calendars
DAYS = 14
MAX_EVENTS = 10

AIRLINE_IATA = {'united': 'UA', 'delta': 'DL', 'american': 'AA', 'southwest': 'WN',
                'alaska': 'AS', 'jetblue': 'B6', 'spirit': 'NK', 'frontier': 'F9'}
AIRLINES = '|'.join(AIRLINE_IATA)
FLIGHT_RE = re.compile(rf'({AIRLINES})|airlines?|airways|\bflight\b|\b[A-Z]{{2}}\s?\d{{3,4}}\b', re.I)
# Outlook titles read "United Airlines flight 2344 to Washington (G4T32R)":
# bare number after "flight", destination after "to", confirmation code in parens.
FNUM_RE = re.compile(r'\bflight\s+(\d{2,4})', re.I)
DEST_RE = re.compile(r'\bto\s+([A-Za-z][A-Za-z .]*?)\s*\(')
CONF_RE = re.compile(r'\(([A-Z0-9]{6})\)')


def grant(store):
    done, st = threading.Event(), {}

    def cb(ok, err):
        st['ok'] = bool(ok)
        done.set()

    if store.respondsToSelector_('requestFullAccessToEventsWithCompletion:'):
        store.requestFullAccessToEventsWithCompletion_(cb)
    else:
        store.requestAccessToEntityType_completion_(EKEntityTypeEvent, cb)
    done.wait(30)
    return st.get('ok', False)


def main():
    quiet = '--quiet' in sys.argv
    store = EKEventStore.alloc().init()
    if not grant(store):
        raise SystemExit('calendar access denied for this process')

    cals = [c for c in store.calendarsForEntityType_(EKEntityTypeEvent)
            if str(c.source().title() if c.source() else '').lower()
            not in EXCLUDE_SOURCES]

    pred = store.predicateForEventsWithStartDate_endDate_calendars_(
        NSDate.date(), NSDate.dateWithTimeIntervalSinceNow_(DAYS * 86400), cals)
    evs = sorted(store.eventsMatchingPredicate_(pred) or [],
                 key=lambda e: e.startDate().timeIntervalSince1970())

    now = datetime.now()
    events, flights, seen = [], [], set()
    for e in evs:
        title = str(e.title() or '').strip()
        start = datetime.fromtimestamp(e.startDate().timeIntervalSince1970())
        key = (title, start.isoformat())
        if key in seen:                      # the same event can appear via 2 calendars
            continue
        seen.add(key)
        row = {'title': title[:60],
               'cal': str(e.calendar().title() or '')[:18],
               'start': start.isoformat(timespec='minutes'),
               'allDay': bool(e.isAllDay()),
               'today': start.date() == now.date()}
        events.append(row)
        if FLIGHT_RE.search(title) and not e.isAllDay():
            low = title.lower()
            iata = next((c for n, c in AIRLINE_IATA.items() if n in low), '')
            num = FNUM_RE.search(title)
            dest = DEST_RE.search(title)
            conf = CONF_RE.search(title)
            end = (datetime.fromtimestamp(e.endDate().timeIntervalSince1970())
                   if e.endDate() else None)
            flights.append({**row,
                            'fnum': (iata + num.group(1)) if num else None,
                            'dest': dest.group(1).strip() if dest else None,
                            'conf': conf.group(1) if conf else None,
                            'end': end.isoformat(timespec='minutes') if end else None,
                            'inDays': (start.date() - now.date()).days})

    # legs sharing a confirmation code are one trip; the last leg is where
    # you actually end up
    trips = []
    for f in flights:
        t = next((t for t in trips if f['conf'] and t['conf'] == f['conf']), None)
        if t:
            # Outlook can write the same leg twice (once per city in the pair);
            # the same flight number at the same minute is one leg, not two.
            if any(x['fnum'] == f['fnum'] and x['start'] == f['start']
                   for x in t['legs']):
                continue
            t['legs'].append(f)
            t['finalDest'] = f['dest'] or t['finalDest']
        else:
            trips.append({'conf': f['conf'], 'legs': [f],
                          'finalDest': f['dest'], 'start': f['start'],
                          'inDays': f['inDays']})

    out = {'events': events[:MAX_EVENTS], 'total': len(events),
           'today': sum(1 for x in events if x['today']),
           'flights': flights[:6], 'trips': trips[:3],
           'cals': len(cals), 'fetched': now.strftime('%H:%M')}
    open(os.path.join(ROOT, 'calendardata.js'), 'w').write(
        'const CAL=' + json.dumps(out, separators=(',', ':')) + ';\n')

    print(f"  {len(events)} events / {DAYS}d across {len(cals)} calendars "
          f"(iCloud excluded), {out['today']} today, {len(flights)} flights")
    if not quiet:
        for x in events[:8]:
            print(f"    {x['start'][5:16]}  [{x['cal'][:14]:16s}] {x['title'][:44]}")
        for t in trips:
            legs = ' > '.join(x['fnum'] or '?' for x in t['legs'])
            print(f"    TRIP in {t['inDays']}d: {legs} -> {t['finalDest']}  [{t['conf']}]")
    print('  calendardata.js updated')


if __name__ == '__main__':
    main()
