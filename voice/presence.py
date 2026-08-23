#!/usr/bin/env python3
"""mmWave presence -> mirror wake/sleep. For the DFRobot SEN0395 on USB serial.

The sensor streams "$JYBSS,1, , , *" when someone is present, ",0," when the room
is empty. On a state change this writes a presence command into controldata.js —
the same channel the phone remote uses — and the HUD sleeps or wakes. Runs only
when the sensor exists; safe to launch before it arrives (it just waits).

    ~/.venvs/jarvis/bin/python voice/presence.py [--port /dev/cu.usbserial-XXXX]

EMPTY_HOLD keeps the mirror awake through brief absences (leaning out of frame),
so it doesn't flicker off every time you bend over the sink.
"""
import glob, json, os, sys, time

import serial

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAUD = 115200
EMPTY_HOLD = 90        # seconds of continuous absence before sleeping


def find_port():
    for a in sys.argv:
        if a.startswith('--port'):
            return sys.argv[sys.argv.index(a) + 1] if a == '--port' else a.split('=')[1]
    hits = (glob.glob('/dev/cu.usbserial*') + glob.glob('/dev/cu.usbmodem*')   # macOS
            + glob.glob('/dev/cu.SLAB*') + glob.glob('/dev/cu.wchusbserial*')
            + glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*'))             # Linux
    return hits[0] if hits else None


def send(state):
    cmd = {'k': 'presence', 'v': 'on' if state else 'off',
           'seq': int(time.time() * 1000)}
    tmp = os.path.join(ROOT, 'controldata.js.tmp')
    open(tmp, 'w').write('const CONTROL=' + json.dumps(cmd) + ';\n')
    os.replace(tmp, os.path.join(ROOT, 'controldata.js'))
    print(f'  presence -> {"PRESENT" if state else "EMPTY"}')


def main():
    port = find_port()
    while not port:
        print('  no serial sensor found — plug in the SEN0395; retrying in 30s')
        time.sleep(30)
        port = find_port()
    print(f'  sensor on {port}')
    ser = serial.Serial(port, BAUD, timeout=2)

    present, last_seen = None, 0.0
    while True:
        line = ser.readline().decode('ascii', 'replace').strip()
        now = time.time()
        if '$JYBSS' in line:
            hot = ',1,' in line.replace(' ', '')
            if hot:
                last_seen = now
                if present is not True:
                    present = True
                    send(True)
            elif present is not False and now - last_seen > EMPTY_HOLD:
                present = False
                send(False)


if __name__ == '__main__':
    main()
