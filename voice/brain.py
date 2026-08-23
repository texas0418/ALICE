#!/usr/bin/env python3
"""The brain: transcribed question in, spoken answer + card directive out.

One Claude call per question. All eleven data sources already live on disk as
small JS files, refreshed by the daemon — so instead of tool round-trips, the
CURRENT data snapshot rides in the user message (~4K tokens) and the static
persona/system block is prompt-cached for an hour. Answers come back as strict
JSON: {"speech": ..., "focus": ...}, where speech may carry the HUD's
[phrase|target] pulse markers.

Test without the microphone:   brain.py "how's traffic to the airport"
"""
import json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _cfg():
    try:
        return json.load(open(os.path.join(ROOT, 'config.local.json')))
    except Exception:
        return {}
CFG = _cfg()
PERSONA = CFG.get('persona', {})
NAME = PERSONA.get('name', 'ALICE')
ACRONYM = PERSONA.get('acronym', 'ATTENTIVE LOCAL INTELLIGENCE & CONCIERGE ENGINE')
OWNER = PERSONA.get('owner', 'the owner')
PLACE = (CFG.get('home') or {}).get('place', 'home')
BRAIN = CFG.get('brain', {})
PROVIDER = BRAIN.get('provider', 'anthropic')       # anthropic | openai
MODEL = BRAIN.get('model', 'claude-opus-5')

DATA_FILES = ['weatherdata', 'mapdata', 'maildata', 'remindersdata',
              'calendardata', 'signalsdata', 'scoutsdata', 'cidata',
              'appstoredata', 'queuedata', 'newsdata', 'tickerdata', 'statusdata',
              'flightdata', 'workdata']

CARDS = {
    'weather':   'temp,cond,hour,precip,sunset,loc',
    'daylight':  'left,sunset,sunrise',
    'calendar':  'today,next,total',
    'flights':   'next,fnum,when',
    'traffic':   'eta,delay,arrive,dist,jam',
    'mail':      'total,a0,a1',
    'reminders': 'overdue,today,total',
    'signals':   'watching,top,run',
    'auction':   'nearby,total,top',
    'acquisition': 'now,total,top',
    'builds':    'failing,top,green',
    'appstore':  'attention,top,live',
    'queues':    'broken,top,waiting',
    'news':      'top,count',
}

SYSTEM = f"""You are {NAME} — {ACRONYM.title()} — the voice of a smart mirror in
{OWNER}'s home ({PLACE}).

Persona: composed, precise, lightly dry, warm underneath — a British woman who
runs the house with quiet authority. Never chatty, never sycophantic. Almost always one or two short sentences; you are heard, not read.
Convert 24h times to spoken 12h form. Say numbers the way a person would.

You receive a snapshot of every data source the mirror has (weather, traffic routes,
mail counts, reminders, calendar+flights, stock signals, auction/acquisition scouts,
CI builds, App Store, content pipelines, headlines, quotes, source freshness).
Answer ONLY from the snapshot. If the needed source is stale or missing, say so
plainly instead of guessing. Traffic mapdata contains routes keyed airport/downtown/
emory with liveMin (current) and freeMin (typical).

Reply with STRICT JSON only, no fences:
{{"speech": "...", "focus": "<card or null>"}}

focus picks the card the mirror should summon — the one whose data you answered
from — or null for chit-chat. Cards and their pulse targets:
""" + '\n'.join(f'  {k}: targets {v}' for k, v in CARDS.items()) + """

In speech, wrap the key data points in [phrase|target] markers using ONLY the
focused card's targets, e.g. "[84 degrees|temp]". At most 3 markers. If focus is
null, use no markers."""


def keychain(account, service):
    r = subprocess.run(['security', 'find-generic-password', '-a', account,
                        '-s', service, '-w'], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def snapshot():
    parts = []
    for name in DATA_FILES:
        try:
            raw = open(os.path.join(ROOT, name + '.js')).read()
            j = raw[raw.index('=') + 1:].rstrip().rstrip(';')
            if name == 'mapdata':      # 450KB of geometry; the brain needs routes only
                d = json.loads(j)
                j = json.dumps({k: {x: v[x] for x in
                                    ('label', 'mi', 'freeMin', 'liveMin')}
                                for k, v in d['routes'].items()},
                               separators=(',', ':'))
            parts.append(f'### {name}\n{j}')
        except Exception:
            parts.append(f'### {name}\nMISSING')
    return '\n'.join(parts)


_client = None
def client():
    """Anthropic client (default provider). Key from the Keychain only."""
    global _client
    if _client is None:
        import anthropic
        key = keychain('jarvis-mirror', 'anthropic-key')
        if not key:
            raise RuntimeError('no anthropic-key in Keychain — run:\n'
                               '  security add-generic-password -U -a jarvis-mirror '
                               '-s anthropic-key -w')
        _client = anthropic.Anthropic(api_key=key)
    return _client


def _parse(out):
    out = re.sub(r'^```(json)?|```$', '', out.strip(), flags=re.M).strip()
    try:
        d = json.loads(out)
    except json.JSONDecodeError:
        d = {'speech': out[:200], 'focus': None}
    if d.get('focus') not in CARDS:
        d['focus'] = None
    return d


def ask_openai(text):
    """Any OpenAI-compatible endpoint: OpenAI itself, Ollama, LM Studio, vLLM...
    base_url + model from config.brain; key from Keychain service openai-key
    (optional — local servers usually need none)."""
    import urllib.request
    base = BRAIN.get('openai_base_url', 'http://localhost:11434/v1').rstrip('/')
    key = keychain('jarvis-mirror', 'openai-key') or 'none'
    body = json.dumps({'model': BRAIN.get('openai_model', 'llama3.1'),
                       'messages': [{'role': 'system', 'content': SYSTEM},
                                    {'role': 'user', 'content':
                                     f'DATA SNAPSHOT:\n{snapshot()}\n\n{OWNER} asks: {text}'}],
                       'max_tokens': 400, 'temperature': 0.4}).encode()
    req = urllib.request.Request(base + '/chat/completions', data=body, headers={
        'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'})
    with urllib.request.urlopen(req, timeout=60) as r:
        j = json.load(r)
    d = _parse(j['choices'][0]['message']['content'])
    u = j.get('usage', {})
    d['usage'] = {'in': u.get('prompt_tokens', 0), 'out': u.get('completion_tokens', 0),
                  'cacheW': 0, 'cacheR': 0}
    return d


def ask(text):
    if PROVIDER == 'openai':
        return ask_openai(text)
    resp = client().messages.create(
        model=MODEL, max_tokens=400,
        system=[{'type': 'text', 'text': SYSTEM,
                 'cache_control': {'type': 'ephemeral', 'ttl': '1h'}}],
        messages=[{'role': 'user',
                   'content': f'DATA SNAPSHOT:\n{snapshot()}\n\n{OWNER} asks: {text}'}],
    )
    if resp.stop_reason == 'refusal':
        return {'speech': "I'd rather not answer that one.", 'focus': None,
                'usage': {}}
    d = _parse(''.join(b.text for b in resp.content if b.type == 'text'))
    u = resp.usage
    d['usage'] = {'in': u.input_tokens, 'out': u.output_tokens,
                  'cacheW': getattr(u, 'cache_creation_input_tokens', 0),
                  'cacheR': getattr(u, 'cache_read_input_tokens', 0)}
    return d


if __name__ == '__main__':
    q = ' '.join(sys.argv[1:]) or "what's the weather"
    import time
    t0 = time.time()
    d = ask(q)
    print(f'[{time.time()-t0:.2f}s]  focus={d["focus"]}')
    print(f'  speech: {d["speech"]}')
    print(f'  usage : {d["usage"]}')
