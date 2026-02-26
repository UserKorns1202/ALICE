import os
import logging
# ALICE is imported lazily via get_alice() to avoid heavy import-time side-effects
# (cv2, pygame, model files) which can crash the bridge when those resources
# are not present. Use get_alice() below where ALICE functions are needed.
import re
import shlex
import subprocess
import json
import uuid
import platform

try:
    import uvicorn
except Exception:
    uvicorn = None

LOG_PATH = os.environ.get('AMICA_ALICE_BRIDGE_LOG', 'bridge_calls.log')
logging.basicConfig(filename=LOG_PATH, level=logging.INFO, format='%(asctime)s %(message)s')

BRIDGE_TOKEN = os.environ.get('AMICA_ALICE_BRIDGE_TOKEN', '')


def contains_destructive_command(text: str) -> bool:
    """Basic heuristic to detect destructive intents that should require explicit confirmation."""
    if not text:
        return False
    t = text.lower()
    destructive_keywords = ["format ", "rm -rf", "delete all", "wipe", "shutdown", "reboot", "uninstall", "factory reset", "reset windows", "erase ", "kill process", "taskkill /f", "remove user"]
    return any(k in t for k in destructive_keywords)



import asyncio
import base64
import json
import os
import re
import shlex
import signal
import subprocess
import uuid
import time
from typing import Dict, Any, Optional

import httpx
try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Body, HTTPException
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
    HAS_FASTAPI = True
except Exception:
    # Allow importing this module in environments where FastAPI isn't installed
    HAS_FASTAPI = False
    FastAPI = None  # type: ignore
    WebSocket = None  # type: ignore
    WebSocketDisconnect = Exception  # type: ignore
    Request = None  # type: ignore
    Body = None  # type: ignore
    HTTPException = Exception  # type: ignore
    JSONResponse = dict  # type: ignore
    # pydantic BaseModel won't be available; define a simple fallback for typing only
    class BaseModel:  # type: ignore
        pass

if HAS_FASTAPI:
    app = FastAPI(title="Amica ALICE Bridge")
    try:
        # Add permissive CORS middleware so browser-based frontends can call the bridge
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    except Exception:
        # If CORSMiddleware is not available for any reason, continue without failing import.
        pass
    # Optional debugging middleware: log request paths, headers and bodies when DEBUG_BRIDGE=1
    if os.environ.get("DEBUG_BRIDGE", "0") == "1":
        @app.middleware("http")
        async def _log_requests(request, call_next):
            try:
                body_bytes = await request.body()
                try:
                    body_text = body_bytes.decode("utf-8")
                except Exception:
                    body_text = str(body_bytes)
                logging.info("[BRIDGE DEBUG] %s %s headers=%s body=%s", request.method, request.url.path, dict(request.headers), body_text)
            except Exception as e:
                logging.warning("[BRIDGE DEBUG] failed to read body: %s", e)
            return await call_next(request)
else:
    # Provide a small dummy `app` object with decorator methods that return
    # identity decorators. This allows the module to define route handler
    # functions with `@app.get/post/websocket` decorators even when FastAPI
    # isn't installed (useful for local unit tests and `--selftest`).
    class _DummyApp:
        def get(self, *a, **kw):
            def _dec(f):
                return f
            return _dec
        def post(self, *a, **kw):
            def _dec(f):
                return f
            return _dec
        def websocket(self, *a, **kw):
            def _dec(f):
                return f
            return _dec
        # Provide additional no-op decorators to mimic FastAPI surface used during import-time
        def options(self, *a, **kw):
            def _dec(f):
                return f
            return _dec
        def middleware(self, *a, **kw):
            def _dec(f):
                return f
            return _dec
        # Allow add_middleware calls (no-op)
        def add_middleware(self, *a, **kw):
            return None
    app = _DummyApp()


    # Attempt to load Amica frontend config so bridge can separate system prompt from user text
    AMICA_SYSTEM_PROMPT = None
    def _load_amica_system_prompt():
        global AMICA_SYSTEM_PROMPT
        candidates = [
            os.path.join(os.path.dirname(__file__), 'Amica', 'Amica-temp', 'src', 'features', 'externalAPI', 'dataHandlerStorage', 'config.json'),
            os.path.join(os.path.dirname(__file__), '..', 'Amica', 'Amica-temp', 'src', 'features', 'externalAPI', 'dataHandlerStorage', 'config.json'),
            os.path.join(os.path.dirname(__file__), 'Amica', 'Amica-temp', 'src', 'features', 'chat', 'buildPrompt.ts'),
        ]
        for p in candidates:
            try:
                if os.path.exists(p):
                    with open(p, 'r', encoding='utf-8') as f:
                        try:
                            j = json.load(f)
                            sp = j.get('system_prompt') or j.get('personality_prompt_alice') or j.get('personality_prompt_cortana')
                            if sp and isinstance(sp, str) and sp.strip():
                                AMICA_SYSTEM_PROMPT = sp.strip()
                                logging.info(f"[BRIDGE] Loaded Amica system_prompt from {p}")
                                return
                        except Exception:
                            # try to read as plain text (for buildPrompt.ts)
                            try:
                                txt = f.read()
                                # look for config("system_prompt") literal in the JS/TS buildPrompt file
                                m = re.search(r'config\("system_prompt"\)\s*\)\s*\+\s*"\\n\\n"\s*;?', txt)
                                # fallback: search for the default phrase 'You are'
                                if 'You are' in txt and not AMICA_SYSTEM_PROMPT:
                                    # heuristically extract first paragraph starting with 'You are'
                                    m2 = re.search(r'(You are[\s\S]{20,500}?)"', txt)
                                    if m2:
                                        cand = m2.group(1)
                                        AMICA_SYSTEM_PROMPT = cand.strip()
                                        logging.info(f"[BRIDGE] Heuristically loaded Amica system_prompt from {p}")
                                        return
                            except Exception:
                                pass
            except Exception:
                continue

    _load_amica_system_prompt()

# Configuration
KEVIN_URL = os.environ.get("KEVIN_URL", "http://127.0.0.1:5000")
PIPER_URL = os.environ.get("PIPER_URL", "http://127.0.0.1:3000")
BRIDGE_API_KEY = os.environ.get("BRIDGE_API_KEY", "212umob")
ALICE_EXEC_PATH = os.environ.get("ALICE_EXEC_PATH")  # optional path to existing ALICE implementation

if not BRIDGE_API_KEY:
    BRIDGE_API_KEY = str(uuid.uuid4())
    print("BRIDGE_API_KEY not set — generated one for dev use:", BRIDGE_API_KEY)

# internal per-session streaming queues
sessions: Dict[str, asyncio.Queue] = {}

# Simple in-memory pending actions store (action_id -> action dict)
pending_actions: Dict[str, Dict[str, Any]] = {}

# Action whitelist - these are the only 'kinds' allowed by default. Map to handlers below.
ACTION_WHITELIST = {"open_url", "open_file", "run_preapproved", "screenshot"}

# Helper models
class QueryRequest(BaseModel):
    text: str
    session_id: Optional[str] = None

class ActionRequest(BaseModel):
    kind: str
    args: Dict[str, Any] = {}

# ---------- Utilities ----------

async def call_kevin(prompt: str, timeout: int = 60, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    # KEVIN expects a JSON body with 'text' (and optional flags like use_history/speak)
    async with httpx.AsyncClient(timeout=timeout) as client:
        payload = {"text": prompt, "use_history": False, "speak": False}
        # Merge any caller-supplied extras (e.g., {'planner': True, 'fast': True, 'model': 'tiny'})
        if extra and isinstance(extra, dict):
            try:
                payload.update(extra)
            except Exception:
                pass
        # Optional debug logging for outgoing KEVIN requests
        try:
            if os.environ.get("DEBUG_BRIDGE", "0") == "1":
                logging.info("[BRIDGE DEBUG] call_kevin POST %s payload=%s", KEVIN_URL, json.dumps(payload))
        except Exception:
            pass

        # Allow KEVIN_URL to be either the base URL or already include '/query'.
        post_url = KEVIN_URL
        if not post_url.rstrip('/').endswith('/query'):
            post_url = post_url.rstrip('/') + '/query'

        r = await client.post(post_url, json=payload)

        # If KEVIN returns 422, attempt a few compatibility payloads and log the response body
        if r.status_code == 422:
            try:
                body_text = r.text
            except Exception:
                body_text = '<could not read response body>'
            logging.warning('[BRIDGE DEBUG] KEVIN returned 422 for payload %s; body=%s', json.dumps(payload), body_text)

            # Try alternative payload shapes common to other chat servers
            alt_payloads = [
                {"messages": [{"role": "user", "content": prompt}]},
                {"prompt": prompt},
                {"input": prompt},
            ]
            for alt in alt_payloads:
                try:
                    if os.environ.get("DEBUG_BRIDGE", "0") == "1":
                        logging.info('[BRIDGE DEBUG] call_kevin trying alternate payload %s', json.dumps(alt))
                    r2 = await client.post(post_url, json=alt)
                    if r2.status_code == 200:
                        try:
                            return r2.json()
                        except Exception:
                            return {"response": r2.text}
                except Exception:
                    continue

            # None of the alternates worked; raise with original body for debugging
            try:
                txt = r.text
            except Exception:
                txt = '<could not read response text>'
            raise Exception(f"KEVIN HTTP {r.status_code}: {txt}")

        # Log response details when debugging
        try:
            if os.environ.get("DEBUG_BRIDGE", "0") == "1":
                try:
                    txt = r.text
                except Exception:
                    txt = "<could not read response text>"
                logging.info("[BRIDGE DEBUG] call_kevin response status=%s text=%s", r.status_code, txt)
        except Exception:
            pass

        # If KEVIN returned a non-200, raise an informative exception so callers
        # can include the status and body in debug traces.
        if r.status_code != 200:
            try:
                txt = r.text
            except Exception:
                txt = "<could not read response text>"
            raise Exception(f"KEVIN HTTP {r.status_code}: {txt}")

        # Try to decode JSON; fall back to raw text if decode fails
        try:
            return r.json()
        except Exception:
            try:
                return {"response": r.text}
            except Exception:
                return {"response": ""}

def extract_tags_and_text(raw: str):
    tags = []
    # Amica frontend allowed emotions (kept in sync with Amica repo)
    ALLOWED_EMOTIONS = [
        "neutral", "happy", "angry", "sad", "relaxed", "Surprised",
        "Shy", "Jealous", "Bored", "Serious", "Suspicious", "Victory",
        "Sleep", "Love"
    ]

    # helper: normalize a raw tag to a canonical allowed emotion (case-insensitive)
    def normalize_tag(t: str):
        if not t:
            return None
        t_str = t.strip()
        # direct case-sensitive match
        if t_str in ALLOWED_EMOTIONS:
            return t_str
        # case-insensitive match
        for cand in ALLOWED_EMOTIONS:
            if cand.lower() == t_str.lower():
                return cand
        # try simple capitalization variants (e.g., 'sleep' -> 'Sleep')
        for cand in ALLOWED_EMOTIONS:
            if cand.lower() == t_str.lower():
                return cand
        return None

    # match leading bracket tags e.g. [happy][serious] Hello
    while True:
        m = re.match(r'^\[(\w[\w-]*)\]\s*', raw)
        if not m:
            break
        raw_tag = m.group(1)
        norm = normalize_tag(raw_tag)
        if norm:
            tags.append(norm)
        else:
            # keep unknown tags verbatim to preserve behavior
            tags.append(raw_tag)
        raw = raw[m.end():]
    return tags, raw


def _free_ports_on_windows(ports: list, dry_run: bool = False):
    """Attempt to find and (optionally) kill processes listening on the given TCP ports on Windows.

    This is destructive: it will call `netstat -ano` and `taskkill /PID <pid> /F` when not in dry-run.
    Only runs when `platform.system()` reports 'Windows'. Controlled by env `BRIDGE_PORT_FREE`.
    """
    try:
        if platform.system() != 'Windows':
            logging.info("[BRIDGE PORT-FREE] Not Windows; skipping")
            return
    except Exception:
        return

    try:
        out = subprocess.check_output(['netstat', '-ano'], text=True, stderr=subprocess.DEVNULL)
    except Exception as e:
        logging.warning(f"[BRIDGE PORT-FREE] netstat failed: {e}")
        return

    pids = set()
    for line in out.splitlines():
        parts = [p for p in line.split() if p]
        if len(parts) < 5:
            continue
        proto = parts[0]
        local = parts[1]
        pid = parts[-1]
        if proto.upper() != 'TCP':
            continue
        for port in ports:
            try:
                if str(local).endswith(':'+str(port)):
                    pids.add(int(pid))
            except Exception:
                continue

    if not pids:
        logging.info(f"[BRIDGE PORT-FREE] No PIDs found for ports {ports}")
        return

    for pid in pids:
        try:
            logging.info(f"[BRIDGE PORT-FREE] PID {pid} listening on {ports}")
            if dry_run:
                logging.info(f"[BRIDGE PORT-FREE] dry-run: would kill PID {pid}")
                continue
            # show tasklist for visibility
            try:
                subprocess.check_call(['tasklist', '/FI', f'PID eq {pid}'])
            except Exception:
                pass
            subprocess.check_call(['taskkill', '/PID', str(pid), '/F'])
            logging.info(f"[BRIDGE PORT-FREE] killed PID {pid}")
        except Exception as e:
            logging.warning(f"[BRIDGE PORT-FREE] failed to kill PID {pid}: {e}")

async def proxy_tts(text: str, voice: Optional[str] = None) -> Optional[str]:
    """If a Piper server is configured, request audio and return the playback URL path (or None on failure).
    This is a simple helper that posts to PIPER_URL + '/tts'. The exact API depends on your Piper server.
    """
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            params = {"text": text}
            if voice:
                params["voice"] = voice
            r = await client.get(f"{PIPER_URL}/tts", params=params)
            if r.status_code == 200:
                # assume server returns bytes (audio) or a JSON with url
                ctype = r.headers.get("content-type","")
                if "application/json" in ctype:
                    data = r.json()
                    return data.get("url")
                # otherwise write temp file and return path
                fname = f"audio_{uuid.uuid4().hex}.wav"
                path = os.path.join(".", "tmp_audio")
                os.makedirs(path, exist_ok=True)
                out = os.path.join(path, fname)
                with open(out, "wb") as f:
                    f.write(r.content)
                return out
    except Exception as e:
        print("proxy_tts failed:", e)
    return None


# Lazy import helper for ALICE to avoid importing heavy modules (cv2, pygame, etc.)
# at process start. This prevents the bridge from failing when ALICE's optional
# dependencies or data files (like YOLO cfg/weights) are missing.
_ALICE_MODULE = None
_ALICE_IMPORT_ERROR = None
def get_alice():
    global _ALICE_MODULE
    if _ALICE_MODULE is not None:
        return _ALICE_MODULE
    try:
        # Prefer the newer ALICE_v2 module if present, fall back to ALICE for compatibility
        try:
            import ALICE_v2 as alice_mod
        except Exception:
            import ALICE as alice_mod
        _ALICE_MODULE = alice_mod
        return _ALICE_MODULE
    except Exception as e:
        # Record the import error for diagnostics (readable when DEBUG_BRIDGE=1)
        try:
            _ALICE_IMPORT_ERROR = str(e)
        except Exception:
            _ALICE_IMPORT_ERROR = repr(e)
        logging.warning("Lazy import of ALICE failed: %s", _ALICE_IMPORT_ERROR)
        return None

# ---------- Simple auth dependency ----------

def require_api_key(req):
    # req is expected to be a FastAPI Request-like object when running under FastAPI.
    # In non-FastAPI contexts this function may be called with a plain object that
    # provides `headers` and `query_params`; keep it duck-typed to avoid import-time errors.
    key = None
    try:
        key = req.headers.get("x-bridge-api-key") or req.query_params.get("api_key")
    except Exception:
        # fallback: try dict-like access
        try:
            key = req.get("x-bridge-api-key") or (req.get("query_params") or {}).get("api_key")
        except Exception:
            key = None
    if key != BRIDGE_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

# ---------- HTTP endpoints ----------
@app.get("/health")
async def health():
    # Return bridge status plus a proxied KEVIN /health when possible so frontends
    # can reliably detect the model even if KEVIN_URL was configured to include
    # an explicit '/query' suffix.
    info = {"ok": True, "kevin_url": KEVIN_URL, "piper_url": PIPER_URL}
    # Try to fetch KEVIN's /health and include it; keep failure non-fatal.
    try:
        # Normalize KEVIN base (strip trailing '/query' if present)
        base = KEVIN_URL.rstrip('/')
        if base.endswith('/query'):
            base = base[:-len('/query')]
        health_url = base.rstrip('/') + '/health'
        import httpx as _httpx
        async with _httpx.AsyncClient(timeout=3) as _c:
            r = await _c.get(health_url)
            if r.status_code == 200:
                try:
                    hj = r.json()
                except Exception:
                    hj = None
                if isinstance(hj, dict):
                    info['kevin_health'] = hj
                    if 'model_name' in hj:
                        info['kevin_model_name'] = hj.get('model_name')
            else:
                info['kevin_health_error'] = f"HTTP {r.status_code}"
    except Exception as e:
        info['kevin_health_error'] = str(e)

    return info


# Backwards-compatible aliases for older frontend paths that expect /bridge/alice/*
@app.get("/bridge/alice/health")
async def bridge_health():
    return await health()


@app.options("/bridge/alice/query")
async def bridge_query_options():
    # Allow CORS preflight to succeed when frontend hits /bridge/alice/query
    return JSONResponse(status_code=200, content={})


async def try_use_tools(original_prompt: str) -> Optional[str]:
    """Use a fast planner (KEVIN) to decide whether a tool is needed.

    If a tool is requested, run it and return an augmented prompt (original + tool result).
    Otherwise return None.
    """
    try:
        planner_instruction = (
            "You are a fast tool-selector. If the user's request requires calling an external tool (weather, search, calculator, time, etc.),\n"
            "respond ONLY with a JSON object like: {\"tool\": {\"name\": \"weather\", \"args\": {\"location\": \"Seattle\"}} }\n"
            "If no tool is needed, respond with {\"no_tool\": true}. Do not output any other text."
        )
        planner_prompt = planner_instruction + "\n\nUser: " + original_prompt
        # Ask KEVIN in a quick/fast mode (bridge adds optional flags which KEVIN server may honor)
        planner_resp = await call_kevin(planner_prompt, timeout=6, extra={"planner": True, "fast": True})
        planner_text = planner_resp.get("response", "") if isinstance(planner_resp, dict) else str(planner_resp)
        # Try to parse JSON directly
        obj = None
        try:
            obj = json.loads(planner_text)
        except Exception:
            # Try to extract first JSON object from text
            try:
                m = re.search(r"(\{[\s\S]*\})", planner_text)
                if m:
                    obj = json.loads(m.group(1))
            except Exception:
                obj = None

        if not obj or not isinstance(obj, dict):
            return None

        if obj.get("no_tool"):
            return None

        tool = obj.get("tool")
        if not tool or not isinstance(tool, dict):
            return None

        name = tool.get("name")
        args = tool.get("args", {}) or {}
        if not name:
            return None

        # Run the tool
        try:
            import tools as _tools
            tool_result = await _tools.run_tool(name, args)
        except Exception as e:
            tool_result = {"error": str(e)}

        # Compose an augmented prompt for the heavy model containing the tool result
        augmented = original_prompt + "\n\n[Tool call executed] tool=%s args=%s result=%s\nPlease answer the user's request using the tool result where useful." % (
            name, json.dumps(args, ensure_ascii=False), json.dumps(tool_result, ensure_ascii=False)
        )
        return augmented
    except Exception as e:
        logging.info("[BRIDGE] try_use_tools failed: %s", e)
        return None


@app.post("/bridge/alice/query")
async def bridge_query_alias(request: 'Request', body: dict = None):
    # Map /bridge/alice/query -> /query for compatibility with older frontends.
    # Attempt to read raw body first and log a truncated preview for diagnostics
    if body is None:
        try:
            raw_bytes = await request.body()
            try:
                raw_text = raw_bytes.decode('utf-8')
            except Exception:
                raw_text = str(raw_bytes)
            if len(raw_text) > 2000:
                raw_preview = raw_text[:2000] + '...<truncated>'
            else:
                raw_preview = raw_text
            logging.info('[BRIDGE RAW BODY] %s', raw_preview)
            print(f"[BRIDGE RAW BODY] {raw_preview}")
            try:
                body = json.loads(raw_text)
            except Exception:
                # fall back to older parsing below
                body = None
        except Exception:
            body = None

    # If frontend sent a structured payload {system, messages} or compact {system, user}, handle it directly
    try:
        if isinstance(body, dict) and (('system' in body) or ('messages' in body) or ('user' in body)):
            system_text = body.get('system') or ''
            # Support compact single-user message payloads: { user: '...' }
            if 'user' in body and body.get('user'):
                user_text = body.get('user')
            else:
                msgs = body.get('messages') or []
                user_parts = []
                try:
                    for m in msgs:
                        if isinstance(m, dict) and m.get('role') == 'user' and m.get('content'):
                            user_parts.append(m.get('content'))
                except Exception:
                    pass
                user_text = '\n'.join(user_parts) if user_parts else (body.get('text') or '')

            prompt = (system_text.strip() + '\n\n' + user_text.strip()).strip() if system_text else user_text
            # Prefer the shared query handling (which will try ALICE first then KEVIN)
            try:
                qreq = QueryRequest(text=prompt)
                return await query_endpoint(qreq, request)
            except HTTPException:
                raise
            except Exception:
                # fallback to direct KEVIN call if anything goes wrong here
                try:
                    kevin = await call_kevin(prompt)
                    raw = kevin.get("response", "") if isinstance(kevin, dict) else str(kevin)
                    tags, text = extract_tags_and_text(raw)
                    return {"id": str(uuid.uuid4()), "raw": raw, "text": text, "tags": tags, "used_alice": False}
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"KEVIN error: {e}")
    except Exception:
        # fall back to legacy behavior below
        pass

    # Normalize common frontend key names to 'text'
    if isinstance(body, dict):
        text_val = body.get('text') or body.get('message') or body.get('input') or body.get('query') or body.get('content') or ''
        session_id = body.get('session_id') or body.get('session') or body.get('sid')
        normalized = {'text': text_val}
        if session_id:
            normalized['session_id'] = session_id
    else:
        # If body is a raw string, use it as text
        try:
            normalized = {'text': str(body)}
        except Exception:
            normalized = {'text': ''}

    # Build QueryRequest model from normalized dict
    try:
        q = QueryRequest(**normalized)
    except Exception:
        # Fallback: create minimal QueryRequest
        q = QueryRequest(text=normalized.get('text', ''))
    return await query_endpoint(q, request)

@app.post("/query")
async def query_endpoint(q: QueryRequest, request: 'Request'):
    require_api_key(request)
    prompt = q.text
    session_id = q.session_id or str(uuid.uuid4())
    # First try to let a locally-imported ALICE handle the prompt (commands).
    try:
        alice = get_alice()
        # DEBUG: surface what get_alice returned when debugging is enabled
        if os.environ.get("DEBUG_BRIDGE", "0") == "1":
            try:
                logging.info("[BRIDGE DEBUG] get_alice() -> %r", alice)
                # if import previously failed, log that error text too
                try:
                    logging.info("[BRIDGE DEBUG] _ALICE_IMPORT_ERROR=%r", _ALICE_IMPORT_ERROR)
                except Exception:
                    pass
                if alice is not None:
                    try:
                        logging.info("[BRIDGE DEBUG] alice dir: %s", sorted(dir(alice)))
                    except Exception:
                        pass
            except Exception:
                pass
        # ALICE_v2 often creates its ContextManager inside `main()`; when imported
        # the module may expose `context_manager` (the class) but not the
        # `context_mgr` instance. Accept either form and lazily create an
        # instance when possible so the bridge can reuse ALICE's intent/router.
        if alice and hasattr(alice, 'execute_routed_command') and (hasattr(alice, 'context_mgr') or hasattr(alice, 'context_manager')):
            # lazily create context_mgr if only class is available
            if not getattr(alice, 'context_mgr', None):
                try:
                    if hasattr(alice, 'context_manager'):
                        alice.context_mgr = alice.context_manager.ContextManager()
                    else:
                        alice.context_mgr = None
                except Exception as _e:
                    logging.warning("[BRIDGE] failed to create alice.context_mgr: %s", _e)
                    alice.context_mgr = None

            # Set minimal safe defaults for globals some ALICE executors expect
            try:
                if not hasattr(alice, 'aiModel'):
                    alice.aiModel = getattr(alice, 'aiModel', 'virgil')
            except Exception:
                pass
            try:
                if not hasattr(alice, 'agent'):
                    alice.agent = None
            except Exception:
                pass
            try:
                if not hasattr(alice, 'engine'):
                    alice.engine = None
            except Exception:
                pass

            if getattr(alice, 'context_mgr', None):
                try:
                    intent = None
                    try:
                        intent = alice.context_mgr.analyze_intent(prompt)
                    except Exception:
                        intent = None
                    entities = None
                    try:
                        entities = alice.context_mgr.extract_entities(prompt)
                    except Exception:
                        entities = None
                    routed = None
                    try:
                        routed = alice.context_mgr.route_command(prompt, intent, entities)
                    except Exception:
                        routed = None

                    if intent == 'command' and routed:
                        try:
                            resp = alice.execute_routed_command(routed, prompt, alice.context_mgr)
                            return {"id": session_id, "raw": str(resp), "text": str(resp), "tags": [], "used_alice": True}
                        except Exception as e:
                            logging.warning("[BRIDGE] ALICE execution failed: %s", e)
                            print(f"[BRIDGE] ALICE execution failed: {e}")
                except Exception as _e:
                    logging.info("[BRIDGE] ALICE analysis/execution path raised: %s", _e)

    except Exception as _e:
        # If lazy import or analysis fails, fall back to KEVIN below
        logging.info("[BRIDGE] ALICE not available or analysis failed: %s", _e)

    # If ALICE didn't handle it, fall back to KEVIN as before
    try:
        # Quick rule-based prefilter: if ALICE's context manager exposes
        # `decide_tool`, consult it first to short-circuit obvious tool calls
        # (weather/search/calc/time). This avoids the fast planner roundtrip.
        try:
            alice = get_alice()
            if alice and getattr(alice, 'context_mgr', None) and hasattr(alice.context_mgr, 'decide_tool'):
                try:
                    dt = alice.context_mgr.decide_tool(prompt)
                    if dt and isinstance(dt, dict) and dt.get('name'):
                        try:
                            import tools as _tools
                            tool_result = await _tools.run_tool(dt.get('name'), dt.get('args', {}) or {})
                        except Exception as _te:
                            tool_result = {"error": str(_te)}
                        prompt = prompt + "\n\n[Tool call executed] tool=%s args=%s result=%s\nPlease answer the user's request using the tool result where useful." % (
                            dt.get('name'), json.dumps(dt.get('args', {}) or {}, ensure_ascii=False), json.dumps(tool_result, ensure_ascii=False)
                        )
                        logging.info("[BRIDGE] decide_tool triggered tool=%s", dt.get('name'))
                except Exception as _e:
                    logging.info("[BRIDGE] decide_tool hook failed: %s", _e)
        except Exception:
            pass

        # If rule-based prefilter didn't run or didn't indicate a tool, fall back
        # to the planner model which may decide to call a tool.
        try:
            planner_aug = await try_use_tools(prompt)
            if planner_aug:
                logging.info("[BRIDGE] planner augmented prompt used")
                prompt = planner_aug
        except Exception as _e:
            logging.info("[BRIDGE] planner check failed: %s", _e)

        kevin = await call_kevin(prompt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"KEVIN error: {e}")

    # KEVIN may return different shapes. If KEVIN signals a command (e.g. {type: 'command', action: '...'}),
    # create a pending action for GUI confirmation and surface that to the client.
    try:
        if isinstance(kevin, dict) and kevin.get("type") == "command":
            cmd = kevin.get("action")
            # create a pending action that the GUI must confirm
            action_id = str(uuid.uuid4())
            pending_actions[action_id] = {"action": {"kind": "run_raw", "args": {"cmd": cmd}}, "created_at": asyncio.get_running_loop().time()}
            # include KEVIN's response text (user-friendly) if present
            user_facing = kevin.get("response") or kevin.get("message") or "ALICE requests to run a command"
            prompt_text = f"ALICE requests to run: {cmd}"
            return {"id": session_id, "raw": user_facing, "text": user_facing, "tags": [], "action_required": True, "action_id": action_id, "action_prompt": prompt_text, "used_alice": False}

        # If KEVIN returned a tool-call request, run the requested tool and re-query KEVIN
        async def _handle_potential_tool_in_kevin(kevin_obj):
            # Return the final kevin-like object after optionally running a tool
            # Allow two tool call iterations to avoid loops
            max_rounds = 2
            current = kevin_obj
            for _ in range(max_rounds):
                tool_request = None
                # Common shapes: dict with 'tool_call' or {'type':'tool','tool':{name,args}} or text containing JSON
                if isinstance(current, dict):
                    if 'tool_call' in current and isinstance(current['tool_call'], dict):
                        tool_request = current['tool_call']
                    elif current.get('type') in ('tool', 'tool_call') and isinstance(current.get('tool'), dict):
                        tool_request = current.get('tool')
                    elif 'tool' in current and isinstance(current.get('tool'), dict):
                        tool_request = current.get('tool')
                else:
                    # try to parse JSON embedded in text
                    try:
                        parsed = json.loads(str(current))
                        if isinstance(parsed, dict) and isinstance(parsed.get('tool'), dict):
                            tool_request = parsed.get('tool')
                    except Exception:
                        tool_request = None

                if not tool_request:
                    break

                name = tool_request.get('name')
                args = tool_request.get('args', {}) or {}
                try:
                    import tools as _tools
                    tool_result = await _tools.run_tool(name, args)
                except Exception as e:
                    tool_result = {"error": str(e)}

                # Append tool result to original prompt and ask KEVIN to produce a final answer
                followup = prompt + "\n\nTool call result for %s: %s\nPlease answer the original question again using the tool result where useful." % (name, json.dumps(tool_result))
                try:
                    current = await call_kevin(followup)
                except Exception:
                    # if KEVIN failed on followup, return the tool result as final
                    return {"response": json.dumps(tool_result), "tool_result": tool_result}

            return current

        final_kevin = await _handle_potential_tool_in_kevin(kevin)
        raw = final_kevin.get("response", "") if isinstance(final_kevin, dict) else str(final_kevin)
        tags, text = extract_tags_and_text(raw)
        return {"id": session_id, "raw": raw, "text": text, "tags": tags, "used_alice": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bridge postprocess error: {e}")


def split_commands(text: str) -> list:
    """Split user input into smaller commands (copied/lightweight from ALICE)."""
    if not isinstance(text, str):
        return []
    quote_pattern = re.compile(r'(".*?"|".*?"|\'.*?\')')
    # Fallback simple splitter if regex fails
    try:
        # Protect quoted substrings by masking them
        quote_pattern = re.compile(r'(".*?"|\'.*?\')')
    except Exception:
        quote_pattern = re.compile(r'(".*?"|\'.*?\')')

    masks = {}
    def _mask(m):
        key = f"__Q{len(masks)}__"
        masks[key] = m.group(0)
        return key

    masked = quote_pattern.sub(_mask, text)

    if '\n' in masked or ';' in masked:
        parts = re.split(r'[\n;]+', masked)
    else:
        if re.search(r'\band then\b|\bthen\b', masked, flags=re.I):
            parts = re.split(r'\band then\b|\bthen\b', masked, flags=re.I)
        else:
            parts = re.split(r'\band\b', masked, flags=re.I)

    restored = []
    for p in parts:
        if not p:
            continue
        for k, v in masks.items():
            if k in p:
                p = p.replace(k, v)
        p = p.strip()
        if p:
            restored.append(p)
    return restored


@app.post("/bridge/alice")
async def bridge_alice(request: 'Request', body: dict = None):
    """Endpoint the GUI can call to send text to ALICE logic. This bridge implements
    its own lightweight command detection and execution (does not modify ALICE.py).
    """
    require_api_key(request)
    # body may be provided directly (test harness) or needs to be read from the request.
    # Read raw body and log a truncated preview for diagnostics, then attempt to parse JSON
    if body is None:
        try:
            raw_bytes = await request.body()
            try:
                raw_text = raw_bytes.decode('utf-8')
            except Exception:
                raw_text = str(raw_bytes)
            if len(raw_text) > 2000:
                preview = raw_text[:2000] + '...<truncated>'
            else:
                preview = raw_text
            logging.info('[BRIDGE RAW BODY] %s', preview)
            print(f"[BRIDGE RAW BODY] {preview}")
            try:
                body = json.loads(raw_text)
            except Exception:
                body = None
        except Exception:
            body = None

    # Normalize text and confirmation keys from various frontends
    if isinstance(body, dict):
        # Support structured payloads from the Amica frontend: { system, messages } or compact { system, user }
        if ('system' in body) or ('messages' in body) or ('user' in body):
            structured_system = body.get('system') or ''
            # compact single-user message payloads: { user: '...' }
            if 'user' in body and body.get('user'):
                user_text = body.get('user')
            else:
                msgs = body.get('messages') or []
                user_parts = []
                try:
                    for m in msgs:
                        if isinstance(m, dict) and m.get('role') == 'user' and m.get('content'):
                            user_parts.append(m.get('content'))
                except Exception:
                    pass
                user_text = '\n'.join(user_parts) if user_parts else (body.get('text') or '')

            # combine system+user for raw_text but keep user_text separate for routing
            raw_text = (structured_system.strip() + '\n\n' + user_text.strip()).strip() if structured_system else user_text
            confirm = bool(body.get('confirm', False) or body.get('confirmed', False))
        else:
            raw_text = body.get('text') or body.get('message') or body.get('input') or body.get('query') or body.get('content') or ''
            confirm = bool(body.get('confirm', False) or body.get('confirmed', False))
    else:
        # Non-dict body, treat as raw text
        try:
            raw_text = str(body)
        except Exception:
            raw_text = ''
        confirm = False

    # Separate system prompt (if present) from user text so the bridge doesn't treat
    # frontend system/assistant lines as user input to be split and forwarded.
    system_text = ''
    user_text = ''
    try:
        # If the Amica system prompt is known and embedded, strip it out
        if AMICA_SYSTEM_PROMPT and isinstance(raw_text, str) and AMICA_SYSTEM_PROMPT in raw_text:
            system_text = (system_text + ' ' + AMICA_SYSTEM_PROMPT).strip()
            raw_text = raw_text.replace(AMICA_SYSTEM_PROMPT, '')

        # Remove explicit role-prefixed lines (System:, Assistant:, User:, etc.)
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
        role_prefix_re = re.compile(r'^(system|assistant|user|jarvis|kevin|alice)\s*[:\-]\s*', flags=re.I)
        user_lines = [role_prefix_re.sub('', l).strip() for l in lines if re.match(r'^\s*user\s*[:\-]', l, flags=re.I)]
        removed_system_lines = [role_prefix_re.sub('', l).strip() for l in lines if re.match(r'^\s*(system|assistant|kevin|alice|jarvis)\s*[:\-]', l, flags=re.I)]
        if removed_system_lines:
            system_text = (system_text + ' ' + ' '.join(removed_system_lines)).strip()

        if user_lines:
            user_text = ' '.join(user_lines)
        else:
            filtered = [role_prefix_re.sub('', l).strip() for l in lines if not re.match(r'^\s*(system|assistant|kevin|alice|jarvis)\s*[:\-]', l, flags=re.I)]
            if filtered:
                user_text = ' '.join(filtered)
            else:
                user_text = lines[-1] if lines else raw_text

        # Debug visibility
        try:
            logging.info('[BRIDGE] raw_text=%s system_text=%s user_text=%s', raw_text, system_text, user_text)
            print(f"[BRIDGE] raw_text={raw_text!r} system_text={system_text!r} user_text={user_text!r}")
        except Exception:
            pass
    except Exception:
        user_text = raw_text

    # Debug log lines to return to GUI for diagnostic display
    debug_lines = []
    debug_id = str(int(time.time()))
    # Terminal debug: log receipt for local troubleshooting
    try:
        logging.info("[BRIDGE] /bridge/alice received raw_text=%s confirm=%s", raw_text, confirm)
        print(f"[BRIDGE] /bridge/alice received raw_text={raw_text!r} confirm={confirm}")
    except Exception:
        pass
    try:
        tags, _ = extract_tags_and_text(raw_text)
    except Exception:
        tags = []
    # Basic receive message log (use raw_text here)
    debug_lines.append(f"info{debug_id}receiveMessageFromUser {raw_text}")
    # Model emotion requests: add debug lines for any recognized emotion tags
    try:
        # canonical allowed emotions (same as extract_tags_and_text uses)
        ALLOWED_EMOTIONS = [
            "neutral", "happy", "angry", "sad", "relaxed", "Surprised",
            "Shy", "Jealous", "Bored", "Serious", "Suspicious", "Victory",
            "Sleep", "Love"
        ]
        for t in tags:
            # if tag is a recognized allowed emotion, report canonical form
            if isinstance(t, str) and any(t.lower() == ae.lower() for ae in ALLOWED_EMOTIONS):
                # Find canonical capitalization from list
                canon = next((ae for ae in ALLOWED_EMOTIONS if ae.lower() == t.lower()), t)
                debug_lines.append(f"debug{debug_id}model.playEmotion: requested expression -> {canon}")
            else:
                # generic tag reported
                debug_lines.append(f"debug{debug_id}model.playEmotion: requested expression -> {t}")
    except Exception:
        pass

    if contains_destructive_command(user_text) and not confirm:
        # create pending action and return for explicit confirmation
        action_id = str(uuid.uuid4())
        # Use the cleaned user_text (was previously `text` which may be undefined)
        pending_actions[action_id] = {"action": {"kind": "run_raw", "args": {"cmd": user_text}}, "created_at": asyncio.get_running_loop().time()}
        return {"status": "needs_confirmation", "message": "This looks potentially destructive. Resend with confirm=true to execute.", "action_id": action_id}

    # Split only the user text into commands (do not split system prompt lines)
    parts = split_commands(user_text)
    command_results = []
    assistant_texts = []

    # lightweight agent for shell execution when requested
    try:
        import agents
        _dry = os.environ.get("AGENT_DRY_RUN", "true").lower() not in ("0", "false", "no")
        local_agent = agents.TerminalAgent(dry_run=_dry)
    except Exception:
        local_agent = None

    for part in parts:
        p = part.strip()
        if not p:
            continue

        # If the ALICE module is available, prefer using its intent analysis
        # and routing so the bridge executes commands the same way as ALICE.
        try:
            alice = get_alice()
            # Provide extra diagnostics when debugging so we can see why ALICE
            # isn't being used (import failure or missing attrs).
            if os.environ.get("DEBUG_BRIDGE", "0") == "1":
                try:
                    logging.info("[BRIDGE DEBUG] loop get_alice() -> %r", alice)
                    logging.info("[BRIDGE DEBUG] _ALICE_IMPORT_ERROR=%r", _ALICE_IMPORT_ERROR)
                    if alice is not None:
                        logging.info("[BRIDGE DEBUG] loop alice dir: %s", sorted(dir(alice)))
                except Exception:
                    pass

            if alice and hasattr(alice, 'execute_routed_command') and (hasattr(alice, 'context_manager') or hasattr(alice, 'context_mgr')):
                # Ensure a context manager instance exists on the alice module
                if not getattr(alice, 'context_mgr', None):
                    try:
                        alice.context_mgr = alice.context_manager.ContextManager()
                    except Exception:
                        alice.context_mgr = None

                if getattr(alice, 'context_mgr', None):
                    try:
                        # Terminal debug: ALICE module and context manager present
                        logging.info("[BRIDGE] ALICE module loaded; context_mgr present")
                        print("[BRIDGE] ALICE module loaded; context_mgr present")
                        intent = None
                        try:
                            intent = alice.context_mgr.analyze_intent(p)
                        except Exception:
                            intent = None
                        entities = None
                        try:
                            entities = alice.context_mgr.extract_entities(p)
                        except Exception:
                            entities = None
                        routed = None
                        try:
                            routed = alice.context_mgr.route_command(p, intent, entities)
                        except Exception:
                            routed = None

                        if routed:
                            # Terminal debug: routed command detected
                            logging.info("[BRIDGE] routed command=%s intent=%s entities=%s", routed, intent, entities)
                            print(f"[BRIDGE] routed command={routed} intent={intent} entities={entities}")
                            # Surface intent/route diagnostics to the GUI debug log so users
                            # can see what ALICE's context manager produced.
                            try:
                                debug_lines.append(f"debug{debug_id}intent: intent={intent} entities={entities} routed={routed}")
                            except Exception:
                                pass
                            # Execute the routed command using ALICE's executor so behavior matches
                            try:
                                # Terminal debug: about to call execute_routed_command
                                logging.info("[BRIDGE] calling alice.execute_routed_command")
                                print("[BRIDGE] calling alice.execute_routed_command")
                                resp = alice.execute_routed_command(routed, p, alice.context_mgr)
                                # Record result in both command_results and debug_lines for visibility
                                try:
                                    command_results.append({"query": p, "response": resp})
                                except Exception:
                                    pass
                                try:
                                    debug_lines.append(f"debug{debug_id}routedCommand: routed={routed} resp={resp}")
                                except Exception:
                                    pass
                                # If the routed command was handled, continue to next part
                                # Terminal debug: execute_routed_command returned
                                logging.info("[BRIDGE] execute_routed_command returned: %s", resp)
                                print(f"[BRIDGE] execute_routed_command returned: {resp}")
                                continue
                            except Exception as e:
                                # Record error for GUI diagnostics and fall through to other handlers
                                try:
                                    debug_lines.append(f"error{debug_id}routedCommandError: {e}")
                                except Exception:
                                    pass
                                # Fall through to other handlers on error
                                pass
                    except Exception:
                        pass
        except Exception:
            # If anything goes wrong, fall back to existing local parsing below
            pass

        # run shell shorthand
        m = re.match(r'^\s*(?:run\s+shell|run)\s*:\s*(.+)$', p, flags=re.I)
        if m:
            cmd = m.group(1).strip()
            if not confirm:
                action_id = str(uuid.uuid4())
                pending_actions[action_id] = {"action": {"kind": "run_raw", "args": {"cmd": cmd}}, "created_at": asyncio.get_running_loop().time()}
                return {"status": "needs_confirmation", "message": "Command requires confirmation", "action_id": action_id}
            # if allowed, execute via agent or subprocess
            try:
                if local_agent:
                    res = local_agent.run(cmd, require_confirmation=False)
                    ok = res.get('ok') if isinstance(res, dict) else False
                    out = res.get('stdout') if isinstance(res, dict) else str(res)
                    command_results.append({"query": p, "response": out, "ok": ok})
                else:
                    subprocess.Popen(shlex.split(cmd), close_fds=True)
                    command_results.append({"query": p, "response": "launched"})
            except Exception as e:
                command_results.append({"query": p, "response": f"error: {e}"})
            continue

        # open program
        mo = re.match(r'^\s*(?:open|start)\s+(.+)$', p, flags=re.I)
        if mo:
            prog = mo.group(1).strip()
            alice = get_alice()
            if alice:
                try:
                    resp = alice.open_program(prog)
                    command_results.append({"query": p, "response": resp})
                except Exception as e:
                    command_results.append({"query": p, "response": f"error: {e}"})
            else:
                # ALICE not available locally; try to open the program directly as a fallback.
                try:
                    # Map a few common friendly program names to executables on Windows
                    mapped_prog = prog
                    try:
                        if os.name == "nt":
                            low = prog.strip().lower()
                            if low in ("calculator", "calc"):
                                mapped_prog = "calc.exe"
                            elif low in ("notepad", "texteditor"):
                                mapped_prog = "notepad.exe"
                            elif low in ("powershell", "powershell.exe"):
                                mapped_prog = "powershell.exe"
                    except Exception:
                        mapped_prog = prog

                    # First try to launch the program name directly (works for executables like "calc.exe").
                    try:
                        subprocess.Popen(shlex.split(mapped_prog), close_fds=True)
                        command_results.append({"query": p, "response": "launched (fallback)"})
                    except Exception:
                        # Try os.startfile (Windows default-association open)
                        try:
                            os.startfile(mapped_prog)
                            command_results.append({"query": p, "response": "launched (startfile)"})
                        except Exception:
                            # Last resort: use shell-start on Windows or shell execution on Unix
                            if os.name == "nt":
                                try:
                                    subprocess.Popen(["cmd", "/c", "start", "", mapped_prog], shell=False)
                                    command_results.append({"query": p, "response": "launched (cmd start)"})
                                except Exception as e:
                                    command_results.append({"query": p, "response": f"error: {e}"})
                            else:
                                try:
                                    subprocess.Popen(mapped_prog, shell=True)
                                    command_results.append({"query": p, "response": "launched (shell)"})
                                except Exception as e:
                                    command_results.append({"query": p, "response": f"error: {e}"})
                except Exception as e:
                    command_results.append({"query": p, "response": f"error: {e}"})
            continue

        # close program
        mc = re.match(r'^\s*(?:close|stop|kill)\s+(.+)$', p, flags=re.I)
        if mc:
            prog = mc.group(1).strip()
            alice = get_alice()
            if alice:
                try:
                    resp = alice.close_program(prog)
                    command_results.append({"query": p, "response": resp})
                except Exception as e:
                    command_results.append({"query": p, "response": f"error: {e}"})
            else:
                command_results.append({"query": p, "response": "error: ALICE module not available (import failed)"})
            continue

        # fallback: send to KEVIN for chat
        try:
            # Debug: log making and handling stream
            debug_lines.append(f"debug{debug_id}receiveMessageFromUser: making and handling stream {json.dumps({'messagesCount': 2})}")
            # Debug: build outgoing chat payload (include system_text only when present)
            sys_content = system_text if system_text else AMICA_SYSTEM_PROMPT if AMICA_SYSTEM_PROMPT else "You are an assistant."
            chat_payload = [{"role": "system", "content": sys_content}, {"role": "user", "content": p}]
            try:
                debug_lines.append(f"debug{debug_id}getChatResponseStream {json.dumps(chat_payload)}")
            except Exception:
                pass
            # Prepend system_text to the single-part prompt sent to KEVIN, only when present
            kevin_prompt = (sys_content + "\n\n" + p) if sys_content else p
            # Quick rule-based decide_tool check (use ALICE context manager if available)
            try:
                alice = get_alice()
                if alice and getattr(alice, 'context_mgr', None) and hasattr(alice.context_mgr, 'decide_tool'):
                    try:
                        dt = alice.context_mgr.decide_tool(p)
                        if dt and isinstance(dt, dict) and dt.get('name'):
                            try:
                                import tools as _tools
                                tool_result = await _tools.run_tool(dt.get('name'), dt.get('args', {}) or {})
                            except Exception as _te:
                                tool_result = {"error": str(_te)}
                            kevin_prompt = kevin_prompt + "\n\n[Tool call executed] tool=%s args=%s result=%s\nPlease answer the user's request using the tool result where useful." % (
                                dt.get('name'), json.dumps(dt.get('args', {}) or {}, ensure_ascii=False), json.dumps(tool_result, ensure_ascii=False)
                            )
                            logging.info("[BRIDGE] bridge_alice decide_tool triggered tool=%s", dt.get('name'))
                    except Exception as _e:
                        logging.info("[BRIDGE] bridge_alice decide_tool hook failed: %s", _e)
            except Exception:
                pass

            kevin = await call_kevin(kevin_prompt)
            raw = kevin.get("response", "") if isinstance(kevin, dict) else str(kevin)
            tags, txt = extract_tags_and_text(raw)
            assistant_texts.append(txt)
        except Exception as e:
            # Report KEVIN error in both assistant_texts and debug lines
            err_msg = str(e)
            debug_lines.append(f"error{debug_id}Error: KEVIN chat error ({err_msg})")
            assistant_texts.append(f"KEVIN error: {e}")
            debug_lines.append(f"debug{debug_id}receiveMessageFromUser: makeAndHandleStream result Error: KEVIN chat error ({err_msg})")

    assistant_text = "\n".join(assistant_texts)
    # Include debug lines so GUI can display the internal debug trace
    response_obj = {"status": "ok", "assistant_text": assistant_text, "command_results": command_results, "debug_log": debug_lines}
    # If the frontend requested a specific personality (e.g., cortana or alice),
    # include the canonical allowed emotions list so the frontend/model can trigger correctly.
    try:
        if isinstance(body, dict):
            persona = (body.get('personality') or body.get('persona') or body.get('model') or '').lower()
            if persona in ("cortana", "alice"):
                response_obj['allowed_emotions'] = [
                    "neutral", "happy", "angry", "sad", "relaxed", "Surprised",
                    "Shy", "Jealous", "Bored", "Serious", "Suspicious", "Victory",
                    "Sleep", "Love"
                ]
    except Exception:
        pass

    # When debugging is enabled, include ALICE import diagnostics in the response
    try:
        if os.environ.get("DEBUG_BRIDGE", "0") == "1":
            try:
                if _ALICE_IMPORT_ERROR:
                    response_obj.setdefault('debug_log', []).append(f"debug_import_error: {_ALICE_IMPORT_ERROR}")
            except Exception:
                pass
            try:
                # Surface current alice module dir to GUI for quick inspection
                alice_tmp = get_alice()
                if alice_tmp is None:
                    response_obj.setdefault('debug_log', []).append("debug_alice: None (import failed)")
                else:
                    try:
                        response_obj.setdefault('debug_log', []).append(f"debug_alice_dir: {sorted(dir(alice_tmp))}")
                    except Exception:
                        response_obj.setdefault('debug_log', []).append(f"debug_alice_repr: {repr(alice_tmp)}")
            except Exception:
                pass
    except Exception:
        pass

    return response_obj


@app.post("/bridge/amicalife")
async def bridge_amicalife(request: 'Request', body: dict = None):
    """Adapter endpoint for Amica Life autonomous events.

    Frontend can POST JSON like { event: 'News'|'VRMA'|'Subconcious'|'IdleTextPrompts'|'UserMessage', text?: string, meta?: {...} }
    This endpoint will forward any provided text to the shared `query_endpoint` (which tries ALICE first,
    then KEVIN) so Amica Life events can trigger assistant automations.
    """
    require_api_key(request)
    if body is None:
        try:
            raw_bytes = await request.body()
            try:
                raw_text = raw_bytes.decode('utf-8')
            except Exception:
                raw_text = str(raw_bytes)
            if len(raw_text) > 2000:
                preview = raw_text[:2000] + '...<truncated>'
            else:
                preview = raw_text
            logging.info('[BRIDGE RAW BODY amicalife] %s', preview)
            try:
                body = json.loads(raw_text)
            except Exception:
                body = None
        except Exception:
            body = None

    # Normalize
    if isinstance(body, dict):
        event = body.get('event') or body.get('events') or body.get('type') or 'UserMessage'
        text = body.get('text') or body.get('message') or body.get('prompt') or ''
    else:
        event = 'UserMessage'
        try:
            text = str(body)
        except Exception:
            text = ''

    logging.info('[BRIDGE] /bridge/amicalife event=%s text=%s', event, (text[:200] + '...') if len(text) > 200 else text)

    # Provide lightweight mapping for common Amica Life events when no explicit text provided
    if not text:
        if isinstance(event, str) and event.lower() == 'news':
            text = 'news'
        elif isinstance(event, str) and event.lower() in ('idletextprompts', 'idletext', 'text'):
            # Nothing specific; return early — frontend should include the prompt to route
            return {"status": "ok", "event": event, "message": "no text provided to route"}

    # If we have text, leverage existing query handling (ALICE-first) by constructing a QueryRequest
    if text:
        try:
            qreq = QueryRequest(text=text)
            res = await query_endpoint(qreq, request)
            return {"status": "ok", "event": event, "result": res}
        except HTTPException:
            raise
        except Exception as e:
            logging.warning('[BRIDGE] /bridge/amicalife forward failed: %s', e)
            # Fall back to KEVIN directly if necessary
            try:
                kevin = await call_kevin(text)
                raw = kevin.get('response', '') if isinstance(kevin, dict) else str(kevin)
                tags, txt = extract_tags_and_text(raw)
                return {"status": "ok", "event": event, "result": {"raw": raw, "text": txt, "tags": tags, "used_alice": False}}
            except Exception as e2:
                logging.error('[BRIDGE] /bridge/amicalife kevin fallback failed: %s', e2)
                raise HTTPException(status_code=500, detail=f"amicalife forward error: {e}")

    return {"status": "ok", "event": event, "message": "no action taken"}

@app.post("/action/request")
async def action_request(action: ActionRequest, request: 'Request'):
    require_api_key(request)
    if action.kind not in ACTION_WHITELIST:
        raise HTTPException(status_code=400, detail="Action not allowed")
    action_id = str(uuid.uuid4())
    # store the pending action and return a prompt for the GUI to show user
    pending_actions[action_id] = {"action": action.dict(), "created_at": asyncio.get_running_loop().time()}
    prompt = f"ALICE requests to perform: {action.kind}"
    # include friendly description
    if action.kind == "open_url":
        prompt = f"ALICE requests to open URL: {action.args.get('url')}"
    return {"action_id": action_id, "prompt": prompt}


@app.get("/bridge/commands")
async def bridge_commands(request: 'Request'):
    """Return a summary of commands and bridge-related options available to callers.

    Requires the bridge API key. This helps frontends list available actions
    (including preapproved run mappings) and boolean flags like whether raw
    commands are allowed.
    """
    # Validate API key first and return the standard FastAPI HTTPException when missing
    require_api_key(request)

    # Build a defensive, serializable response and avoid letting malformed
    # environment variables cause an unhandled exception.
    try:
        run_allowlist = os.environ.get("RUN_ALLOWLIST", "")
        run_allowlist_list = [p.strip() for p in run_allowlist.split(",") if p.strip()]

        run_map_json = os.environ.get("RUN_MAP_JSON")
        run_map = {}
        run_map_error = None
        if run_map_json:
            try:
                run_map = json.loads(run_map_json)
                if not isinstance(run_map, dict):
                    run_map_error = "RUN_MAP_JSON did not decode to an object"
                    run_map = {}
            except Exception as exc:
                run_map_error = f"invalid RUN_MAP_JSON: {exc}"
                run_map = {}

        commands = {
            "allowed_actions": sorted(list(ACTION_WHITELIST)),
            "run_preapproved": {
                "enabled": bool(run_map_json) and not run_map_error,
                "allowlist": run_allowlist_list,
                "mappings": run_map,
            },
            "allow_raw_commands": os.environ.get("ALLOW_RAW_COMMANDS", "0") == "1",
            "alice_exec_path": ALICE_EXEC_PATH or "",
            "endpoints": ["/query", "/bridge/alice", "/bridge/amicalife", "/action/request", "/action/confirm", "/ws/{session_id}"],
        }

        if run_map_error:
            # Include a lightweight, non-sensitive error hint to help debugging
            commands.setdefault('diagnostics', {})['run_map_error'] = run_map_error

        return JSONResponse(status_code=200, content=commands)
    except HTTPException:
        # propagate FastAPI HTTP errors (auth etc.) unchanged
        raise
    except Exception as e:
        # Log full exception for server-side debugging, but return a compact
        # JSON error to the client to avoid crashing with an unhandled 500.
        logging.exception("/bridge/commands failed: %s", e)
        detail = "internal bridge error"
        if os.environ.get("DEBUG_BRIDGE", "0") == "1":
            # When debugging is enabled, surface the exception message (non-sensitive)
            detail = str(e)
        return JSONResponse(status_code=500, content={"error": detail})

async def execute_action(kind: str, args: Dict[str, Any]):
    """Execute a single whitelisted action; returns a dict result or raises HTTPException."""
    # Keep logic the same as before but factored out so it can be invoked from a CLI/test harness
    try:
        if kind == "open_url":
            import webbrowser
            url = args.get("url")
            if not url:
                raise ValueError("missing url")
            webbrowser.open(url)
            return {"status": "ok"}

        if kind == "open_file":
            path = args.get("path")
            if not path:
                raise ValueError("missing path")
            # on Windows this will open with default associated app
            os.startfile(path)
            return {"status": "ok"}

        if kind == "run_preapproved":
            allowlist = os.environ.get("RUN_ALLOWLIST", "")
            allowed = [p.strip() for p in allowlist.split(",") if p.strip()]
            cmd_key = args.get("cmd_key")
            if cmd_key not in allowed:
                raise HTTPException(status_code=403, detail="command not allowed")
            run_map_json = os.environ.get("RUN_MAP_JSON")
            if not run_map_json:
                raise HTTPException(status_code=500, detail="run map not configured")
            run_map = json.loads(run_map_json)
            cmd = run_map.get(cmd_key)
            if not cmd:
                raise HTTPException(status_code=404, detail="command mapping not found")
            subprocess.Popen(shlex.split(cmd), close_fds=True)
            return {"status": "ok"}

        if kind == "screenshot":
            try:
                from PIL import ImageGrab
                im = ImageGrab.grab()
                out = f"screenshot_{uuid.uuid4().hex}.png"
                im.save(out)
                return {"status": "ok", "file": out}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        if kind == "run_raw":
            cmd = args.get("cmd")
            if not cmd:
                raise HTTPException(status_code=400, detail="missing cmd")
            allow_raw = os.environ.get("ALLOW_RAW_COMMANDS", "0") == "1"
            if not allow_raw:
                raise HTTPException(status_code=403, detail="raw command execution disabled; use run_preapproved or enable ALLOW_RAW_COMMANDS=1")
            try:
                subprocess.Popen(shlex.split(cmd), close_fds=True)
                return {"status": "ok"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        if ALICE_EXEC_PATH:
            payload = {"kind": kind, "args": args}
            p = subprocess.Popen([ALICE_EXEC_PATH], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = p.communicate(json.dumps(payload).encode("utf-8"))
            try:
                return json.loads(stdout.decode("utf-8"))
            except Exception:
                return {"status": "ok", "raw_stdout": stdout.decode("utf-8"), "stderr": stderr.decode("utf-8")}

        raise HTTPException(status_code=400, detail="unsupported action")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/action/confirm") if HAS_FASTAPI else (lambda f: f)
async def action_confirm(body: Dict[str, Any], request: 'Request'):
    require_api_key(request)
    action_id = body.get("action_id")
    ok = bool(body.get("ok"))
    if not action_id:
        raise HTTPException(status_code=400, detail="missing action_id")
    action_entry = pending_actions.pop(action_id, None)
    if not action_entry:
        raise HTTPException(status_code=404, detail="not found")
    if not ok:
        return {"status": "cancelled"}
    action = action_entry["action"]
    kind = action.get("kind")
    args = action.get("args", {})
    return await execute_action(kind, args)

# ---------- WebSocket streaming endpoint ----------
@app.websocket("/ws/{session_id}")
async def ws_stream(websocket, session_id: str):
    # Note: in production you might verify headers or an initial auth message
    await websocket.accept()
    q: asyncio.Queue = asyncio.Queue()
    sessions[session_id] = q
    try:
        while True:
            # Wait for either queue item or client message
            done, pending = await asyncio.wait(
                [asyncio.create_task(q.get()), asyncio.create_task(websocket.receive_text())],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in done:
                try:
                    res = task.result()
                except Exception:
                    continue
                if isinstance(res, dict):
                    # frame coming from server side
                    await websocket.send_text(json.dumps(res))
                else:
                    # client message
                    try:
                        msg = json.loads(res)
                    except Exception:
                        continue
                    # handle control messages from client
                    cmd = msg.get("cmd")
                    if cmd == "query":
                        prompt = msg.get("text", "")
                        # spawn stream worker
                        asyncio.create_task(handle_query_stream(prompt, session_id))
                    elif cmd == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        sessions.pop(session_id, None)

async def handle_query_stream(prompt: str, session_id: str):
    q = sessions.get(session_id)
    if not q:
        return
    try:
        kevin = await call_kevin(prompt)
        raw = kevin.get("response", "")
        tags, text = extract_tags_and_text(raw)
        # naive sentence split
        parts = re.split(r"(?<=[.!?])\s+", text)
        for i, part in enumerate(parts):
            frame = {"type": "text", "chunk": part, "is_final": False, "tags": tags}
            await q.put(frame)
            await asyncio.sleep(0.05)
        # final
        await q.put({"type": "text", "is_final": True, "full_text": text, "tags": tags})
    except Exception as e:
        await q.put({"type": "error", "error": str(e)})

# ---------- Basic CLI helpers so script can be launched directly ----------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8700)
    parser.add_argument("--selftest", action="store_true", help="Run a lightweight self-test of action execution without starting the FastAPI server")
    args = parser.parse_args()

    if args.selftest:
        # Run a simple self-test that exercises action execution (open URL)
        print("Running bridge self-test (execute_action open_url)")
        try:
            import asyncio as _asyncio
            res = _asyncio.run(execute_action("open_url", {"url": "http://example.com"}))
            print("Self-test result:", res)
            print("Self-test completed — check whether your browser opened http://example.com")
        except Exception as e:
            print("Self-test failed:", e)
        raise SystemExit(0)

    print("Starting Amica-ALICE Bridge on http://%s:%d (api_key in BRIDGE_API_KEY)" % (args.host, args.port))
    # run with uvicorn when launched directly
    try:
        import uvicorn
        # Optionally attempt to free ports on Windows before starting (controlled by BRIDGE_PORT_FREE)
        try:
            if os.environ.get('BRIDGE_PORT_FREE', '').lower() in ('1', 'true', 'yes'):
                dry = os.environ.get('BRIDGE_PORT_FREE_DRY', '').lower() in ('1', 'true', 'yes')
                ports = [args.port]
                logging.info('[BRIDGE PORT-FREE] env requested, dry=%s ports=%s', dry, ports)
                _free_ports_on_windows(ports, dry_run=dry)
        except Exception:
            pass
        # Pass the app object directly to uvicorn.run instead of the "module:app" string.
        # Using the string causes the module to be imported again (double-execution when
        # running the file as a script) which can lead to unexpected startup/shutdown.
        if not HAS_FASTAPI:
            print("FastAPI not installed; cannot run server. Use --selftest to exercise actions without the server.")
            raise SystemExit(1)
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    except Exception as e:
        print("Run uvicorn to serve this app. Example:\n  uvicorn amica_alice_bridge:app --host 127.0.0.1 --port 8700 --reload")
