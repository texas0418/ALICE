#!/usr/bin/env python3
"""ALICE voice service — the half that owns the microphone.

The browser is a display, not an application: it never touches audio, never holds a
key, never decides anything. This process captures the mic, runs the wake word, and
pushes state to the HUD over a websocket. That split is why API keys can live here
and not in a page anyone standing at the mirror could open.

PHASE A  mic level -> the spoke burst                        [done]
PHASE B  "hey jarvis" -> wake, capture the utterance         [done]
PHASE C  faster-whisper transcription                        [done]
PHASE D  Claude brain + spoken replies (say/Daniel)          [done]

    ~/.venvs/jarvis/bin/python voice/service.py
"""
import asyncio, json, math, queue, subprocess, sys, threading, time
import numpy as np
import sounddevice as sd
import websockets
from openwakeword.model import Model
from faster_whisper import WhisperModel

import brain, tts

HOST, PORT   = '127.0.0.1', 8765
SR           = 16000        # whisper's native rate; resampling later would be waste
BLOCK        = 1280         # 80 ms — exactly one wake-word frame
SEND_HZ      = 30
FLOOR_DB     = -62.0
CEIL_DB      = -14.0

import json as _json, os as _os
try:
    _CFG = _json.load(open(_os.path.join(_os.path.dirname(_os.path.dirname(
        _os.path.abspath(__file__))), 'config.local.json')))
except Exception:
    _CFG = {}
_PERSONA = _CFG.get('persona', {})
WAKE_MODEL   = _PERSONA.get('wake_model', 'hey_jarvis')
WAKE_THRESH  = 0.55
WAKE_COOLDOWN= 2.0          # seconds after a hit before we listen for it again

SPEECH_ON    = 0.18         # level above this counts as speech
SILENCE_END  = 0.75         # this much quiet ends the utterance
WAIT_SPEECH  = 3.0          # if nothing is said after waking, stand down
MAX_UTTER    = 12.0

# base.en over small.en: 0.58s vs 1.64s per utterance on this chip, with identical
# accuracy on command-length speech. Its cost is near-constant — dominated by fixed
# overhead rather than audio length — so long questions cost no more than short ones.
STT_MODEL    = 'base.en'
STT_THREADS  = 6            # of 8; leaving headroom for the HUD's own rendering
TTS_VOICE    = _PERSONA.get('voice', 'Flo')   # `say` voice name, or a Piper .onnx path
TTS_BACKEND  = _PERSONA.get('tts', 'auto')    # say | piper | none | auto
MARK_RE      = __import__('re').compile(r'\[([^\]|]+)\|[^\]]+\]')

clients: set = set()
level = 0.0
peak = 0.0
events: "queue.Queue" = queue.Queue()
frames: "queue.Queue" = queue.Queue(maxsize=64)
state = 'IDLE'


def emit(**msg):
    events.put(json.dumps(msg))


def on_audio(indata, n, t, status):
    """PortAudio callback. Stays cheap: level only, then hand the frame off."""
    global level, peak
    x = indata[:, 0]
    rms = float(np.sqrt(np.mean(x * x)) + 1e-9)
    db = 20.0 * math.log10(rms)
    v = (db - FLOOR_DB) / (CEIL_DB - FLOOR_DB)
    v = 0.0 if v < 0 else 1.0 if v > 1 else v
    # fast attack, slow release: speech should snap the rings open and ease shut,
    # which reads as "listening" rather than "metering"
    level = v if v > level else level + (v - level) * 0.22
    peak = max(peak * 0.94, level)
    try:
        frames.put_nowait(x.copy())
    except queue.Full:
        pass


def listener():
    """Wake word + endpointing, off the audio thread."""
    global state
    model = Model(wakeword_models=[WAKE_MODEL], inference_framework='onnx')
    t0 = time.time()
    stt = WhisperModel(STT_MODEL, device='cpu', compute_type='int8',
                       cpu_threads=STT_THREADS)
    print(f'  whisper {STT_MODEL} loaded in {time.time()-t0:.1f}s')
    print('  ready — say "hey jarvis"\n')
    last_hit = 0.0
    utter, waking_at, speech_seen, quiet_since = [], 0.0, False, 0.0

    while True:
        x = frames.get()
        now = time.time()

        if state == 'IDLE':
            pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
            score = float(model.predict(pcm).get(WAKE_MODEL, 0.0))
            if score >= WAKE_THRESH and now - last_hit > WAKE_COOLDOWN:
                last_hit = now
                state = 'LISTENING'
                utter, waking_at, speech_seen, quiet_since = [], now, False, 0.0
                print(f'  wake  ({score:.2f})')
                emit(t='state', s='WAKE', sub='WAKE WORD DETECTED')
                emit(t='state', s='LISTENING', sub='SPEAK NOW')
            continue

        # LISTENING
        utter.append(x)
        if level >= SPEECH_ON:
            speech_seen, quiet_since = True, 0.0
        elif speech_seen:
            quiet_since = quiet_since or now

        dur = len(utter) * BLOCK / SR
        done = (
            (speech_seen and quiet_since and now - quiet_since >= SILENCE_END)
            or dur >= MAX_UTTER
            or (not speech_seen and now - waking_at >= WAIT_SPEECH)
        )
        if not done:
            continue

        state = 'IDLE'
        if not speech_seen:
            print('  stood down (nothing said)')
            emit(t='state', s='IDLE')
            continue

        audio = np.concatenate(utter)
        secs = len(audio) / SR
        print(f'  captured {secs:.1f}s')
        emit(t='state', s='THINKING', sub='TRANSCRIBING')

        t0 = time.time()
        segs, _ = stt.transcribe(audio, language='en', beam_size=1,
                                 vad_filter=False, condition_on_previous_text=False)
        text = ' '.join(s.text for s in segs).strip()
        took = time.time() - t0
        print(f'  "{text}"   [{took:.2f}s, {secs/max(took,1e-3):.1f}x rt]')

        if not text:
            emit(t='state', s='IDLE')
            continue

        emit(t='heard', text=text, secs=round(secs, 1), took=round(took, 2))

        if brain.keychain('jarvis-mirror', 'anthropic-key'):
            try:
                t1 = time.time()
                d = brain.ask(text)
                print(f'  brain [{time.time()-t1:.2f}s] focus={d["focus"]} '
                      f'cacheR={d["usage"].get("cacheR", 0)}')
            except Exception as ex:
                print(f'  brain FAILED: {type(ex).__name__}: {ex}')
                d = {'speech': 'I could not reach the brain just now.', 'focus': None}
        else:
            # Not configured yet, and honest about it — this is deliberate until
            # Simon sets the key on land, not a failure.
            d = {'speech': f'I heard: {text}. My reasoning is not connected yet.',
                 'focus': None}

        # The HUD runs the full choreography (rolodex spin, card, typed markers);
        # speech goes out through the Mac's own voice in parallel.
        emit(t='answer', focus=d['focus'], speech=d['speech'])
        spoken = MARK_RE.sub(r'\1', d['speech'])
        emit(t='state', s='SPEAKING')
        try:
            if tts.speak(spoken, TTS_VOICE, TTS_BACKEND) == 'none':
                time.sleep(max(1.6, len(spoken) * 0.05))   # silent: pace the HUD
        except Exception:
            time.sleep(max(1.6, len(spoken) * 0.05))
        emit(t='state', s='IDLE')


async def pump():
    period = 1.0 / SEND_HZ
    while True:
        out = [json.dumps({'t': 'level', 'v': round(level, 4), 'p': round(peak, 4)})]
        while True:
            try:
                out.append(events.get_nowait())
            except queue.Empty:
                break
        if clients:
            for m in out:
                await asyncio.gather(*(c.send(m) for c in list(clients)),
                                     return_exceptions=True)
        await asyncio.sleep(period)


async def handler(ws):
    clients.add(ws)
    await ws.send(json.dumps({'t': 'hello', 'sr': SR, 'phase': 'D'}))
    print(f'  HUD connected ({len(clients)})')
    try:
        async for _ in ws:
            pass
    except Exception:
        pass
    finally:
        clients.discard(ws)
        print(f'  HUD disconnected ({len(clients)} left)')


async def main():
    dev = None
    for i, a in enumerate(sys.argv):
        if a == '--device' and i + 1 < len(sys.argv):
            dev = int(sys.argv[i + 1])
    print(f'  mic: {sd.query_devices(dev if dev is not None else sd.default.device[0])["name"]}')
    print(f'  ws:  ws://{HOST}:{PORT}')
    threading.Thread(target=listener, daemon=True).start()
    with sd.InputStream(samplerate=SR, blocksize=BLOCK, channels=1,
                        dtype='float32', callback=on_audio, device=dev):
        async with websockets.serve(handler, HOST, PORT):
            await pump()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\n  stopped')
