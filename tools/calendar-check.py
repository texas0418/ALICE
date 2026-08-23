#!/usr/bin/env python3
"""Request Calendar access and report what EventKit can see.

Run this from YOUR terminal (not through Claude) so the macOS prompt appears in
front of you and the grant lands on the right process.
"""
import threading
from EventKit import EKEventStore, EKEntityTypeEvent
from Foundation import NSDate

store = EKEventStore.alloc().init()
done, st = threading.Event(), {}


def cb(ok, err):
    st['ok'] = bool(ok)
    done.set()


if store.respondsToSelector_('requestFullAccessToEventsWithCompletion:'):
    store.requestFullAccessToEventsWithCompletion_(cb)
else:
    store.requestAccessToEntityType_completion_(EKEntityTypeEvent, cb)
done.wait(60)

if not st.get('ok'):
    raise SystemExit('DENIED — open System Settings > Privacy & Security > Calendars '
                     'and switch on your terminal app, then run this again.')

cals = list(store.calendarsForEntityType_(EKEntityTypeEvent) or [])
print(f'GRANTED. {len(cals)} calendars:')
for c in cals:
    src = c.source().title() if c.source() else '?'
    print(f'   [{src}] {c.title()}')

pred = store.predicateForEventsWithStartDate_endDate_calendars_(
    NSDate.date(), NSDate.dateWithTimeIntervalSinceNow_(21 * 86400), cals)
evs = list(store.eventsMatchingPredicate_(pred) or [])
print(f'\nnext 21 days: {len(evs)} events')
