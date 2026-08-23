#!/usr/bin/env python3
"""Read incomplete Apple Reminders via EventKit.

Local and offline — EventKit reads whatever macOS has already synced, so this works
with no network at all. Requires the one-time Reminders permission prompt, granted
to whatever runs it (your terminal now; the launchd agent later, separately).

    ~/.venvs/jarvis/bin/python tools/reminders.py [--quiet]

--quiet prints counts only, never reminder titles, so output is safe to paste.
"""
import json, os, sys, threading
from datetime import datetime, timedelta

from EventKit import EKEventStore, EKEntityTypeReminder

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HORIZON_DAYS = 30
MAX_SHOWN = 8


def ns_to_dt(nsdate):
    if nsdate is None:
        return None
    try:
        return datetime.fromtimestamp(nsdate.timeIntervalSince1970())
    except Exception:
        return None


def grant(store):
    done, state = threading.Event(), {}

    def cb(ok, err):
        state['ok'] = bool(ok)
        done.set()

    if store.respondsToSelector_('requestFullAccessToRemindersWithCompletion:'):
        store.requestFullAccessToRemindersWithCompletion_(cb)
    else:
        store.requestAccessToEntityType_completion_(EKEntityTypeReminder, cb)
    done.wait(30)
    return state.get('ok', False)


def fetch(store):
    cals = store.calendarsForEntityType_(EKEntityTypeReminder)
    pred = store.predicateForIncompleteRemindersWithDueDateStarting_ending_calendars_(
        None, None, cals)
    done, box = threading.Event(), {}

    def cb(items):
        box['items'] = list(items or [])
        done.set()

    store.fetchRemindersMatchingPredicate_completion_(pred, cb)
    done.wait(30)
    return box.get('items', [])


def main():
    quiet = '--quiet' in sys.argv
    store = EKEventStore.alloc().init()
    if not grant(store):
        raise SystemExit('Reminders access denied. Grant it in '
                         'System Settings > Privacy & Security > Reminders.')

    now = datetime.now()
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    horizon = now + timedelta(days=HORIZON_DAYS)

    items = []
    for r in fetch(store):
        due = ns_to_dt(r.dueDateComponents().date()) if r.dueDateComponents() else None
        if due and due > horizon:
            continue
        items.append({
            'title': str(r.title() or '').strip() or '(untitled)',
            'list': str(r.calendar().title() or ''),
            'due': due.isoformat(timespec='minutes') if due else None,
            'overdue': bool(due and due < now),
            'today': bool(due and now <= due <= today_end),
            'priority': int(r.priority() or 0),
        })

    # overdue first, then soonest; undated sink to the bottom — a mirror should
    # lead with what is late, not with whatever happens to sort first
    items.sort(key=lambda x: (not x['overdue'], x['due'] or '9999'))

    out = {
        'items': items[:MAX_SHOWN],
        'total': len(items),
        'overdue': sum(1 for i in items if i['overdue']),
        'today': sum(1 for i in items if i['today']),
        'lists': sorted({i['list'] for i in items}),
        'fetched': now.strftime('%H:%M'),
    }
    open(os.path.join(ROOT, 'remindersdata.js'), 'w').write(
        'const REMINDERS=' + json.dumps(out, separators=(',', ':')) + ';\n')

    print(f"  {out['total']} open   {out['overdue']} overdue   {out['today']} due today"
          f"   across {len(out['lists'])} lists")
    if not quiet:
        for i in out['items']:
            when = i['due'][5:16].replace('T', ' ') if i['due'] else '   —      '
            flag = '!' if i['overdue'] else ' '
            print(f"   {flag} {when}  {i['list'][:18]:20s} {i['title'][:46]}")
    print('  remindersdata.js updated')


if __name__ == '__main__':
    main()
