"""Remote access + notification server for ALICE.

Features:
 - Command injection (/command)
 - Conversation poll (/stream)
 - Real-time SSE (/events)
 - Web Push (Android) with VAPID (/vapid, /subscribe, /pushnotify)
 - Discord DM fallback (env: DISCORD_BOT_TOKEN, DISCORD_DM_USER_ID)
 - Simple client page (/client) registering service worker (/sw.js) + manifest
"""
from __future__ import annotations

import os, json, threading, queue, secrets, time, base64, sys
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional

import sms_notifier  # local module; should exist already

print(f"[Remote][Env] Python executable: {sys.executable}")
print(f"[Remote][Env] sys.path[0:3]: {sys.path[:3]}")

try:
    from pywebpush import webpush, WebPushException  # type: ignore
except Exception:  # degrade gracefully if not installed
    webpush = None  # type: ignore
    class WebPushException(Exception):
        pass
try:
    import requests  # type: ignore
except Exception:
    requests = None  # type: ignore

try:
    import cryptography  # type: ignore
except Exception:
    print("[Remote][Env] 'cryptography' not importable in this interpreter. If you expected push keys, install with:")
    print(f"[Remote][Env]   {sys.executable} -m pip install cryptography pywebpush requests")

_incoming_commands: "queue.Queue[str]" = queue.Queue()
_events_lock = threading.Lock()
_events: list[dict] = []

# Remote session tracking for audio responses
_remote_sessions: dict[str, dict] = {}  # session_id -> {'last_command': str, 'audio_file': str, 'timestamp': float}
_sessions_lock = threading.Lock()
_last_remote_session: str | None = None

def add_event(kind: str, **data):
    evt = {"kind": kind, "ts": time.time(), **data}
    with _events_lock:
        _events.append(evt)
        if len(_events) > 500:
            del _events[:-500]
    return evt

def track_remote_session(session_id: str, command: str):
    """Track a remote session for audio response delivery."""
    global _last_remote_session
    with _sessions_lock:
        _remote_sessions[session_id] = {
            'last_command': command,
            'audio_file': None,
            'timestamp': time.time()
        }
        _last_remote_session = session_id
        # Clean up old sessions (older than 5 minutes)
        cutoff = time.time() - 300
        _remote_sessions = {k: v for k, v in _remote_sessions.items() if v['timestamp'] > cutoff}

def get_last_remote_session() -> str | None:
    """Get the last remote session ID."""
    with _sessions_lock:
        return _last_remote_session

def clear_last_remote_session():
    """Clear the last remote session."""
    global _last_remote_session
    with _sessions_lock:
        _last_remote_session = None

def track_remote_session(session_id: str, command: str):
    """Track a remote session for audio response delivery."""
    global _remote_sessions
    with _sessions_lock:
        _remote_sessions[session_id] = {
            'last_command': command,
            'audio_file': None,
            'timestamp': time.time()
        }
        # Clean up old sessions (older than 5 minutes)
        cutoff = time.time() - 300
        _remote_sessions = {k: v for k, v in _remote_sessions.items() if v['timestamp'] > cutoff}

def get_remote_session(session_id: str) -> dict | None:
    """Get remote session info."""
    with _sessions_lock:
        return _remote_sessions.get(session_id)

def set_session_audio(session_id: str, audio_file: str):
    """Associate an audio file with a remote session."""
    with _sessions_lock:
        if session_id in _remote_sessions:
            _remote_sessions[session_id]['audio_file'] = audio_file

def speak_to_file(text: str, filename: str) -> bool:
    """Generate TTS audio and save to file for remote playback."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        
        # Configure voice (use same as ALICE)
        try:
            with open(os.path.join(os.path.dirname(__file__), "config.txt"), 'r') as f:
                ai_model = f.read().strip().lower()
            if ai_model == "alice":
                engine.setProperty('voice', r'HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices\Tokens\TTS_MS_EN-GB_HAZEL_11.0')
            else:  # virgil, vrgl
                engine.setProperty('voice', r'HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices\Tokens\TTS_MS_EN-US_DAVID_11.0')
        except Exception:
            # Default to David voice
            engine.setProperty('voice', r'HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices\Tokens\TTS_MS_EN-US_DAVID_11.0')
        
        engine.save_to_file(text, filename)
        engine.runAndWait()
        return True
    except Exception as e:
        print(f"[Remote] TTS to file failed: {e}")
        return False

def generate_audio_response(session_id: str, response_text: str):
    """Generate audio file for a remote session response."""
    if not session_id or not response_text:
        return
    
    try:
        # Create audio directory if it doesn't exist
        audio_dir = os.path.join(os.path.dirname(__file__), "audio_responses")
        os.makedirs(audio_dir, exist_ok=True)
        
        # Generate unique filename
        audio_file = os.path.join(audio_dir, f"response_{session_id}_{int(time.time())}.wav")
        
        # Generate audio
        if speak_to_file(response_text, audio_file):
            set_session_audio(session_id, audio_file)
            print(f"[Remote] Generated audio response for session {session_id}: {audio_file}")
        else:
            print(f"[Remote] Failed to generate audio for session {session_id}")
    except Exception as e:
        print(f"[Remote] Audio generation error: {e}")
        import traceback
        traceback.print_exc()

# --- VAPID / Web Push state ---
_VAPID_PATH = os.path.join(os.path.dirname(__file__), "vapid_keys.json")
_SUBS_PATH = os.path.join(os.path.dirname(__file__), "push_subscriptions.json")
_VAPID: Optional[dict] = None
_SUBS: list[dict] = []
_VAPID_LOCK = threading.Lock()

def _load_vapid(force: bool = False):
    """Load or (re)generate VAPID keys."""
    global _VAPID
    with _VAPID_LOCK:
        if not force and _VAPID is not None:
            return _VAPID
        if not force and os.path.exists(_VAPID_PATH):
            try:
                with open(_VAPID_PATH,'r') as f:
                    _VAPID = json.load(f)
            except Exception:
                _VAPID = None
        need_gen = force or (not _VAPID) or (not _VAPID.get('private_key_pem'))
        if need_gen:
            try:
                from cryptography.hazmat.primitives.asymmetric import ec
                from cryptography.hazmat.primitives import serialization
                priv = ec.generate_private_key(ec.SECP256R1())
                pem = priv.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption()
                ).decode()
                _VAPID = {"private_key_pem": pem}
                with open(_VAPID_PATH,'w') as f:
                    json.dump(_VAPID, f)
                print("[Remote][Push] Generated VAPID keys")
            except Exception as e:
                import sys, traceback
                print(f"[Remote][Push] VAPID generation failed: {e}")
                print(f"[Remote][Push] Python executable: {sys.executable}")
                print(f"[Remote][Push] sys.path (first 5): {sys.path[:5]}")
                print(f"[Remote][Push] Working dir: {os.getcwd()}")
                print(f"[Remote][Push] Exists cryptography module? {'cryptography' in sys.modules}")
                traceback.print_exc()
                _VAPID = {}
        return _VAPID

def _public_key_b64url(regen_if_empty: bool = True) -> str:
    _load_vapid()
    if not _VAPID or not _VAPID.get('private_key_pem'):
        if regen_if_empty:
            _load_vapid(force=True)
        if not _VAPID or not _VAPID.get('private_key_pem'):
            return ""
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend
        priv = serialization.load_pem_private_key(
            _VAPID['private_key_pem'].encode(), password=None, backend=default_backend()
        )
        pub = priv.public_key()
        raw = pub.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint
        )
        import base64 as _b64
        return _b64.urlsafe_b64encode(raw).decode().rstrip('=')
    except Exception as e:
        print(f"[Remote][Push] Public key derive failed: {e}")
        return ""

def _load_subs():
    global _SUBS
    if os.path.exists(_SUBS_PATH):
        try:
            with open(_SUBS_PATH,'r') as f:
                _SUBS = json.load(f)
        except Exception:
            _SUBS = []

def _save_subs():
    try:
        with open(_SUBS_PATH,'w') as f:
            json.dump(_SUBS, f)
    except Exception:
        pass

def send_web_push_all(title: str, body: str):
    if not webpush:
        return 0
    _load_vapid()
    if not _VAPID or not _VAPID.get('private_key_pem'):
        return 0
    sent = 0
    dead = []
    for i, sub in enumerate(list(_SUBS)):
        ep = sub.get('endpoint','?')
        print(f"[Remote][Push] Attempt -> {ep[:60]}")
        try:
            webpush(
                subscription_info=sub,
                data=json.dumps({"title": title, "body": body}),
                vapid_private_key=_VAPID['private_key_pem'],
                vapid_claims={"sub": "mailto:alice@example.invalid"}
            )
            sent += 1
            print(f"[Remote][Push] OK    <- {ep[:60]}")
        except WebPushException as e:
            print(f"[Remote][Push] DEAD  <- {ep[:60]} ({e})")
            dead.append(i)
        except Exception as e:
            print(f"[Remote][Push] ERR   <- {ep[:60]} ({e})")
    if dead:
        for idx in reversed(dead):
            try:
                del _SUBS[idx]
            except Exception:
                pass
        _save_subs()
    if sent:
        print(f"[Remote][Push] Sent {sent} push notifications")
    return sent

def _discord_dm_async(bot_token: str, user_id: str, content: str):
    if not requests:
        return
    def _worker():
        try:
            r = requests.post(
                'https://discord.com/api/v10/users/@me/channels',
                headers={'Authorization': f'Bot {bot_token}','Content-Type':'application/json'},
                json={'recipient_id': user_id}, timeout=10
            )
            if r.status_code >= 300:
                return
            channel_id = r.json().get('id')
            if not channel_id:
                return
            requests.post(
                f'https://discord.com/api/v10/channels/{channel_id}/messages',
                headers={'Authorization': f'Bot {bot_token}','Content-Type':'application/json'},
                json={'content': content[:1900]}, timeout=10
            )
        except Exception:
            pass
    threading.Thread(target=_worker, daemon=True).start()

_load_vapid()
_load_subs()

def notify(text: str, kind: str = "vrgl", sms: bool = False,
           discord_channel: str | None = None,
           discord_message: str | None = None,
           push: bool = True) -> dict:
    evt = add_event(kind, text=text)
    if sms:
        try:
            ok, info = sms_notifier.send_sms(text)
            if not ok:
                print(f"[Remote][Notify] SMS failed: {info}")
        except Exception as e:
            print(f"[Remote][Notify] SMS exception: {e}")
    if discord_channel:
        try:
            import discord_notifier  # type: ignore
            ok, info = discord_notifier.send_discord_message(discord_channel, discord_message or text)
            if not ok:
                print(f"[Remote][Notify] Discord channel failed: {info}")
        except Exception as e:
            print(f"[Remote][Notify] Discord channel exception: {e}")
    else:
        bot_token = os.environ.get('DISCORD_BOT_TOKEN')
        dm_user = os.environ.get('DISCORD_DM_USER_ID')
        if bot_token and dm_user:
            _discord_dm_async(bot_token, dm_user, text)
    if push:
        try:
            send_web_push_all(kind.upper(), text)
        except Exception as e:
            print(f"[Remote][Notify] push error: {e}")
    return evt

SERVICE_WORKER_JS = """self.addEventListener('install',e=>self.skipWaiting());
self.addEventListener('activate',e=>clients.claim());
function show(d){const t=d.title||'ALICE';const o={body:d.body||'',tag:'alice-push',renotify:true,vibrate:[200,100,200]};try{self.registration.showNotification(t,o);}catch(e){}}
self.addEventListener('message',e=>{if(e.data&&e.data.__notify) show(e.data.__notify);});
self.addEventListener('push',e=>{try{if(!e.data)return;let data;try{data=e.data.json();}catch(_){data={body:e.data.text()};}show({title:data.title||'ALICE',body:data.body||''});}catch(err){}});
"""

MANIFEST_JSON = {
    "name": "ALICE Remote",
    "short_name": "ALICE",
    "start_url": "/client",
    "display": "standalone",
    "background_color": "#111111",
    "theme_color": "#111111",
    "icons": []
}

def _token_path():
    return os.path.join(os.path.dirname(__file__), "remote_token.txt")


def _maybe_debug_log_request(handler: 'BaseHTTPRequestHandler', note: str = ''):
    """If REMOTE_DEBUG=1, print the incoming request's method, path, headers and small body (safe-size).

    This helper is intentionally opt-in via env var to avoid noisy logs in normal use.
    """
    if os.environ.get('REMOTE_DEBUG') not in ('1', 'true', 'True'):
        return
    # Print a compact header summary and small body preview
    meth = handler.command
    path = handler.path
    print(f"[Remote][DEBUG] {note} -> {meth} {path}")
    # Print headers
    for k, v in handler.headers.items():
        # avoid printing very long header values
        short = v if len(v) < 400 else (v[:396] + '...')
        print(f"[Remote][DEBUG]   H: {k}: {short}")
    # Try to read small body without consuming it for later reads
    try:
        length = int(handler.headers.get('Content-Length') or 0)
    except Exception:
        length = 0
    if length > 0:
        # read up to 2048 bytes for logging
        toread = min(length, 2048)
        body = handler.rfile.read(toread)
        try:
            s = body.decode(errors='replace')
        except Exception:
            s = repr(body)
        if len(s) > 1000:
            s = s[:1000] + '...'
        print(f"[Remote][DEBUG]   Body (first {toread} bytes): {s}")
        # If we didn't read the full body, and the remainder will be read later by existing code,
        # we need to restore the unread bytes onto the rfile so later reads still work. We'll
        # reconstruct rfile by concatenating the unread portion back. This is somewhat hacky but
        # acceptable for small debug sessions. Only perform the restore when we've read less than
        # the Content-Length (so there is remainder to reattach).
        if toread < length:
            try:
                remainder = handler.rfile.read(length - toread)
                # Rebuild a simple BytesIO and replace handler.rfile
                import io
                handler.rfile = io.BytesIO(body + remainder)
            except Exception:
                # If restore fails, we can't do much; continue (may break later reads)
                pass


def get_token() -> str:
    p = _token_path()
    if not os.path.exists(p):
        tok = secrets.token_hex(16)
        with open(p,'w') as f:
            f.write(tok)
        return tok
    with open(p,'r') as f:
        return f.read().strip()

def has_commands():
    return not _incoming_commands.empty()

def pop_command() -> Optional[tuple[str, str | None]]:
    try:
        return _incoming_commands.get_nowait()
    except Exception:
        return None

class _RemoteHandler(BaseHTTPRequestHandler):
    server_version = "ALICERemote/0.4"

    def log_message(self, *a, **k):
        return

    def _fail(self, code, msg):
        self.send_response(code)
        self.send_header('Content-Type','application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"ok": False, "error": msg}).encode())

    def _ok(self, payload: dict):
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True, **payload}).encode())

    def _auth(self, supplied: Optional[str]):
        """Authenticate a request.

        Order of checks:
        - Authorization header (Bearer token or Basic auth if REMOTE_BASIC_USER/PASS set)
        - X-Access-Token / X-Token header
        - supplied token parameter (from query/body)
        """
        try:
            # 1) Check Authorization header
            auth = self.headers.get('Authorization')
            if auth:
                auth = auth.strip()
                if auth.lower().startswith('bearer '):
                    token = auth.split(None, 1)[1].strip()
                    return token == get_token()
                if auth.lower().startswith('basic '):
                    # Optional Basic auth support: REMOTE_BASIC_USER and REMOTE_BASIC_PASS
                    cred_b64 = auth.split(None, 1)[1].strip()
                    try:
                        cred = base64.b64decode(cred_b64).decode(errors='ignore')
                        user, pwd = cred.split(':', 1)
                        env_user = os.environ.get('REMOTE_BASIC_USER')
                        env_pass = os.environ.get('REMOTE_BASIC_PASS')
                        if env_user and env_pass and user == env_user and pwd == env_pass:
                            return True
                    except Exception:
                        pass

            # 2) Check X-Access-Token headers
            xh = self.headers.get('X-Access-Token') or self.headers.get('X-Token')
            if xh:
                if xh.strip() == get_token():
                    return True

            # 3) Fallback to supplied token (query param or json body)
            if supplied and supplied == get_token():
                return True

            return False
        except Exception:
            return False

    def _read_json(self):
        try:
            ln = int(self.headers.get('Content-Length',0))
        except Exception:
            ln = 0
        if ln <= 0:
            return {}
        raw = self.rfile.read(ln)
        try:
            return json.loads(raw.decode())
        except Exception:
            return {}

    def _safe_write(self, chunk: bytes) -> bool:
        try:
            self.wfile.write(chunk)
            return True
        except Exception:
            return False

    def do_GET(self):
        p = urlparse(self.path)
        # Optional debug logging of incoming request (set REMOTE_DEBUG=1 to enable)
        _maybe_debug_log_request(self, 'do_GET')
        if p.path == '/ping':
            return self._ok({"time": time.time()})
        if p.path.startswith('/audio/'):
            # Serve audio response for a session
            session_id = p.path[len('/audio/'):]
            session_info = get_remote_session(session_id)
            if not session_info or not session_info.get('audio_file'):
                return self._fail(404, 'audio not found')
            
            audio_file = session_info['audio_file']
            if not os.path.exists(audio_file):
                return self._fail(404, 'audio file missing')
            
            try:
                with open(audio_file, 'rb') as f:
                    audio_data = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'audio/wav')
                self.send_header('Content-Length', str(len(audio_data)))
                self.end_headers()
                self.wfile.write(audio_data)
                # Clean up the audio file after serving
                try:
                    os.remove(audio_file)
                except Exception:
                    pass
                return
            except Exception as e:
                return self._fail(500, f'audio error: {e}')
        if p.path == '/media/aiOpen.mp3':
            # Serve the aiOpen mp3 file (whitelisted only) from assets/sounds
            fpath = os.path.join(os.path.dirname(__file__), 'assets', 'sounds', 'aiOpen.mp3')
            if not os.path.exists(fpath):
                return self._fail(404,'audio missing')
            try:
                with open(fpath,'rb') as f:
                    data = f.read()
                self.send_response(200)
                self.send_header('Content-Type','audio/mpeg')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                print(f"[Remote][Media] Error serving aiOpen.mp3: {e}")
                return self._fail(500,'serve error')
            return
        if p.path == '/token':
            if self.client_address[0] not in ('127.0.0.1','::1'):
                return self._fail(403,'local only')
            return self._ok({"token": get_token()})
        if p.path == '/vapid':
            pub = _public_key_b64url()
            if not pub:
                print("[Remote][Push] /vapid requested but key empty (needs cryptography/pywebpush & HTTPS context)")
            return self._ok({"public_key": pub})
        if p.path == '/stream':
            qs = parse_qs(p.query)
            tok = (qs.get('token') or [None])[0]
            if not self._auth(tok):
                return self._fail(401,'unauthorized')
            since_raw = (qs.get('since') or ['0'])[0]
            try:
                since = int(since_raw)
            except ValueError:
                since = 0
            try:
                import VRGL as ALICE  # type: ignore
                history = ALICE.conversation_history
            except Exception:
                history = []
            new = history[since:]
            return self._ok({"messages": new, "next_index": since + len(new)})
        if p.path == '/events':
            qs = parse_qs(p.query)
            tok = (qs.get('token') or [None])[0]
            if not self._auth(tok):
                return self._fail(401,'unauthorized')
            self.send_response(200)
            self.send_header('Content-Type','text/event-stream')
            self.send_header('Cache-Control','no-cache')
            self.send_header('Connection','keep-alive')
            self.end_headers()
            try:
                import VRGL as ALICE  # type: ignore
                history = ALICE.conversation_history
            except Exception:
                history = []
            msg_index = len(history)
            evt_index = 0
            heartbeat = time.time()
            try:
                while True:
                    try:
                        import VRGL as ALICE  # type: ignore
                        history = ALICE.conversation_history
                    except Exception:
                        history = []
                    if msg_index < len(history):
                        new_msgs = history[msg_index:]
                        msg_index = len(history)
                    else:
                        new_msgs = []
                    for m in new_msgs:
                        if not self._safe_write(f"data: {json.dumps(m)}\n\n".encode()):
                            raise ConnectionAbortedError
                    with _events_lock:
                        if evt_index < len(_events):
                            new_events = _events[evt_index:]
                            evt_index = len(_events)
                        else:
                            new_events = []
                    for ev in new_events:
                        if not self._safe_write(f"data: {json.dumps({'event': ev})}\n\n".encode()):
                            raise ConnectionAbortedError
                    if new_msgs or new_events:
                        try:
                            self.wfile.flush()
                        except Exception:
                            raise ConnectionAbortedError
                    if time.time() - heartbeat > 20:
                        if not self._safe_write(b": ping\n\n"):
                            raise ConnectionAbortedError
                        try:
                            self.wfile.flush()
                        except Exception:
                            raise ConnectionAbortedError
                        heartbeat = time.time()
                    time.sleep(1)
            except Exception:
                return
            return
        if p.path == '/sw.js':
            self.send_response(200)
            self.send_header('Content-Type','application/javascript')
            self.end_headers()
            self.wfile.write(SERVICE_WORKER_JS.encode())
            return
        if p.path == '/manifest.json':
            self.send_response(200)
            self.send_header('Content-Type','application/manifest+json')
            self.end_headers()
            self.wfile.write(json.dumps(MANIFEST_JSON).encode())
            return
        if p.path == '/client':
            qs = parse_qs(p.query)
            token_param = (qs.get('token') or [''])[0]
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.end_headers()
            beep_data = 'data:audio/wav;base64,' + base64.b64encode(
                b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00" +
                b"\x01\x00\x01\x00D\xac\x00\x00D\xac\x00\x00" +
                b"\x01\x00\x08\x00data\x00\x00\x00\x00"
            ).decode()
            html = (
                "<!DOCTYPE html><html><head><meta charset='utf-8'><title>ALICE Remote</title>"
                "<link rel='manifest' href='/manifest.json'><meta name='viewport' content='width=device-width,initial-scale=1,user-scalable=no'>"
                "<style>body{font-family:Arial;background:#111;color:#eee;margin:1rem;}button{margin:.25rem;padding:.4rem .7rem;border-radius:4px;border:none;background:#333;color:#eee;}button:hover{background:#555;}button:active{background:#777;}button:disabled{background:#666;color:#999;}#log{white-space:pre-wrap;font-size:.8rem;max-height:60vh;overflow:auto;background:#000;border:1px solid #333;padding:.5rem;border-radius:4px;} .note{background:#222;margin:.25rem 0;padding:.35rem;border-left:4px solid #4caf50;border-radius:0 4px 4px 0;} .err{border-left-color:#e74c3c;} .evt{border-left-color:#3498db;} .voice{background:#2a2a4a;border-left-color:#9b59b6;} #voiceStatus{color:#9b59b6;font-weight:bold;} .listening{background:#4a2a2a;border-left-color:#e67e22;} .warning{background:#4a4a2a;border-left-color:#f39c12;} .success{background:#2a4a2a;border-left-color:#27ae60;} @media (max-width: 600px){body{margin:.5rem;}button{padding:.6rem 1rem;font-size:1rem;}#log{max-height:50vh;}}</style></head><body>"
                "<h3>ALICE Remote Client</h3><div>Status: <span id='status'>init</span></div>"
                "<div id='voiceStatus'>Voice: Ready</div>"
                "<div id='micStatus'>Microphone: <span id='micPerm'>Unknown</span></div>"
                "<div id='audioStatus'>Audio: <span id='audioPerm'>Not Enabled</span></div>"
                "<p style='font-size:.7rem;opacity:.7'>HTTPS required for microphone/audio. Enable permissions then subscribe.</p>"
                f"<audio id='beep' src='{beep_data}' preload='auto'></audio>"
                "<div><button id='perm'>Notification Permission</button><button id='micPermBtn'>🎙️ Microphone Permission</button><button id='audioEnable'>🔊 Enable Audio</button><button id='pushEnable'>Enable Push</button><button id='pushTest'>Server Push Test</button><button id='diag'>🔍 Diagnostics</button><button id='playOpen'>Play aiOpen</button><button id='test'>Local Test</button></div>"
                "<div><button id='voiceStart'>🎤 Start Voice</button><button id='voiceStop' disabled>⏹️ Stop Voice</button></div>"
                "<div style='margin:.5rem 0;'><input type='text' id='textCommand' placeholder='Type command here...' style='width:70%;padding:.4rem;border:1px solid #555;border-radius:4px;background:#222;color:#eee;'><button id='sendText'>📤 Send</button></div>"
                "<div id='mobileHelp' style='background:#333;padding:1rem;border-radius:4px;margin:.5rem 0;display:none;'><h4>📱 Mobile Setup Help</h4><ol style='margin:0;padding-left:1.5rem;'><li>Make sure you're using <strong>HTTPS</strong> (required for microphone)</li><li>Tap '🎙️ Microphone Permission' and allow access</li><li>Tap '🎤 Start Voice' to begin listening</li><li>Say 'Hey Alice' or 'Hey Virgil' + your command</li><li>Tap '🔊 Enable Audio' to allow response playback</li></ol><p style='margin:.5rem 0 0 0;font-size:.8rem;color:#ff6b6b;'>⚠️ Mobile browsers require HTTPS and user interaction for audio/microphone access.</p></div>"
                "<div id='log'></div><script>(function(){if('serviceWorker' in navigator){navigator.serviceWorker.register('/sw.js').catch(()=>{});}"
                f"const token={json.dumps(token_param)};const statusEl=document.getElementById('status');const logEl=document.getElementById('log');const beep=document.getElementById('beep');const voiceStatus=document.getElementById('voiceStatus');const micStatusEl=document.getElementById('micPerm');const audioStatusEl=document.getElementById('audioPerm');const mobileHelp=document.getElementById('mobileHelp');"
                "let recognition=null;let isListening=false;let wakeWords=['hey alice','hey virgil','hey vergil','alice','virgil','vergil','ok alice','ok virgil','ok vergil'];let micPermission='unknown';let audioContext=null;let audioEnabled=false;"
                "function log(m,c){const d=document.createElement('div');d.className='note '+(c||'');d.textContent=new Date().toLocaleTimeString()+' - '+m;logEl.prepend(d);}"
                "function fetchWithAuth(path, opts){opts=opts||{};opts.method=opts.method||'GET';opts.headers=opts.headers||{};if(opts.method!=='GET' && !opts.headers['Content-Type']){opts.headers['Content-Type']='application/json';}if(token){opts.headers['Authorization']='Bearer '+token;}return fetch(path,opts);}"
                "function updateMicStatus(){try{if(navigator.permissions&&navigator.permissions.query){navigator.permissions.query({name:'microphone'}).then(r=>{micPermission=r.state;micStatusEl.textContent=r.state.charAt(0).toUpperCase()+r.state.slice(1);micStatusEl.style.color=r.state==='granted'?'#4caf50':r.state==='denied'?'#e74c3c':'#f39c12';}).catch(()=>{micStatusEl.textContent='API not supported';});}else{micStatusEl.textContent='Check not supported';}\n                    // Update audio status UI as well\n                    try{audioStatusEl.textContent = audioEnabled ? 'Enabled' : 'Not Enabled'; audioStatusEl.style.color = audioEnabled ? '#4caf50' : '#f39c12';}catch(_e){}\n                }catch(e){micStatusEl.textContent='Error';log('updateMicStatus error: '+e,'err');}}"
                "function notify(title,body){try{if(Notification.permission==='granted'){new Notification(title,{body});}else if(navigator.serviceWorker.controller){navigator.serviceWorker.controller.postMessage({__notify:{title,body}});} }catch(e){}}"
                "function sendCommand(text){fetchWithAuth('/voice-command',{method:'POST',body:JSON.stringify({text:text,token:token})}).then(r=>r.json()).then(j=>{if(j.ok&&j.queued){log('Voice command sent: '+j.command,'voice');notify('ALICE','Command: '+j.command);if(j.session_id&&audioEnabled){checkForAudioResponse(j.session_id);}}else{log('Voice command ignored: '+(j.message||'no command'),'evt');}}).catch(e=>log('Voice send error: '+e,'err'));}"
                "function checkForAudioResponse(sessionId){if(!audioEnabled){log('Audio not enabled - tap 🔊 Enable Audio first','warning');return;}setTimeout(()=>{fetch('/audio/'+sessionId).then(r=>{if(r.ok){return r.blob();}else{throw new Error('No audio yet');}}).then(blob=>{const audio=new Audio(URL.createObjectURL(blob));audio.play().then(()=>{log('Playing audio response','voice');}).catch(e=>{log('Audio play failed: '+e+' (mobile browsers require user interaction first)','err');if(e.name==='NotAllowedError'){log('Tap 🔊 Enable Audio and try again','warning');}})}).catch(e=>{if(!e.message.includes('No audio yet')){log('Audio check error: '+e,'err');}else{/* Audio not ready yet, will be checked again */}})},1000);}"
                "function processVoice(text){log('Heard: '+text,'voice');const lower=text.toLowerCase();let foundWake=false;for(const wake of wakeWords){if(lower.includes(wake)){foundWake=true;text=text.substring(text.toLowerCase().indexOf(wake)+wake.length).trim();break;}}if(foundWake||isListening){sendCommand(text);}}"
                "function startVoice(){if(!('webkitSpeechRecognition' in window)&&!('SpeechRecognition' in window)){log('Speech recognition not supported','err');return;}if(micPermission==='denied'){log('Microphone permission denied. Please enable in browser settings.','err');return;}const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;recognition=new SpeechRecognition();recognition.continuous=true;recognition.interimResults=false;recognition.lang='en-US';recognition.onstart=()=>{isListening=true;voiceStatus.textContent='Voice: Listening...';voiceStatus.className='listening';log('Voice recognition started','voice');};recognition.onresult=(e)=>{const transcript=e.results[e.results.length-1][0].transcript;processVoice(transcript);};recognition.onerror=(e)=>{log('Voice error: '+e.error,'err');if(e.error==='not-allowed'){log('Microphone access denied. Please allow microphone permission.','err');}};recognition.onend=()=>{isListening=false;voiceStatus.textContent='Voice: Ready';voiceStatus.className='';log('Voice recognition ended','voice');document.getElementById('voiceStart').disabled=false;document.getElementById('voiceStop').disabled=true;};try{recognition.start();document.getElementById('voiceStart').disabled=true;document.getElementById('voiceStop').disabled=false;}catch(e){log('Failed to start voice: '+e,'err');}}"
                "function stopVoice(){if(recognition){recognition.stop();}}"
                "async function requestMicPermission(){try{if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia){log('Media devices API not supported','err');return;}const stream=await navigator.mediaDevices.getUserMedia({audio:true});stream.getTracks().forEach(track=>track.stop());log('Microphone permission granted','success');updateMicStatus();}catch(e){log('Microphone permission failed: '+e,'err');updateMicStatus();}}"
                "document.getElementById('perm').onclick=()=>Notification.requestPermission().then(r=>log('Permission: '+r,'evt'));"
                "document.getElementById('micPermBtn').onclick=()=>{requestMicPermission();mobileHelp.style.display='block';};"
                "document.getElementById('audioEnable').onclick=async ()=>{try{if(!audioContext){audioContext=new(window.AudioContext||window.webkitAudioContext)();}try{await audioContext.resume();}catch(_e){}audioEnabled=true;try{audioStatusEl.textContent='Enabled';audioStatusEl.style.color='#4caf50';}catch(_e){}log('Audio enabled','success');try{await beep.play();}catch(_e){} }catch(e){log('Enable audio failed: '+e,'err');}};"
                "document.getElementById('test').onclick=()=>{notify('Test','Local notification');log('Local test fired','evt');};"
                "document.getElementById('sendText').onclick=()=>{const input=document.getElementById('textCommand');const text=input.value.trim();if(text){sendCommand(text);input.value='';log('Text command sent: '+text,'voice');}else{log('Please enter a command','warning');}};"
                "document.getElementById('textCommand').onkeypress=(e)=>{if(e.key==='Enter'){document.getElementById('sendText').click();}};"
                "document.getElementById('voiceStart').onclick=()=>startVoice();document.getElementById('voiceStop').onclick=()=>stopVoice();"
                "async function enablePush(){try{if(!('serviceWorker' in navigator)){log('No service worker API (HTTP or unsupported)','err');return;}if(!window.isSecureContext){log('Not secure context (need HTTPS)','err');}const reg=await navigator.serviceWorker.ready;if(!('pushManager' in reg)){log('No pushManager on registration (browser/context lacks push)','err');return;}if(!('PushManager' in window)){log('PushManager interface missing (no push support)','err');return;}const existing=await reg.pushManager.getSubscription();if(existing){log('Reusing existing subscription','evt');const r0=await fetchWithAuth('/subscribe',{method:'POST',body:JSON.stringify({subscription:existing})});const j0=await r0.json();if(j0.ok){log('Confirmed existing ('+j0.count+')','evt');notify('ALICE','Push still enabled');}else{log('Reconfirm fail '+JSON.stringify(j0),'err');}return;}const vapid=await fetch('/vapid').then(r=>r.json()).then(j=>j.public_key);if(!vapid){log('No VAPID key (server side issue)','err');return;}const conv=b64=>Uint8Array.from(atob(b64.replace(/-/g,'+').replace(/_/g,'/')),c=>c.charCodeAt(0));let keyBytes;try{keyBytes=conv(vapid);}catch(e){log('VAPID decode failed '+e,'err');return;}let sub;try{sub=await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:keyBytes});}catch(e){log('subscribe() threw '+e,'err');return;}const r=await fetchWithAuth('/subscribe',{method:'POST',body:JSON.stringify({subscription:sub})});const j=await r.json();if(j.ok){log('Push subscribed ('+j.count+')','evt');notify('ALICE','Push enabled');}else{log('Sub fail '+JSON.stringify(j),'err');}}catch(e){log('Push error '+e,'err');log('UA:'+navigator.userAgent,'err');}}"
                "async function testServerPush(){const r=await fetchWithAuth('/pushnotify',{method:'POST',body:JSON.stringify({title:'Test',body:'Server push test'})});const j=await r.json();if(j.ok){log('Server push sent to '+j.sent,'evt');}else{log('Push send fail '+JSON.stringify(j),'err');}}"
                "                "                "function diag(){try{log('UA: '+navigator.userAgent,'evt');log('SecureContext: '+window.isSecureContext,'evt');log('Has serviceWorker API: '+('serviceWorker'in navigator),'evt');log('Has PushManager global: '+('PushManager'in window),'evt');log('Notification.permission: '+Notification.permission,'evt');log('SpeechRecognition: '+('webkitSpeechRecognition' in window || 'SpeechRecognition' in window),'voice');log('MediaDevices API: '+('mediaDevices' in navigator && 'getUserMedia' in navigator.mediaDevices),'voice');updateMicStatus();try{log('Audio enabled: '+audioEnabled,'evt');log('AudioContext state: '+(audioContext?audioContext.state:'none'),'evt');}catch(_e){}if('serviceWorker' in navigator){navigator.serviceWorker.ready.then(r=>{const keys=Object.keys(r.__proto__||{});log('SW reg proto keys: '+keys.join(','),'evt');try{log('typeof r.pushManager: '+typeof r.pushManager,'evt');if(r.pushManager){log('pushManager obj keys: '+Object.keys(r.pushManager.__proto__||{}).join(','),'evt');}}catch(e){log('Access pushManager threw '+e,'err');}}).catch(e=>log('ready() err '+e,'err'));}else{log('Service Worker not available','evt');}}catch(e){log('diag err '+e,'err');}};}}"
                "document.getElementById('pushEnable').onclick=()=>enablePush();document.getElementById('pushTest').onclick=()=>testServerPush();document.getElementById('diag').onclick=()=>diag();document.getElementById('playOpen').onclick=()=>log('Custom audio disabled; using system notification sound','evt');"
                "function start(){if(!token){log('Missing token param (?token=...)','err');}updateMicStatus();const es=new EventSource('/events?token='+encodeURIComponent(token));es.onopen=()=>{statusEl.textContent='connected';log('SSE connected','evt');};es.onerror=()=>{statusEl.textContent='error';log('SSE error','err');};es.onmessage=e=>{try{const data=JSON.parse(e.data);if(data.role||data.content){log('Msg: '+(data.content||'[no content]'),'evt');notify('ALICE',data.content||'[message]');}if(data.event){log('Event '+data.event.kind+': '+(data.event.text||JSON.stringify(data.event)),'evt');notify((data.event.kind||'EVENT'),data.event.text||data.event.kind);}}catch(err){log('Bad payload '+err,'err');}};}start();})();</script></body></html>"
            )
            self.wfile.write(html.encode())
            return
            # Fallback 404 (no path matched above)
            return self._fail(404,'not found')

    def do_POST(self):
        p = urlparse(self.path)
        # Optional debug logging of incoming request (set REMOTE_DEBUG=1 to enable)
        _maybe_debug_log_request(self, 'do_POST')
        if p.path == '/command':
            data = self._read_json()
            if not self._auth(data.get('token')):
                return self._fail(401,'unauthorized')
            text = (data.get('text') or '').strip()
            if not text:
                return self._fail(400,'text required')
            _incoming_commands.put((text, None))  # No session ID for regular commands
            return self._ok({'queued': True})
        if p.path == '/subscribe':
            data = self._read_json()
            if not self._auth(data.get('token')):
                return self._fail(401,'unauthorized')
            sub = data.get('subscription')
            if not isinstance(sub, dict) or 'endpoint' not in sub:
                return self._fail(400,'invalid subscription')
            endpoints = [s.get('endpoint') for s in _SUBS]
            if sub['endpoint'] not in endpoints:
                _SUBS.append(sub)
                _save_subs()
            return self._ok({'stored': True, 'count': len(_SUBS)})
        if p.path == '/pushnotify':
            data = self._read_json()
            if not self._auth(data.get('token')):
                return self._fail(401,'unauthorized')
            title = (data.get('title') or 'ALICE').strip()
            body = (data.get('body') or '').strip()
            sent = send_web_push_all(title, body)
            add_event('pushnotify', text=body or title)
            return self._ok({'sent': sent})
        if p.path == '/voice-command':
            data = self._read_json()
            if not self._auth(data.get('token')):
                return self._fail(401,'unauthorized')
            text = (data.get('text') or '').strip()
            if not text:
                return self._fail(400,'text required')
            
            # Generate session ID for audio response tracking
            session_id = secrets.token_hex(8)
            
            # Process wake words for voice commands
            wake_words = ['hey alice', 'hey virgil', 'hey vergil', 'ok alice', 'ok virgil', 'ok vergil', 'alice', 'virgil', 'vergil']
            processed_text = text.lower()
            command_text = None
            
            # Find and remove wake word
            for wake in wake_words:
                if processed_text.startswith(wake):
                    # Extract command after wake word, handling punctuation
                    remaining = processed_text[len(wake):].strip()
                    # Remove leading punctuation
                    remaining = remaining.lstrip(',.!? ')
                    command_text = remaining
                    break
            
            # If no wake word found, treat as direct command
            if command_text is None:
                command_text = text
            
            # Check for shutdown commands
            shutdown_commands = ['goodbye', 'exit', 'quit', 'shutdown', 'bye', 'see you', 'good night']
            if any(cmd in command_text.lower() for cmd in shutdown_commands):
                # Send shutdown command to ALICE
                _incoming_commands.put(('goodbye', None))
                add_event('shutdown_command', text='Shutdown requested via voice')
                return self._ok({'queued': True, 'command': 'goodbye', 'shutdown': True})
            
            if command_text:
                # Track this as a remote session for audio response
                track_remote_session(session_id, command_text)
                _incoming_commands.put((command_text, session_id))
                add_event('voice_command', text=command_text, session_id=session_id)
                return self._ok({'queued': True, 'command': command_text, 'session_id': session_id})
            else:
                return self._ok({'queued': False, 'message': 'No command after wake word'})
        if p.path == '/discord':
            data = self._read_json()
            if not self._auth(data.get('token')):
                return self._fail(401,'unauthorized')
            channel = data.get('channel')
            message = (data.get('message') or '').strip()
            if not channel or not message:
                return self._fail(400,'channel+message required')
            try:
                import discord_notifier  # type: ignore
                ok, info = discord_notifier.send_discord_message(channel, message)
            except Exception as e:
                return self._fail(500,f'discord error {e}')
            if not ok:
                return self._fail(500, info)
            return self._ok({'sent': True})
        if p.path == '/notify':
            data = self._read_json()
            if not self._auth(data.get('token')):
                return self._fail(401,'unauthorized')
            msg = (data.get('message') or '').strip() or '(empty)'
            try:
                ok, info = sms_notifier.send_sms(msg)
            except Exception as e:
                return self._fail(500, f'sms error {e}')
            if not ok:
                return self._fail(500, info)
            add_event('sms', text=msg)
            return self._ok({'sent': True})
        return self._fail(404,'not found')

_server_thread: Optional[threading.Thread] = None
_httpd: Optional[ThreadingHTTPServer] = None
_funnel_thread: Optional[threading.Thread] = None
_FUNNEL_STARTED = False

class _QuietThreadingHTTPServer(ThreadingHTTPServer):
    """ThreadingHTTPServer that silences benign disconnect tracebacks (WinError 10053 / Broken pipe)."""
    def handle_error(self, request, client_address):  # type: ignore[override]
        import sys, traceback
        exc = sys.exc_info()
        if not exc[0]:
            return
        etype = exc[0].__name__
        msg = str(exc[1])
        if 'WinError 10053' in msg or 'Broken pipe' in msg or 'ConnectionResetError' in etype:
            return  # suppress noisy network disconnects
        ThreadingHTTPServer.handle_error(self, request, client_address)

def start_server(host: str = '0.0.0.0', port: int = 8765):
    global _server_thread, _httpd
    if _server_thread and _server_thread.is_alive():
        return
    try:
        _httpd = _QuietThreadingHTTPServer((host, port), _RemoteHandler)
    except OSError as e:
        print(f"[Remote] Bind failed {host}:{port}: {e}")
        return

    def _launch_funnel_clean():
        """Optional: Set up tailscale serve for easier access within tailnet."""
        print('[Remote][Funnel] Skipping automatic setup (can be done manually if needed)')
        print('[Remote][Funnel] Access via: http://100.79.99.39:8765/client?token=' + get_token())
        return

    def _serve():
        print(f"[Remote] Listening on {host}:{port} token={get_token()} (remote_token.txt)")
        print("[Remote] Tip: set environment variable REMOTE_DEBUG=1 to enable verbose request/header/body logging for debugging client requests")
        try:
            _httpd.serve_forever()
        except Exception as e:
            print(f"[Remote] Server stopped: {e}")
    _server_thread = threading.Thread(target=_serve, daemon=True)
    _server_thread.start()

    # Start funnel thread once
    global _funnel_thread
    if not _funnel_thread or not _funnel_thread.is_alive():
        _funnel_thread = threading.Thread(target=_launch_funnel_clean, daemon=True)
        _funnel_thread.start()

    # After launching, print helpful access URLs for other devices on the network
    try:
        import socket
        addrs = set()
        # Method 1: gethostbyname_ex
        try:
            hn = socket.gethostname()
            _, _, ips = socket.gethostbyname_ex(hn)
            for ip in ips:
                if ip and not ip.startswith('127.'):
                    addrs.add(ip)
        except Exception:
            pass

        # Method 2: socket trick to get primary outbound address
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            primary = s.getsockname()[0]
            s.close()
            if primary and not primary.startswith('127.'):
                addrs.add(primary)
        except Exception:
            pass

        # Method 3: getaddrinfo fallback
        try:
            for fam, socktype, proto, canonname, sa in socket.getaddrinfo(socket.gethostname(), None):
                ip = sa[0]
                if ':' in ip:
                    continue
                if ip and not ip.startswith('127.'):
                    addrs.add(ip)
        except Exception:
            pass

        if not addrs:
            addrs.add('127.0.0.1')

        token = get_token()
        print('[Remote] Access URLs (open from another device):')
        for ip in sorted(addrs):
            proto = 'http'
            print(f'  {proto}://{ip}:{port}/client?token={token}')
            # Also show /events and /voice-command endpoints for advanced testing
            print(f'    - events (SSE): {proto}://{ip}:{port}/events?token={token}')
            print(f'    - voice command POST: {proto}://{ip}:{port}/voice-command (include Authorization: Bearer <token> or ?token=...)')

        # If any Tailscale-looking address present, highlight it
        ts = [a for a in addrs if a.startswith('100.')]
        if ts:
            print('[Remote] Tailscale-like addresses detected: ' + ', '.join(ts))

    except Exception as _e:
        print(f'[Remote] Failed to enumerate local addresses: {_e}')

def poll_next_command() -> Optional[tuple[str, str | None]]:
    try:
        cmd = _incoming_commands.get_nowait()
        return cmd
    except Exception:
        return None

if __name__ == '__main__':
    try:
        start_server()
        print("[Remote] Server started successfully")
        while True:
            if has_commands():
                cmd = pop_command()
                print('Incoming:', cmd)
            time.sleep(0.5)
    except Exception as e:
        print(f"[Remote] Fatal error: {e}")
        import traceback
        traceback.print_exc()
    except KeyboardInterrupt:
        print("[Remote] Shutting down...")
        pass
