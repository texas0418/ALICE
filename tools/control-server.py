#!/usr/bin/env python3
"""Phone remote for the mirror.

A deliberately separate server from the mirror itself: the mirror's data server
stays bound to 127.0.0.1, while this listens on the LAN — but it serves ONLY a
control page and a health summary. None of the mirror's data files (mail,
calendar, routes, home coordinates) are reachable here. Every request needs the
token from config.local.json; wrong or missing token gets 403 with no detail.

Commands are written to controldata.js, which the mirror polls every few seconds
— no socket into the page, nothing for a guest on the wifi to probe.

    ~/.venvs/jarvis/bin/python tools/control-server.py     (port 8778)
Phone URL:  http://<mac-ip>:8778/?t=<token>
"""
import json, os, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, 'config.local.json')))
TOKEN = CFG['controlToken']
PORT = 8778

ALLOWED = {'privacy': {'on', 'off'},
           'presence': {'on', 'off'},
           'dim': {'auto', 'full', 'boost', 'night'},
           'palette': {'cyan', 'red'},
           'demo': {'on', 'off'},
           'show': {'weather', 'daylight', 'calendar', 'flights', 'traffic',
                    'mail', 'reminders', 'signals', 'auction', 'acquisition',
                    'builds', 'appstore', 'queues', 'news', 'none'}}

PAGE = """<!doctype html><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>JARVIS Remote</title>
<style>
body{background:#000;color:#7ce2ff;font-family:-apple-system,sans-serif;margin:0;
  padding:18px;letter-spacing:.06em}
h1{font-size:14px;letter-spacing:.3em;color:#d6f6ff;margin:6px 0 18px}
h2{font-size:11px;letter-spacing:.24em;color:#57c6e4;margin:20px 0 8px}
.g{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.g3{grid-template-columns:1fr 1fr 1fr}
button{background:#0a1a22;color:#7ce2ff;border:1px solid #1e4a5c;border-radius:4px;
  padding:14px 6px;font-size:12px;letter-spacing:.12em;text-transform:uppercase}
button:active{background:#123240}
#st{font-size:11px;line-height:1.9;color:#57c6e4;white-space:pre-wrap;margin-top:14px}
.ok{color:#6fe3a8}.bad{color:#ff6a4a}
</style>
<h1>JARVIS REMOTE</h1>
<h2>Brightness</h2><div class=g g3 id=dim></div>
<h2>Show card</h2><div class=g id=show></div>
<h2>Mode</h2><div class=g id=misc></div>
<div id=st>loading status…</div>
<script>
const T=new URLSearchParams(location.search).get('t');
const send=(k,v)=>fetch(`/cmd?t=${T}&k=${k}&v=${v}`,{method:'POST'})
  .then(()=>status());
const B=(parent,k,vals)=>{const p=document.getElementById(parent);
  vals.forEach(v=>{const b=document.createElement('button');
    b.textContent=v;b.onclick=()=>send(k,v);p.appendChild(b)})};
B('dim','dim',['full','boost','night','auto']);
B('show','show',['weather','traffic','flights','calendar','mail','reminders',
  'signals','builds','appstore','queues','news','none']);
B('misc','palette',['cyan','red']); B('misc','demo',['on','off']);
B('misc','privacy',['on','off']);
function status(){fetch(`/status?t=${T}`).then(r=>r.json()).then(d=>{
  document.getElementById('st').innerHTML =
    'DATA: '+d.sources.map(s=>`<span class="${s.stale||s.missing?'bad':'ok'}">${s.name}</span>`).join(' · ')
    +'\\nchecked '+d.checked+' · last command: '+(d.lastCmd||'—');
}).catch(()=>{})}
status(); setInterval(status,10000);
</script>"""


class H(BaseHTTPRequestHandler):
    def _deny(self):
        self.send_response(403)
        self.end_headers()

    def _ok(self, body, ctype='application/json'):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authed(self, q):
        return q.get('t', [''])[0] == TOKEN

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if not self._authed(q):
            return self._deny()
        if u.path == '/':
            return self._ok(PAGE, 'text/html; charset=utf-8')
        if u.path == '/status':
            try:
                raw = open(os.path.join(ROOT, 'statusdata.js')).read()
                st = json.loads(raw[raw.index('=') + 1:].rstrip().rstrip(';'))
            except Exception:
                st = {'sources': [], 'checked': '—'}
            st['lastCmd'] = getattr(H, 'last_cmd', None)
            return self._ok(json.dumps(st))
        self._deny()

    def do_POST(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if not self._authed(q) or u.path != '/cmd':
            return self._deny()
        k = q.get('k', [''])[0]
        v = q.get('v', [''])[0]
        if k not in ALLOWED or v not in ALLOWED[k]:
            return self._deny()
        cmd = {'k': k, 'v': v, 'seq': int(time.time() * 1000)}
        tmp = os.path.join(ROOT, 'controldata.js.tmp')
        open(tmp, 'w').write('const CONTROL=' + json.dumps(cmd) + ';\n')
        os.replace(tmp, os.path.join(ROOT, 'controldata.js'))
        H.last_cmd = f'{k}={v}'
        print(f'  cmd from {self.client_address[0]}: {k}={v}')
        self._ok('{"ok":true}')

    def log_message(self, *a):
        pass


if __name__ == '__main__':
    print(f'  control on 0.0.0.0:{PORT}  (token required on every request)')
    ThreadingHTTPServer(('0.0.0.0', PORT), H).serve_forever()
