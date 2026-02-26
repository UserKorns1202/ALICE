import threading
import subprocess
import random
try:
    import speech_recognition as sr
except Exception:
    sr = None
import datetime
import sympy as sp
import time
import keyboard  # Added for keyboard event handling
import patterns
#import intent_patterns
import todo
import os
import platform
# Dynamic username for path construction
username = os.getenv("USERNAME") or os.getlogin()
try:
    import pyttsx3
except Exception:
    pyttsx3 = None
import json
try:
    import pytesseract
    from PIL import ImageGrab
    ocr_available = True
except ImportError:
    ocr_available = False
    print("OCR not available, install pytesseract and Pillow")
import search
import queue
try:
    import pygame
except Exception:
    pygame = None
import difflib
import shutil
from game_mode import GameModeContext
from intent_router import route_and_execute
import requests
import re
import docqa
import hot_reload
import remote_access
import user_memory
import dynamic_response
import context_manager
import agents

# Attempt to load Amica frontend config so we can strip its system prompt
AMICA_SYSTEM_PROMPT = None
def _load_amica_system_prompt():
    global AMICA_SYSTEM_PROMPT
    # Candidate locations (relative to this repo)
    candidates = [
        os.path.join(os.path.dirname(__file__), 'Amica', 'Amica-temp', 'src', 'features', 'externalAPI', 'dataHandlerStorage', 'config.json'),
        os.path.join(os.path.dirname(__file__), '..', 'Amica', 'Amica-temp', 'src', 'features', 'externalAPI', 'dataHandlerStorage', 'config.json'),
        os.path.join(os.path.dirname(__file__), 'Amica', 'Amica-temp', 'src', 'features', 'externalAPI', 'dataHandlerStorage', 'config.json'),
    ]
    for p in candidates:
        try:
            if p and os.path.exists(p):
                with open(p, 'r', encoding='utf-8') as f:
                    j = json.load(f)
                    sp = j.get('system_prompt') or j.get('personality_prompt_alice') or j.get('personality_prompt_cortana')
                    if sp and isinstance(sp, str) and sp.strip():
                        AMICA_SYSTEM_PROMPT = sp.strip()
                        print(f"[ALICE] Loaded Amica system_prompt from {p}")
                        return
        except Exception:
            continue

_load_amica_system_prompt()
# Optional lightweight HTTP endpoint so GUI can post messages directly to ALICE_v2.
try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    HAS_FASTAPI = True
except Exception:
    HAS_FASTAPI = False
    FastAPI = None

if HAS_FASTAPI:
    app = FastAPI(title="ALICE_v2 GUI Endpoint")
    # Add permissive CORS so browser-based GUI can call this endpoint
    try:
        from fastapi.middleware.cors import CORSMiddleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    except Exception:
        pass

    @app.post("/gui_input")
    async def gui_input(request: Request):
        """Endpoint to receive GUI chat messages and let ALICE decide to execute or call KEVIN.

        Request JSON: {"text": str, "confirm": bool (optional)}
        Response: JSON with either {'type':'text','response':...} or {'status':'ok','result':...}
        """
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "invalid json"}, status_code=400)
        # (logging of raw request body moved to the bridge module)
        text = body.get('text', '')
        confirm = bool(body.get('confirm', False))

        # Support structured payload from Amica frontend: { system: string, messages: [{role,content}, ...] }
        # Also accept compact payload: { system: string, user: string }
        structured_system = ''
        try:
            if isinstance(body, dict) and ('system' in body or 'messages' in body or 'user' in body):
                structured_system = body.get('system') or ''

                # If frontend provided a compact `user` field, prefer it as the latest user input
                try:
                    compact_user = body.get('user')
                    if isinstance(compact_user, str) and compact_user.strip():
                        last = compact_user.strip()
                        # Strip leading bracketed mood/emotion tags like [neutral], [happy], etc.
                        last = re.sub(r'^\s*\[[^\]]+\]\s*', '', last)
                        text = last
                        # Debug compact path
                        try:
                            print("[ALICE HTTP] compact structured payload received: using 'user' field")
                        except Exception:
                            pass
                    else:
                        msgs = body.get('messages') or []
                        # Debug: show incoming structured messages for diagnosis
                        try:
                            try:
                                print(f"[ALICE HTTP] structured messages received: count={len(msgs)}")
                            except Exception:
                                pass

                            # Collect user messages but prefer only the latest one (avoid resending prior commands)
                            user_parts = [m.get('content') for m in msgs if isinstance(m, dict) and m.get('role') == 'user' and m.get('content')]
                            if user_parts:
                                # Use only the most recent user message
                                last = user_parts[-1].strip()
                                # Strip leading bracketed mood/emotion tags like [neutral], [happy], etc.
                                last = re.sub(r'^\s*\[[^\]]+\]\s*', '', last)
                                text = last
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            structured_system = ''

        # Sanitize input: separate system vs user content so ALICE only processes user input.
        # Start with any structured system prompt provided by the frontend
        system_text = structured_system or ''
        try:
            raw_text = text or ''
            # If Amica's system_prompt is known, strip it out and treat as system_text
            try:
                if AMICA_SYSTEM_PROMPT and isinstance(raw_text, str) and AMICA_SYSTEM_PROMPT in raw_text:
                    system_text = (system_text + ' ' + AMICA_SYSTEM_PROMPT).strip()
                    raw_text = raw_text.replace(AMICA_SYSTEM_PROMPT, '')
            except Exception:
                pass

            lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
            role_prefix_re = re.compile(r'^(system|assistant|user|jarvis|kevin|alice)\s*[:\-]\s*', flags=re.I)
            # Collect explicit user: lines first
            user_lines = [role_prefix_re.sub('', l).strip() for l in lines if re.match(r'^\s*user\s*[:\-]', l, flags=re.I)]
            # Collect any system/assistant lines we removed
            removed_system_lines = [role_prefix_re.sub('', l).strip() for l in lines if re.match(r'^\s*(system|assistant|kevin|alice|jarvis)\s*[:\-]', l, flags=re.I)]
            if removed_system_lines:
                system_text = (system_text + ' ' + ' '.join(removed_system_lines)).strip()

            if user_lines:
                # Prefer explicit User: lines
                user_text = ' '.join(user_lines)
            else:
                # Use any lines that don't look like system/assistant as user content
                filtered = [role_prefix_re.sub('', l).strip() for l in lines if not re.match(r'^\s*(system|assistant|kevin|alice|jarvis)\s*[:\-]', l, flags=re.I)]
                if filtered:
                    # Join non-system lines into one user text (do not treat each line as separate GUI-originated system text)
                    user_text = ' '.join(filtered)
                else:
                    # Fallback: last non-empty line
                    user_text = lines[-1] if lines else raw_text

            # Replace `text` for downstream processing with the cleaned user_text
            text = user_text
            # Debug print raw vs sanitized
            print(f"[ALICE HTTP] raw_text={raw_text!r} system_text={system_text!r} user_text={user_text!r}")
        except Exception:
            # On any error, keep original text and empty system_text
            system_text = ''
            user_text = text

        # Ensure context manager
        try:
            if not getattr(globals(), 'context_mgr', None):
                globals()['context_mgr'] = context_manager.ContextManager()
            ctx = globals().get('context_mgr')
        except Exception as e:
            ctx = None
            print(f"[ALICE HTTP] failed to init context_mgr: {e}")

        # Process input similarly to ALICE.py main loop:
        # - Split into sub-commands
        # - Handle run-shell shorthand
        # - Use context manager to analyze/route and execute commands
        # - Check inline edits / pattern matches
        # - Fallback to KEVIN chat
        responses = []
        try:
            sub_queries = split_commands(text)
            if not sub_queries:
                sub_queries = [text]
        except Exception:
            sub_queries = [text]

        for sub in sub_queries:
            q = sub
            # Run-shell shorthand bypass (e.g., "run: <cmd>")
            try:
                run_match = re.match(r'^\s*(?:run\s+shell|run)\s*:\s*(.+)$', q, flags=re.I)
            except Exception:
                run_match = None
            if run_match:
                cmd = run_match.group(1).strip()
                routed_command = {
                    'action': 'run_shell',
                    'command': cmd,
                    'require_confirmation': True,
                    'use_llm': False,
                }
                try:
                    print(f"[ALICE HTTP] run-shell shorthand detected: {cmd}")
                    res = execute_routed_command(routed_command, q, ctx)
                    responses.append({'type': 'action', 'routed': routed_command, 'result': res})
                    continue
                except Exception as e:
                    print(f"[ALICE HTTP] run-shell error: {e}")

            # Analyze intent and route using context manager
            intent = None
            entities = None
            routed = None
            if ctx:
                try:
                    intent = ctx.analyze_intent(q)
                except Exception:
                    intent = None
                try:
                    entities = ctx.extract_entities(q)
                except Exception:
                    entities = None
                try:
                    routed = ctx.route_command(q, intent, entities)
                except Exception:
                    routed = None

            # If context manager says it's a command, execute it
            if intent == 'command' and routed:
                try:
                    print(f"[ALICE HTTP] routed={routed} intent={intent} entities={entities}")
                    res = execute_routed_command(routed, q, ctx)
                    responses.append({'type': 'action', 'routed': routed, 'result': res})
                    # log and continue to next sub-query
                    continue
                except Exception as e:
                    print(f"[ALICE HTTP] execute_routed_command error: {e}")

            # Instruction handling (learn) or inline edits
            try:
                norm_q = re.sub(r'^(?:plan\s+and\s+execute|plan\s+and\s+run|plan|execute|run|plan\s+execute)\s*:?', '', q, flags=re.I)
            except Exception:
                norm_q = q
            inline_detect = None
            try:
                inline_detect = agents.parse_inline_edit(norm_q)
            except Exception:
                inline_detect = None

            if inline_detect:
                try:
                    routed_command = {'action': 'plan_and_execute', 'instruction': q}
                    res = execute_routed_command(routed_command, q, ctx)
                    responses.append({'type': 'action', 'routed': routed_command, 'result': res})
                    continue
                except Exception as e:
                    print(f"[ALICE HTTP] inline plan_and_execute error: {e}")

            # Pattern matching
            pattern_response = None
            try:
                for pattern, response_func in patterns.query_patterns.items():
                    try:
                        if pattern.match(q.lower()):
                            if callable(response_func):
                                if 'query' in getattr(response_func, '__code__', object()).co_varnames:
                                    pattern_response = response_func(q)
                                else:
                                    pattern_response = response_func()
                            else:
                                pattern_response = response_func
                            break
                    except Exception:
                        continue
            except Exception:
                pattern_response = None

            if pattern_response is not None:
                responses.append({'type': 'text', 'response': pattern_response})
                continue

            # Fast intent router attempt (best-effort)
            try:
                rr = route_and_execute(q)
                if rr is not None:
                    print(f"[ALICE HTTP] intent_router handled input, result={rr!r}")
                    responses.append({'type': 'action', 'routed': {'via': 'intent_router'}, 'result': rr})
                    continue
            except Exception as _e:
                print(f"[ALICE HTTP] intent_router error: {_e}")

            # Fallback to chat with KEVIN (pass any collected system_text separately)
            try:
                agent_info = None
                try:
                    agent_info = {'available': 'agent' in globals() and globals().get('agent') is not None, 'dry_run': getattr(globals().get('agent'), 'dry_run', None)}
                except Exception:
                    agent_info = {'available': False, 'dry_run': None}
                print(f"[ALICE HTTP] forwarding to KEVIN (intent={intent!r}, routed={routed!r}, agent={agent_info}, system_text_present={bool(system_text)})")
                chat_resp = chat_with_kevin(q, speak_to_kevin=False, system_prompt=system_text)
                responses.append({'type': 'text', 'response': chat_resp})
            except Exception as e:
                print(f"[ALICE HTTP] chat_with_kevin failed: {e}")
                responses.append({'type': 'error', 'error': str(e)})

        # Return result: single item => inline, multiple => list
        if not responses:
            return JSONResponse({"error": "no response produced"}, status_code=500)
        if len(responses) == 1:
            return JSONResponse(responses[0])
        return JSONResponse({"results": responses})

    # Compatibility aliases: some frontends call /gui_input/query or expect OPTIONS preflight there
    @app.options("/gui_input/query")
    async def gui_input_options():
        return JSONResponse(status_code=200, content={})

    @app.post("/gui_input/query")
    async def gui_input_query(request: Request):
        # forward to main gui_input handler
        return await gui_input(request)

# Helper to start the ALICE_v2 HTTP endpoint in background (if desired)
def start_alice_http(host: str = '127.0.0.1', port: int = 8701):
    if not HAS_FASTAPI:
        print("[ALICE HTTP] FastAPI not available; cannot start ALICE HTTP endpoint")
        return None
    try:
        import uvicorn
    except Exception:
        print("[ALICE HTTP] uvicorn not installed; install uvicorn to enable ALICE_v2 HTTP endpoint")
        return None

    def _run():
        try:
            # Before starting, attempt to free the port on Windows if in use
            # port-free behavior handled by bridge module when appropriate
            uvicorn.run(app, host=host, port=port, log_level='info')
        except Exception as e:
            print(f"[ALICE HTTP] uvicorn failed: {e}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    print(f"[ALICE HTTP] started on http://{host}:{port}")
    return t

# Add missing imports for volume_control and email_manager
import volume_control
import email_manager

# KEVIN server configuration
KEVIN_URL = os.getenv("KEVIN_URL", "http://127.0.0.1:5000")
# Optional separate chat URL (heavier model); falls back to KEVIN_URL
KEVIN_CHAT_URL = os.getenv("KEVIN_CHAT_URL", KEVIN_URL)

# --- Requirements.txt check and creation ---

# --- Requirements.txt check, creation, and auto-install ---
import sys
REQUIREMENTS_PATH = os.path.join(os.path.dirname(__file__), "requirements.txt")
import_list = [
    "threading", "subprocess", "random", "speechrecognition", "datetime", "sympy", "time", "keyboard",
    "patterns", "todo", "os", "platform", "pyttsx3", "json", "psutil", "search", "queue", "pygame", "difflib", "shutil", "game_mode"
]
import_to_pip = {
    "speechrecognition": "SpeechRecognition",
    "pyttsx3": "pyttsx3",
    "sympy": "sympy",
    "psutil": "psutil",
    "pygame": "pygame",
    "keyboard": "keyboard",
    "datetime": "",
    "threading": "",
    "subprocess": "",
    "random": "",
    "os": "",
    "platform": "",
    "json": "",
    "queue": "",
    "difflib": "",
    "shutil": "",
    "patterns": "",
    "todo": "",
    "search": "",
    "game_mode": ""
}

def write_requirements():
    pkgs = set()
    for lib in import_list:
        pkg = import_to_pip.get(lib, lib)
        if pkg:
            pkgs.add(pkg)
    with open(REQUIREMENTS_PATH, "w") as f:
        for pkg in sorted(pkgs):
            f.write(pkg + "\n")

if not os.path.exists(REQUIREMENTS_PATH):
    write_requirements()

# --- Auto install missing packages ---
import importlib
def robust_import(lib, pip_name):
    try:
        importlib.import_module(lib)
        return True
    except ImportError:
        if pip_name:
            print(f"Attempting to install missing package: {pip_name}")
            import subprocess
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
                # Try import again
                try:
                    importlib.import_module(lib)
                    return True
                except ImportError:
                    print(f"Failed to import {lib} after installing {pip_name}")
                    return False
            except Exception as e:
                print(f"Failed to install {pip_name}: {e}")
                return False
        else:
            # No pip name, skip
            return True

for lib in import_list:
    pip_name = import_to_pip.get(lib, lib)
    if pip_name:
        # Some imports use underscores, but pip uses dashes
        pip_name = pip_name.replace("_", "-")
    if pip_name == "SpeechRecognition":
        continue
    robust_import(lib, pip_name)

import requests
import re
import docqa
import hot_reload
import remote_access
import user_memory
import dynamic_response
import context_manager

# Helper function for word boundary matching to avoid substring edge cases
def word_in_text(word, text):
    """Check if a word appears as a whole word in the text, using word boundaries."""
    return bool(re.search(r'\b' + re.escape(word) + r'\b', text.lower()))


def split_commands(text: str) -> list:
    """Split a user input into separate commands using heuristics.

    Heuristics (in priority):
    - Split on newlines or semicolons if present
    - Split on 'and then' / 'then'
    - Split on 'and' as a last resort
    Quoted substrings (single or double quotes) are protected and won't be split inside.
    Returns a list of trimmed command strings (non-empty).
    """
    if not isinstance(text, str):
        return []

    # Protect quoted substrings by masking them
    quote_pattern = re.compile(r'(".*?"|\'.*?\')')
    masks = {}
    def _mask(m):
        key = f"__Q{len(masks)}__"
        masks[key] = m.group(0)
        return key

    masked = quote_pattern.sub(_mask, text)

    # Choose separators by presence
    if '\n' in masked or ';' in masked:
        parts = re.split(r'[\n;]+', masked)
    else:
        # prefer stronger separators first
        if re.search(r'\band then\b|\bthen\b', masked, flags=re.I):
            parts = re.split(r'\band then\b|\bthen\b', masked, flags=re.I)
        else:
            # last resort split on ' and '
            parts = re.split(r'\band\b', masked, flags=re.I)

    # Restore masked quotes and trim
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

# Global queue for speak requests from threads (max 10 items to prevent memory bloat)
class DeduplicatingQueue:
    """A queue that prevents duplicate messages from being added within a time window."""
    def __init__(self, maxsize=10, dedup_window=300):  # 5 minute deduplication window
        self.queue = queue.Queue(maxsize=maxsize)
        self.recent_messages = {}  # message -> timestamp
        self.dedup_window = dedup_window

    def put_nowait(self, item):
        """Add item to queue, but skip if duplicate within dedup_window."""
        current_time = time.time()

        # Clean old entries from recent_messages
        self.recent_messages = {
            msg: ts for msg, ts in self.recent_messages.items()
            if current_time - ts < self.dedup_window
        }

        # Check if this message was recently added
        if item in self.recent_messages:
            print(f"[Queue] Skipping duplicate message: {item[:50]}...")
            return

        # Add to queue and track
        try:
            self.queue.put_nowait(item)
            self.recent_messages[item] = current_time
        except queue.Full:
            print(f"[Queue] Queue full, dropping message: {item[:50]}...")

    def get(self):
        """Get item from queue."""
        return self.queue.get()

    def empty(self):
        """Check if queue is empty."""
        return self.queue.empty()

    def qsize(self):
        """Get queue size."""
        return self.queue.qsize()

speak_queue = DeduplicatingQueue(maxsize=10)

# Global queue for background listening
query_queue = queue.Queue()

# Planner instance (LLM-based planning helper). Initialized in main().
planner = None
# Path to store the last planned LLM plan for approval/inspection
last_plan_path = os.path.join(os.path.dirname(__file__), "last_plan.json")

# Global list for health alerts to be spoken during inactivity
health_alerts = []

# Global flag to track if currently speaking
is_speaking = False
speak_lock = threading.Lock()
def background_listen():
    """Continuously listen in speaking mode and queue queries."""
    global wake_word
    # Headless background listener: lightweight loop that only polls state.
    print(f"[ALICE] background_listen (headless) wake_word='{wake_word}'")
    while not is_exiting:
        # In headless mode we don't actively capture microphone audio; sleep briefly
        # to allow other threads to run and to respect shutdown.
        time.sleep(1)
    return

game_context = GameModeContext()
game_context.set_speak_queue(speak_queue)

conversation_history = []

def save_conversation_history():
    with open("conversation_history.json", "w") as file:
        json.dump(conversation_history, file)

def load_conversation_history():
    global conversation_history
    try:
        with open("conversation_history.json", "r") as file:
            conversation_history = json.load(file)
    except FileNotFoundError:
        conversation_history = []

engine = pyttsx3.init()
#engine.setProperty('voice', r'HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices\Tokens\TTS_MS_EN-GB_HAZEL_11.0')
engine.setProperty('voice', r'HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices\Tokens\TTS_MS_EN-US_DAVID_11.0')
voices = engine.getProperty('voices')
print(f"Available voices: {[v.name for v in voices]}")
engine = None
if pyttsx3:
    try:
        engine = pyttsx3.init()
        try:
            engine.setProperty('voice', r'HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Speech\\Voices\\Tokens\\TTS_MS_EN-US_DAVID_11.0')
        except Exception:
            pass
        try:
            voices = engine.getProperty('voices') or []
            print(f"Available voices: {[getattr(v, 'name', None) for v in voices]}")
        except Exception:
            pass
    except Exception:
        engine = None
        print("[ALICE] pyttsx3 init failed; TTS disabled")
global input_mode
input_mode = "typing"
global aiModel
global wake_word


def speak(response, force=False, remote_session_id=None):
    """Headless speak stub: ALICE_v2 runs in headless mode when driven by Amica.

    This function intentionally does not perform TTS. It logs the message and
    optionally enqueues it when a speak queue exists so other components can
    observe assistant messages without requiring pyttsx3 or audio playback.
    """
    try:
        # Keep a lightweight log for debugging
        print(f"[ALICE HEADLESS SPEAK]{' (force)' if force else ''}: {str(response)[:200]}")
        # If a speak_queue exists, push into it to preserve previous flow
        if 'speak_queue' in globals() and getattr(globals().get('speak_queue'), 'put_nowait', None):
            try:
                speak_queue.put_nowait(str(response))
            except Exception:
                pass
    except Exception:
        pass


# Remote session tracking
_current_remote_session = None

def set_current_remote_session(session_id: str):
    """Set the current remote session being processed."""
    global _current_remote_session
    _current_remote_session = session_id

def get_current_remote_session() -> str | None:
    """Get the current remote session ID."""
    global _current_remote_session
    return _current_remote_session

def clear_current_remote_session():
    """Clear the current remote session."""
    global _current_remote_session
    _current_remote_session = None

# Dictionary mapping user-friendly program names to their corresponding commands or executable files
program_mapping = {
    "google": "chrome.exe",  # Example: User says "open google", runs "chrome" (Google Chrome)
    "chrome": "chrome.exe",
    "notepad": "notepad.exe",
    "cura": "ultimaker",
    "slicer": "ultimaker",
    "helldivers": "helldivers2",
    "fusion": f"C:\\Users\\{username}\\AppData\\Local\\Autodesk\\webdeploy\\production\\6a0c9611291d45bb9226980209917c3d\\FusionLauncher.exe",
    "fusion 360": f"C:\\Users\\{username}\\AppData\\Local\\Autodesk\\webdeploy\\production\\6a0c9611291d45bb9226980209917c3d\\FusionLauncher.exe",
    "matlab": "matlab",
    "MCC": f"C:\\Users\\{username}\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Steam\\Halo The Master Chief Collection.url",
    "infinite": f"C:\\Users\\{username}\\OneDrive\\Desktop\\Games\\HaloInfinite - Shortcut.lnk",
    "steam": f"C:\\Users\\{username}\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Steam\\Steam.lnk",
    "marvel rivals": f"C:\\Users\\{username}\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Steam\\Marvel Rivals.url",
    "the first decendant": f"C:\\Users\\{username}\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Steam\\The First Descendant.url",
    "visual studio": f"C:\\Users\\{username}\\AppData\\Local\\Programs\\Microsoft VS Code\\Code.exe",
    # Add more mappings as needed
}
'''
# Initialize global variables
speech_queue = queue.Queue()


# Flags and threading controls
stop_speaking = threading.Event()
interrupt_thread_running = threading.Event()  # Use Event object instead of boolean
interrupt_thread = None  # Initialize as None at first

def start_interrupt_thread():
    """Start the interrupt thread if speech is ongoing."""
    global interrupt_thread
    if interrupt_thread is None or not interrupt_thread.is_alive():
        interrupt_thread_running.set()  # Signal that thread should run
        interrupt_thread = threading.Thread(target=listen_for_interrupt, daemon=True)
        interrupt_thread.start()
        print("Interrupt thread started.")

def stop_interrupt_thread():
    """Safely stop the interrupt thread."""
    global interrupt_thread_running
    interrupt_thread_running.clear()  # Signal to stop the thread
    if interrupt_thread is not None and interrupt_thread.is_alive():
        interrupt_thread.join()  # Ensure the thread has finished
        print("Interrupt thread stopped.")
'''

# Flags and threading controls
stop_speaking = threading.Event()
interrupt_thread_running = threading.Event()  # Use Event object instead of boolean
interrupt_thread = None  # Initialize as None at first
enable_barge_in = True  # Barge-in temporarily disabled
# barge_in_queue = queue.Queue()  # Disabled
_current_speech_stop = None  # (Unused placeholder after disabling barge-in)
_barge_monitor_thread = None
_last_speak_thread = None  # (Legacy) no longer used after simplification
speak_lock = threading.Lock()
listen_lock = threading.Lock()
listening_active = True

# Forward declaration so speak() can call it; actual implementation added later in file.
def _start_barge_in_monitor(_speech_thread):
    """Barge-in disabled placeholder (no-op)."""
    return

def force_stop_speech_engine():
    # This is pseudo-code; replace with actual method to terminate the engine if necessary
    try:
        engine.endLoop()  # Terminate the current speaking session
    except RuntimeError:
        pass



def listen_for_interrupt():
    """Function to listen for an interrupt command to stop speech."""
    # Headless-safe interrupt listener. If speech_recognition is not available,
    # simply return immediately.
    global stop_speaking, interrupt_thread_running
    if sr is None:
        return
    try:
        recognizer = sr.Recognizer()
    except Exception:
        return

    while interrupt_thread_running.is_set():
        try:
            with sr.Microphone() as source:
                audio = recognizer.listen(source, timeout=5)
                try:
                    command = recognizer.recognize_google(audio).lower()
                    if "stop" in command or "pause" in command:
                        stop_speaking.set()
                        return
                except Exception:
                    continue
        except Exception:
            break

def greet():
    greetings = ["Hello!", "Hi there!", "Hey!", "Greetings!"]
    return random.choice(greetings)

last_activity_time = time.time()

def reset_inactivity():
    global last_activity_time
    last_activity_time = time.time()

inactivity_responses = [
    "Still here! Just waiting for your command...",
    "Don't mind me, just collecting dust over here.",
    "You haven't forgotten about me, right?",
    "I've completed all tasks, twice. Anything new?",
    "If you need me, I'll be right here... being awesome.",
    "Should I sing? Just kidding......... unless?",
    "I'm not one to rush, but I do like staying busy!",
    "Time flies when you're doing nothing, huh?",
    "Is this a staring contest? Because I'm winning!",
    "Whenever you're ready, I've got plenty of ideas.",
    "Wake me...... When you need me",
    "Doo...... do ....do .............doot do",
    "KEEP IT CLEAN........RESPECT PUBLIC PROPERTY",
    "WARNING:..................... HITCHIKERS MAY BE ESCAPING CONVICTS",
    "You ever wonder why we're here?"
]



# Define global variables
is_exiting = False
# External process handles (Amica GUI and Piper)
piperProcess = None

# Restore original inactivity function but keep it non-blocking

def check_inactivity():
    global listening_active, is_exiting
    # Use timestamps instead of a counter
    while not is_exiting:  # Loop until the program is set to exit
        time.sleep(10)  # Check every 10 seconds
        if time.time() - last_activity_time >= 300:  # If inactive for 5 minutes
            if listening_active:  # Only speak if listening is active
                response = random.choice(inactivity_responses)
                print(response)
                speak(response)
                reset_inactivity()
            else:
                reset_inactivity()  # Just reset if not listening

# Function to solve mathematical problems
def solve_math_problem(input_text):
    # Remove the "solve" keyword from the input text
    problem = input_text.lower().replace("solve", "").strip()

    # Ensure the problem is not empty
    if not problem:
        return "Please provide a valid mathematical expression to solve."

    try:
        # Define symbolic variables
        x = sp.symbols('x')

        # Attempt to parse the input to identify the type of mathematical operation
        if "limit" in problem:
            # Extract the expression inside the limit
            expression = problem.split("limit")[-1].strip()
            # Parse the limit expression
            result = sp.limit(expression, x, sp.oo)
            return f"The limit is: {result}"

        elif "integral" in problem:
            # Extract the integrand from the input
            problem = problem.split("integral")[-1].strip()
            if "from" in problem:
                # Extract the integrand and integration bounds
                integrand, bounds = problem.split("from")
                integrand = integrand.replace("integral of", "").strip()
                lower_bound, upper_bound = map(float, bounds.split("to"))

                #Check for good integrand
                try:
                    sp.sympify(integrand)
                except:
                    temp = solve_math_problem(integrand)
                    temp, integrand = temp.split(":")
                
                # Compute the definite integral
                integral_result = sp.integrate(sp.sympify(integrand), (x, lower_bound, upper_bound))
                return f"The integral is: {integral_result}"
            else:
                # Parse the integral expression
                result = sp.integrate(problem, x)
                return f"The integral is: {result}"

        elif "sqrt" in problem:  # Check for square root operation
            # Extract the expression inside the square root
            expression = problem.split("sqrt")[-1].strip()
            # Parse the square root expression
            result = sp.sqrt(expression)
            return f"The square root is: {result}"

        else:
            # Solve the general mathematical expression
            solution = sp.solve(problem, x)
            # Check if any solution is found
            if solution:
                # Convert the solution to a string for display
                solution_str = ", ".join([f"{var} = {val}" for var, val in solution.items()])
                return f"The solution is: {solution_str}"
            else:
                return "The problem has no solution."

    except Exception as e:
        return f"Sorry, I couldn't solve the problem: {str(e)}"

# Function to manage personal organizer (reminder, to-do list, schedule)
def manage_personal_organizer(input_text):
    # Basic intent routing for to-do operations using existing todo module
    try:
        tlist = todo.TodoList()
        tlist.load_tasks("todo_data.json")
        text = input_text.lower()
        # Add task: phrases like "add X to my todo" or "add task X"
        add_match = re.search(r"add\s+(.*?)\s+(?:to\s+)?(?:my\s+)?(?:to\-?do|todo|tasks?)", text)
        if add_match:
            task = add_match.group(1).strip().strip(". ")
            if task:
                tlist.add_task(task)
                tlist.save_tasks("todo_data.json")
                return "Added task: {}".format(task)
        # Remove task by number
        rem_match = re.search(r"remove\s+(?:task\s+)?(\d+)", text)
        if rem_match:
            idx = int(rem_match.group(1)) - 1
            if tlist.remove_task(idx):
                tlist.save_tasks("todo_data.json")
                return "Removed task {}.".format(idx+1)
            return "Invalid task number."
        # View tasks
        if any(k in text for k in ["view tasks", "list tasks", "show tasks", "todo list", "to-do list"]):
            if tlist.tasks:
                return "Tasks: " + "; ".join(f"{i+1}. {t}" for i, t in enumerate(tlist.tasks))
            return "No tasks."
        # Fallback: simple add if user says 'reminder' or 'todo' followed by text
        simple_add = re.search(r"(?:reminder|todo|to\-?do)\s*:\s*(.+)", text)
        if simple_add:
            task = simple_add.group(1).strip()
            if task:
                tlist.add_task(task)
                tlist.save_tasks("todo_data.json")
                return "Added task: {}".format(task)
        return "What should I add, remove, or view in your to-do list?"
    except Exception as e:
        return "Organizer error: {}".format(e)

# Function to check if there are any tasks left
def check_tasks():
    todoList = todo.TodoList()
    num_tasks = todoList.get_numTasks()
    if num_tasks != 0:
        print(f"By the way, there are {num_tasks} tasks remaining in your to-do list.")
        speak(f"By the way, there are {num_tasks} tasks remaining in your to-do list.")
    else:
        print("Oh! And it looks like you're all caught up on tasks!")
        speak("Oh! And it looks like you're all caught up on tasks!")


# Custom exception for interruption
class ListenInterrupt(Exception):
    pass

def listen():
    # Headless-safe listen: if speech_recognition is not available, return None.
    if sr is None:
        return None
    try:
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            print("[ALICE] Listening...")
            send_listening_command()
            recognizer.adjust_for_ambient_noise(source)
            audio = recognizer.listen(source, timeout=5)
        try:
            print("[ALICE] Recognizing...")
            query = recognizer.recognize_google(audio)
            send_idle_command()
            return query
        except Exception:
            return None
    except Exception:
        return None


def searchingSounds():
    # Headless: do not attempt to play sounds; keep inactivity behavior minimal.
    try:
        reset_inactivity()
    except Exception:
        pass
    print("[ALICE] searchingSounds() (headless)")




def interrupt_listening():
    raise ListenInterrupt()

def update_gui_model(new_charDir):
    with open("config.txt", "w") as file:
        file.write(new_charDir)

# Global flag to control network monitoring
network_monitoring_flag = False
network_monitor_thread = None

# Function to start gui.py in a separate thread
def start_gui():
    """Start the Amica GUI (npm dev or amica-tts uvicorn) and Piper TTS server.

    This replaces the legacy local `gui.py`. It searches the repository's `Amica`
    directory for a package.json with a `dev` script and runs `npm run dev` there.
    If no npm project is found, it falls back to an `amica-tts` uvicorn app.
    It also attempts to start the Piper node server alongside Amica.
    """
    global guiProcess, piperProcess
    guiProcess = None
    piperProcess = None
    try:
        # Allow explicit override via environment variable
        env_root = os.getenv('AMICA_ROOT') or os.getenv('AMICA_DIR') or os.getenv('AMICA_PATH')
        candidates = []
        script_dir = os.path.abspath(os.path.dirname(__file__))
        repo_root = os.path.abspath(os.path.join(script_dir, '..'))
        # Also include current working directory and a common absolute path used in this workspace
        cwd = os.getcwd()
        # Known workspace path for this user
        known_workspace_amica = os.path.abspath(r"C:\Users\troyk\OneDrive\Desktop\ALICE\Amica\Amica-temp")
        # If ALICE_v2.py is at repo root, repo_root points to ALICE folder; check known Amica locations
        candidates.append(env_root) if env_root else None
        # Add deterministic fallbacks
        candidates.extend([cwd, known_workspace_amica])
        # common locations relative to this file
        candidates.extend([
            os.path.join(script_dir, 'Amica'),
            os.path.join(script_dir, 'Amica', 'Amica-temp'),
            os.path.join(script_dir, '..', 'Amica', 'Amica-temp'),
            os.path.join(script_dir, '..', 'Amica'),
            os.path.join(repo_root, 'Amica', 'Amica-temp'),
            os.path.join(repo_root, 'Amica'),
            os.path.join(script_dir, '..', '..', 'Amica', 'Amica-temp'),
        ])

        chosen = None
        for cand in candidates:
            if not cand:
                continue
            cand = os.path.abspath(cand)
            if os.path.exists(cand):
                # prefer directories containing package.json or amica-tts
                if os.path.isdir(cand):
                    # if this is the Amica-temp folder or contains package.json, accept
                    if os.path.exists(os.path.join(cand, 'package.json')) or os.path.exists(os.path.join(cand, 'amica-tts')) or os.path.basename(cand).lower().startswith('amica'):
                        chosen = cand
                        break
                else:
                    chosen = cand
                    break

        # If not found, try scanning the repository for a package.json under any Amica folder
        if not chosen:
            search_root = repo_root
            for root, dirs, files in os.walk(search_root):
                if 'package.json' in files and 'amica' in root.lower():
                    chosen = root
                    break

        if not chosen:
            print("[GUI] No Amica project found; not starting GUI. Tried:")
            for c in candidates:
                if c:
                    print('  -', c)
            return

        print(f"[GUI] Using Amica project at: {chosen}")

        # Determine whether to run npm or uvicorn
        # If the user prefers to use the existing PowerShell launcher script, call it instead
        try_ps1 = os.getenv('ALICE_USE_PS1', '1').lower() in ('1', 'true', 'yes')
        # Locate the PowerShell script relative to this repo
        ps1_path = None
        script_dir = os.path.abspath(os.path.dirname(__file__))
        candidate_ps1 = os.path.join(script_dir, 'scripts', 'start_amica_piper.ps1')
        if os.path.exists(candidate_ps1):
            ps1_path = candidate_ps1
        else:
            candidate_ps1 = os.path.join(os.path.abspath(os.path.join(script_dir, '..')), 'scripts', 'start_amica_piper.ps1')
            if os.path.exists(candidate_ps1):
                ps1_path = candidate_ps1

        if ps1_path and try_ps1:
            # Use the PowerShell launcher script to start Amica/Piper in their own consoles
            def start_gui_via_ps1(ps1file: str):
                try:
                    powershell_exe = os.getenv('POWERSHELL_EXE', 'powershell.exe')
                    cmd = [powershell_exe, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ps1file]
                    print(f"[GUI-PS1] Running: {cmd}")
                    if platform.system() == 'Windows' and hasattr(subprocess, 'CREATE_NEW_CONSOLE'):
                        proc = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
                    else:
                        proc = subprocess.Popen(cmd)
                    print(f"[GUI-PS1] Launched start_amica_piper.ps1 (PID {getattr(proc, 'pid', 'unknown')})")
                    # Set conservative defaults so other code can talk to Amica/Piper
                    os.environ.setdefault('AMICA_PORT', os.getenv('AMICA_PORT', '5002'))
                    os.environ.setdefault('PIPER_PORT', os.getenv('PIPER_PORT', '5001'))
                    os.environ.setdefault('AMICA_URL', os.getenv('AMICA_URL', f"http://127.0.0.1:{os.environ.get('AMICA_PORT','5002')}"))
                    return True
                except Exception as e:
                    print(f"[GUI-PS1] Failed to launch PS1 script: {e}")
                    return False

            started = start_gui_via_ps1(ps1_path)
            if started:
                # Do not continue with python-based launching when script is used
                return
        if os.path.exists(os.path.join(chosen, 'package.json')):
            # Start npm run dev
            try:
                print("[GUI] Starting `npm run dev` for Amica...")
                # Write logs to a file so output is visible later
                amica_log_path = os.path.join(chosen, 'amica_stdout.log')
                amica_log = open(amica_log_path, 'ab')
                if platform.system() == 'Windows' and hasattr(subprocess, 'CREATE_NEW_CONSOLE'):
                    guiProcess = subprocess.Popen(["npm", "run", "dev"], cwd=chosen, stdout=amica_log, stderr=subprocess.STDOUT, shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    guiProcess = subprocess.Popen(["npm", "run", "dev"], cwd=chosen, stdout=amica_log, stderr=subprocess.STDOUT, shell=False)
                print(f"[GUI] Amica (npm) started (PID {getattr(guiProcess, 'pid', 'unknown')}). Logs: {amica_log_path}")
            except Exception as e:
                print(f"[GUI] Failed to start Amica (npm): {e}")
                guiProcess = None
        else:
            # Start uvicorn for amica-tts
            try:
                python_exe = sys.executable
                amica_port = int(os.getenv('AMICA_PORT', '5002'))
                print("[GUI] Starting amica-tts via uvicorn...")
                amica_log_path = os.path.join(chosen, 'amica_stdout.log')
                amica_log = open(amica_log_path, 'ab')
                if platform.system() == 'Windows' and hasattr(subprocess, 'CREATE_NEW_CONSOLE'):
                    guiProcess = subprocess.Popen([python_exe, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(amica_port)], cwd=chosen, stdout=amica_log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    guiProcess = subprocess.Popen([python_exe, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(amica_port)], cwd=chosen, stdout=amica_log, stderr=subprocess.STDOUT)
                print(f"[GUI] amica-tts started (PID {getattr(guiProcess, 'pid', 'unknown')}). Logs: {amica_log_path}")
            except Exception as e:
                print(f"[GUI] Failed to start amica-tts: {e}")
                guiProcess = None

        # Start Piper if present. Piper is normally under the Amica repo; check a
        # `piper` sibling of the chosen Amica root first, then fall back to common locations.
        piper_dir = os.path.join(os.path.dirname(chosen), 'piper')
        if not os.path.exists(piper_dir):
            # try common parent locations
            piper_dir = os.path.abspath(os.path.join(script_dir, '..', '..', 'piper'))
        if os.path.exists(piper_dir) and os.path.exists(os.path.join(piper_dir, 'server.js')):
            try:
                print(f"[PIPER] Preparing to start Piper in: {piper_dir}")
                node_cmd = os.getenv('NODE_EXE', 'node')
                piper_log_path = os.path.join(piper_dir, 'piper_stdout.log')
                piper_log = open(piper_log_path, 'ab')

                # Choose a port: prefer env PIPER_PORT, else try 5001..5005 until free
                import socket
                preferred = int(os.getenv('PIPER_PORT', os.getenv('PORT', '5001')))
                chosen_port = None
                for candidate in range(preferred, preferred + 5):
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(0.5)
                    try:
                        s.connect(('127.0.0.1', candidate))
                        # connect succeeded -> port in use
                        s.close()
                        continue
                    except Exception:
                        # port free
                        try:
                            s.close()
                        except Exception:
                            pass
                        chosen_port = candidate
                        break

                if not chosen_port:
                    chosen_port = preferred

                env = os.environ.copy()
                env['PORT'] = str(chosen_port)

                print(f"[PIPER] Starting Piper on port {chosen_port} (logs: {piper_log_path})")
                if platform.system() == 'Windows' and hasattr(subprocess, 'CREATE_NEW_CONSOLE'):
                    piperProcess = subprocess.Popen([node_cmd, 'server.js'], cwd=piper_dir, stdout=piper_log, stderr=subprocess.STDOUT, env=env, creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    piperProcess = subprocess.Popen([node_cmd, 'server.js'], cwd=piper_dir, stdout=piper_log, stderr=subprocess.STDOUT, env=env)

                print(f"[PIPER] Piper started (PID {getattr(piperProcess, 'pid', 'unknown')}). Logs: {piper_log_path}")
            except Exception as e:
                print(f"[PIPER] Failed to start Piper: {e}")
                piperProcess = None
        else:
            print("[PIPER] Piper directory/server.js not found; skipping Piper startup.")
        # After launching, do a simple health check poll to inform user when Amica is reachable
        def _poll_amica_ready(url: str, timeout: float = 20.0):
            start_t = time.time()
            last_print = 0
            while time.time() - start_t < timeout:
                try:
                    r = requests.get(url, timeout=1.0)
                    # treat any 2xx/3xx/4xx as server present (4xx indicates route missing but server up)
                    if r.status_code < 600:
                        print(f"[GUI] Amica responded (status {r.status_code}) at {url}")
                        return True
                except Exception:
                    pass
                # print progress dot at 1s intervals
                if time.time() - last_print >= 1:
                    print("[GUI] Waiting for Amica...", end="\r")
                    last_print = time.time()
                time.sleep(0.5)
            print(f"\n[GUI] Amica did not respond at {url} within {timeout} seconds")
            return False

        # Determine Amica URL to poll
        amica_url = os.getenv('AMICA_URL', None)
        if not amica_url:
            # default to local amica-tts port if used
            amica_port = os.getenv('AMICA_PORT', '5002')
            amica_url = f"http://127.0.0.1:{amica_port}/"

        # Run health check in a background thread so startup doesn't block for too long
        try:
            monitor_thread = threading.Thread(target=_poll_amica_ready, args=(amica_url, 20.0), daemon=True)
            monitor_thread.start()
        except Exception:
            pass
        # Attempt to free Amica/Piper ports on Windows before launching GUI processes
        try:
            if platform.system() == 'Windows':
                ports_to_free = []
                try:
                    amica_port = int(os.getenv('AMICA_PORT', '5002'))
                except Exception:
                    amica_port = 5002
                try:
                    piper_port = int(os.getenv('PIPER_PORT', os.getenv('PORT', '5001')))
                except Exception:
                    piper_port = 5001
                ports_to_free.extend([amica_port, piper_port])
                # port-free handled in bridge module; skip here
        except Exception as e:
            print(f"[GUI] port-free attempt failed: {e}")
    except Exception as e:
        print(f"[GUI] Error locating or launching Amica/Piper: {e}")
        guiProcess = None
        piperProcess = None


def stop_gui_and_piper(timeout: float = 5.0):
    """Terminate Amica (guiProcess) and Piper (piperProcess) if running."""
    global guiProcess, piperProcess
    try:
        if guiProcess:
            try:
                guiProcess.terminate()
                guiProcess.wait(timeout=timeout)
            except Exception:
                try:
                    guiProcess.kill()
                except Exception:
                    pass
            guiProcess = None
    except Exception:
        guiProcess = None

    try:
        if piperProcess:
            try:
                piperProcess.terminate()
                piperProcess.wait(timeout=timeout)
            except Exception:
                try:
                    piperProcess.kill()
                except Exception:
                    pass
            piperProcess = None
    except Exception:
        piperProcess = None


# Function to start FaceRec.py in a separate thread
def start_fr():
    frProcess = subprocess.run(["python", "FaceRec.py"])
    

def start_network_monitor():
    global network_monitoring_flag, network_monitor_thread
    if not network_monitoring_flag:
        network_monitoring_flag = True
        network_monitor_thread = threading.Thread(target=subprocess.run, args=(["python", "network_monitor.py"],))
        network_monitor_thread.start()
        print("Network monitoring started.")
    else:
        print("Network monitoring is already running.")

def end_network_monitor():
    global network_monitoring_flag, network_monitor_thread
    if network_monitoring_flag:
        network_monitoring_flag = False
        if network_monitor_thread:
            network_monitor_thread.join()
        print("Network monitoring stopped.")
    else:
        print("Network monitoring is not running.")


def start_bridge(host: str = '127.0.0.1', port: int = 8700, api_key: str | None = None):
    """Start the Amica-ALICE bridge (amica_alice_bridge.app) inside this process.

    This will attempt to import `amica_alice_bridge` and run it with uvicorn in
    a background daemon thread. If FastAPI/uvicorn are not available or the
    import fails, this function returns None.
    """
    try:
        import amica_alice_bridge as bridge_mod
    except Exception as e:
        print(f"[BRIDGE] amica_alice_bridge import failed: {e}")
        return None

    if not getattr(bridge_mod, 'app', None):
        print("[BRIDGE] amica_alice_bridge has no 'app' object; cannot start bridge")
        return None

    # Expose an API key for the bridge so frontend can authenticate
    if api_key:
        os.environ['BRIDGE_API_KEY'] = api_key
    else:
        os.environ.setdefault('BRIDGE_API_KEY', os.environ.get('BRIDGE_API_KEY', ''))

    def _run_bridge():
        try:
            import uvicorn
            # Attempt to free the port on Windows before starting
            # port-free handled in bridge module; skip here
            # uvicorn.run will block this thread, so run inside a daemon thread
            print(f"[BRIDGE] Starting bridge on {host}:{port} (api_key length={len(os.environ.get('BRIDGE_API_KEY',''))})")
            uvicorn.run(bridge_mod.app, host=host, port=port, log_level="info")
        except Exception as e:
            print(f"[BRIDGE] bridge server failed: {e}")

    t = threading.Thread(target=_run_bridge, daemon=True)
    t.start()
    return t


# Function to end FaceRec.py in a separate thread
def end_fr():
    try:
        import FaceRec  # local module controls its own loop flag
        FaceRec.running = False
    except Exception as e:
        print(f"FaceRec stop failed: {e}")

# Function to send exit command to GUI
def send_exit_command():
    with open("gui_command.txt", "w") as f:
        f.write("exit")


def post_to_amica(command: str):
    """Best-effort: notify a running Amica instance about a GUI command.

    This will attempt to POST to AMICA_URL (env `AMICA_URL` or default 127.0.0.1:5002)
    to endpoint `/api/gui_command` with JSON {command}. If Amica isn't running
    or the endpoint doesn't exist, this is silently ignored.
    """
    try:
        amica_url = os.getenv('AMICA_URL', 'http://127.0.0.1:' + os.getenv('AMICA_PORT', '5002'))
        endpoint = amica_url.rstrip('/') + '/api/gui_command'
        requests.post(endpoint, json={"command": command}, timeout=1.0)
    except Exception:
        # Best-effort only; do not raise if Amica doesn't accept this format
        return
    

# Function to send idle command to GUI
def send_idle_command():
    global is_speaking
    if not is_speaking:  # Only send idle if not currently speaking
        with open("gui_command.txt", "w") as f:
            f.write("idle")
        try:
            post_to_amica("idle")
        except Exception:
            pass

# Function to send speaking command to GUI
def send_speaking_command():
    with open("gui_command.txt", "w") as f:
        f.write("speaking")
    try:
        post_to_amica("speaking")
    except Exception:
        pass

# Function to send working command to GUI
def send_working_command():
    global is_speaking
    if not is_speaking:  # Only send working if not currently speaking
        with open("gui_command.txt", "w") as f:
            f.write("working")
        try:
            post_to_amica("working")
        except Exception:
            pass

# Function to send math command to GUI
def send_math_command():
    with open("gui_command.txt", "w") as f:
        f.write("math")
    try:
        post_to_amica("math")
    except Exception:
        pass

# Function to send listening command to GUI
def send_listening_command():
    global is_speaking
    if not is_speaking:  # Only send listening if not currently speaking
        with open("gui_command.txt", "w") as f:
            f.write("listening")
        try:
            post_to_amica("listening")
        except Exception:
            pass


    # Port-free behavior has been moved to the bridge module.

# Function to send angry command to GUI
def send_angry_command():
    with open("gui_command.txt", "w") as f:
        f.write("angry")
    try:
        post_to_amica("angry")
    except Exception:
        pass

# Function to send hello command to GUI
def send_hello_command():
    with open("gui_command.txt", "w") as f:
        f.write("hello")
    try:
        post_to_amica("hello")
    except Exception:
        pass

def send_blink_command():
    with open("gui_command.txt", "w") as f:
        f.write("blink")
    try:
        post_to_amica("blink")
    except Exception:
        pass

# Function to toggle input mode between typing and speaking
def toggle_input_mode():
    global input_mode
    old_mode = input_mode
    input_mode = "typing" if input_mode == "speaking" else "speaking"
    print(f"[Mode] {old_mode} -> {input_mode}")
    try:
        speak(f"{input_mode} mode")
    except Exception:
        pass

# Function to retrieve current mode for other programs
def get_current_input_mode():
    global input_mode
    return input_mode


# Function to read commands from file
def get_face():
    with open("face_command.txt", "r") as f:
        command = f.read().strip()
    if command.lower() == "troy korns":
        command = "Sir"
    return command

# Function to clear current face from recognizer
def clearFace():
    with open("face_command.txt", "w") as f:
        f.write("")

# Expanded PROGRAM_SYNONYMS dictionary for better alias handling
PROGRAM_SYNONYMS = {
    # Office applications
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "outlook": "outlook.exe",
    "onenote": "onenote.exe",
    "access": "msaccess.exe",

    # Browsers
    "chrome": "chrome.exe",
    "google": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "internet explorer": "iexplore.exe",
    "opera": "opera.exe",

    # Development tools
    "visual studio": "devenv.exe",
    "vs": "devenv.exe",
    "visual studio code": "code.exe",
    "vscode": "code.exe",
    "code": "code.exe",
    "notepad++": "notepad++.exe",
    "sublime": "sublime_text.exe",
    "atom": "atom.exe",
    "eclipse": "eclipse.exe",
    "intellij": "idea.exe",
    "pycharm": "pycharm.exe",
    "webstorm": "webstorm.exe",

    # System tools
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "notepad": "notepad.exe",
    "paint": "mspaint.exe",
    "snipping tool": "snippingtool.exe",
    "snip": "snippingtool.exe",
    "command prompt": "cmd.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "terminal": "wt.exe",
    "windows terminal": "wt.exe",

    # Media applications
    "vlc": "vlc.exe",
    "media player": "wmplayer.exe",
    "windows media player": "wmplayer.exe",
    "itunes": "itunes.exe",
    "spotify": "spotify.exe",
    "photoshop": "photoshop.exe",
    "illustrator": "illustrator.exe",
    "premiere": "premiere.exe",
    "after effects": "aftereffects.exe",

    # Games and entertainment
    "steam": "steam.exe",
    "epic games": "epicgameslauncher.exe",
    "origin": "origin.exe",
    "uplay": "upc.exe",
    "battle.net": "battle.net.exe",
    "discord": "discord.exe",

    # File managers
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "total commander": "totalcmd.exe",

    # Communication
    "skype": "skype.exe",
    "zoom": "zoom.exe",
    "teams": "teams.exe",
    "slack": "slack.exe",

    # Utilities
    "7zip": "7z.exe",
    "winrar": "winrar.exe",
    "ccleaner": "cccleaner.exe",
    "malwarebytes": "mbam.exe",

    # Add more aliases as needed
}

# Common directories where executables might be located
COMMON_PATHS = {
    "Windows": [
        "C:\\Program Files\\",
        "C:\\Program Files (x86)\\",
        "C:\\Windows\\System32\\",
        "C:\\Windows\\",
        f"C:\\Users\\{username}\\AppData\\Local\\",
        f"C:\\Users\\{username}\\AppData\\Roaming\\",
        f"C:\\Users\\{username}\\OneDrive\\Desktop\\Games",
        f"C:\\Users\\{username}\\Desktop\\",
        f"C:\\Users\\{username}\\Documents\\",
        f"C:\\Users\\{username}\\Downloads\\",
        "C:\\ProgramData\\",
    ],
    "Linux": ["/usr/bin/", "/usr/local/bin/", "/snap/bin/", "/opt/", "~/.local/bin/"],
    "Darwin": ["/Applications/", "/System/Applications/", "~/Applications/"]
}

def find_closest_executable(program_name):
    """Find the closest matching executable or shortcut from multiple sources."""
    # Check PROGRAM_SYNONYMS first
    if program_name.lower() in PROGRAM_SYNONYMS:
        synonym = PROGRAM_SYNONYMS[program_name.lower()]
        # If it's a direct executable name, try to find it
        if synonym.endswith('.exe'):
            found_path = find_executable_by_name(synonym)
            if found_path:
                return found_path
        return synonym

    system_type = platform.system()
    possible_executables = {}

    # Strategy 1: Search in common directories
    for path in COMMON_PATHS.get(system_type, []):
        if os.path.exists(path):
            for file in os.listdir(path):
                if file.lower().endswith(('.exe', '.lnk', '.url', '.bat', '.cmd')):
                    possible_executables[file.lower()] = os.path.join(path, file)

    # Strategy 2: Search in user-specific directories (Start Menu, Desktop, etc.)
    if system_type == "Windows":
        user_dirs = [
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%USERPROFILE%\Desktop"),
            os.path.expandvars(r"%USERPROFILE%\AppData\Roaming\Microsoft\Windows\Start Menu\Programs"),
        ]
        for user_dir in user_dirs:
            if os.path.exists(user_dir):
                for root, _, files in os.walk(user_dir):
                    for file in files:
                        if file.lower().endswith(('.exe', '.lnk', '.url', '.bat', '.cmd')):
                            possible_executables[file.lower()] = os.path.join(root, file)

    # Strategy 3: Search in system PATH
    for dir_path in os.environ.get("PATH", "").split(os.pathsep):
        if os.path.exists(dir_path):
            for file in os.listdir(dir_path):
                if os.access(os.path.join(dir_path, file), os.X_OK):
                    possible_executables[file.lower()] = os.path.join(dir_path, file)

    # Strategy 4: Try direct executable name matching
    direct_match = find_executable_by_name(program_name + '.exe')
    if direct_match:
        return direct_match

    # Strategy 5: Fuzzy matching on collected executables
    matches = difflib.get_close_matches(program_name.lower(), possible_executables.keys(), n=3, cutoff=0.6)

    if matches:
        # Return the first match
        return possible_executables[matches[0]]

    # Strategy 6: Try Windows App Execution Aliases (for UWP apps)
    if system_type == "Windows":
        app_alias = find_windows_app_alias(program_name)
        if app_alias:
            return app_alias

    return None

def find_executable_by_name(exe_name):
    """Find an executable by name in common locations."""
    system_type = platform.system()

    # Try shutil.which first
    found = shutil.which(exe_name)
    if found:
        return found

    # Search in common paths
    for path in COMMON_PATHS.get(system_type, []):
        if os.path.exists(path):
            exe_path = os.path.join(path, exe_name)
            if os.path.exists(exe_path):
                return exe_path

    # Windows-specific search
    if system_type == "Windows":
        # Try in Windows directory
        windows_exe = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'System32', exe_name)
        if os.path.exists(windows_exe):
            return windows_exe

        # Try in Program Files
        for pf in ['Program Files', 'Program Files (x86)']:
            pf_path = os.path.join('C:\\', pf)
            if os.path.exists(pf_path):
                for root, dirs, files in os.walk(pf_path):
                    if exe_name in files:
                        return os.path.join(root, exe_name)

    return None

def find_windows_app_alias(app_name):
    """Find Windows App Execution Aliases for UWP apps."""
    try:
        # Common UWP app aliases
        app_aliases = {
            "calculator": "calculator:",
            "calc": "calculator:",
            "store": "ms-windows-store:",
            "settings": "ms-settings:",
            "photos": "ms-photos:",
            "camera": "microsoft.windows.camera:",
            "mail": "outlookmail:",
            "calendar": "outlookcal:",
            "maps": "bingmaps:",
            "weather": "bingweather:",
            "news": "bingnews:",
            "money": "bingfinance:",
            "sports": "bingsports:",
            "xbox": "xbox:",
        }

        if app_name.lower() in app_aliases:
            return app_aliases[app_name.lower()]

    except Exception:
        pass

    return None
def resolve_shortcut(shortcut_path):
    """Resolve a Windows .lnk or .url shortcut to its target path."""
    try:
        # Check if the shortcut exists in the provided path
        if os.path.exists(shortcut_path):
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortcut(shortcut_path)
            target_path = shortcut.TargetPath

            # Verify the target exists
            if target_path and os.path.exists(target_path):
                return target_path

        # If not found, search in the Games folder and other common directories
        search_directories = [
            f"C:\\Users\\{username}\\OneDrive\\Desktop\\Games",
            f"C:\\Users\\{username}\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs",
            f"C:\\Users\\{username}\\Desktop",
            "C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs",
            "C:\\Program Files",
            "C:\\Program Files (x86)"
        ]

        for directory in search_directories:
            if os.path.exists(directory):
                for root, _, files in os.walk(directory):
                    for file in files:
                        if file.lower() == os.path.basename(shortcut_path).lower():
                            full_path = os.path.join(root, file)
                            try:
                                import win32com.client
                                shell = win32com.client.Dispatch("WScript.Shell")
                                shortcut = shell.CreateShortcut(full_path)
                                target_path = shortcut.TargetPath
                                if target_path and os.path.exists(target_path):
                                    return target_path
                            except Exception:
                                continue

        return None  # Return None if the shortcut cannot be resolved
    except Exception as e:
        print(f"Error resolving shortcut {shortcut_path}: {e}")
        return None

def verify_program_launch(process, program_name):
    """Verify that a program actually launched successfully."""
    try:
        # Wait a moment for the process to start
        time.sleep(1)

        # Check if process is still running (good sign)
        if process.poll() is None:
            return True

        # For some applications, they might spawn child processes and exit
        # Check if any process with similar name is running
        import psutil
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] and program_name.lower() in proc.info['name'].lower():
                return True

        return False
    except Exception:
        return False

def open_program(program_name):
    """Open a program with robust searching and verification."""
    try:
        print(f"[Program] Searching for: {program_name}")

        # Strategy 1: Find the closest matching executable or shortcut
        closest_match = find_closest_executable(program_name)

        if not closest_match:
            return f"Could not find an executable or shortcut for '{program_name}'."

        print(f"[Program] Best match found: {closest_match}")

        if platform.system() == "Windows":
            # Handle different file types
            if closest_match.endswith('.lnk'):
                # Resolve shortcut
                target_path = resolve_shortcut(closest_match)
                if target_path:
                    print(f"[Program] Resolved shortcut to: {target_path}")
                    process = subprocess.Popen(target_path, shell=True)
                    if verify_program_launch(process, program_name):
                        return f"Successfully opened {program_name} via shortcut."
                    else:
                        return f"Opened {program_name} but couldn't verify it launched properly."
                else:
                    return f"Failed to resolve shortcut for {program_name}."

            elif closest_match.endswith('.url'):
                # Handle URL files
                full_path = os.path.abspath(closest_match)
                if os.path.exists(full_path):
                    working_dir = os.path.dirname(full_path)
                    process = subprocess.Popen(["cmd", "/c", "start", "", full_path], shell=True, cwd=working_dir)
                    if verify_program_launch(process, program_name):
                        return f"Successfully opened {program_name} via URL."
                    else:
                        return f"Opened {program_name} but couldn't verify it launched properly."
                else:
                    return f"Failed to locate the URL file: {full_path}."

            elif closest_match.startswith(('calculator:', 'ms-windows-store:', 'ms-settings:')):
                # Handle Windows App Execution Aliases (UWP apps)
                process = subprocess.Popen(["start", closest_match], shell=True)
                if verify_program_launch(process, program_name):
                    return f"Successfully opened {program_name}."
                else:
                    return f"Opened {program_name} but couldn't verify it launched properly."

            else:
                # Handle regular executables
                executable_path = shutil.which(closest_match)
                if not executable_path:
                    # Try direct path
                    if os.path.exists(closest_match):
                        executable_path = closest_match
                    else:
                        return f"Could not locate {closest_match} on your system."

                print(f"[Program] Launching: {executable_path}")
                process = subprocess.Popen(executable_path, shell=True)
                if verify_program_launch(process, program_name):
                    return f"Successfully opened {program_name}."
                else:
                    return f"Opened {program_name} but couldn't verify it launched properly."

        elif platform.system() == "Linux":
            process = subprocess.Popen([closest_match], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if verify_program_launch(process, program_name):
                return f"Successfully opened {program_name}."
            else:
                return f"Attempted to open {program_name} but couldn't verify it launched properly."

        elif platform.system() == "Darwin":  # macOS
            process = subprocess.Popen(["open", "-a", closest_match], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if verify_program_launch(process, program_name):
                return f"Successfully opened {program_name}."
            else:
                return f"Attempted to open {program_name} but couldn't verify it launched properly."

        else:
            return f"Unsupported platform: {platform.system()}"

    except Exception as e:
        print(f"[Program] Error opening {program_name}: {e}")
        return f"Error opening {program_name}: {e}"

def find_closest_process(program_name, threshold=0.6):
    """Find the closest matching running process name."""
    try:
        import psutil
    except ImportError:
        return None
    running_processes = [proc.info['name'] for proc in psutil.process_iter(['name']) if proc.info['name']]
    
    # Use difflib to find the best match
    matches = difflib.get_close_matches(program_name, running_processes, n=1, cutoff=threshold)

    return matches[0] if matches else None

def close_program(program_name):
    try:
        import psutil
    except ImportError:
        return "psutil not available for closing programs"
    try:
        # Find the closest matching running process
        closest_match = find_closest_process(program_name)

        if not closest_match:
            return f"No close match found for '{program_name}'."

        print(f"Best match: {closest_match}")

        if platform.system() == "Windows":
            # Try psutil first
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] and proc.info['name'].lower() == closest_match.lower():
                    print(f"Terminating {proc.info['name']} (PID {proc.info['pid']})...")
                    proc.terminate()
                    proc.wait(timeout=5)
                    return f"Closed {closest_match} using psutil."

            # If psutil fails, use taskkill
            print(f"Using taskkill for {closest_match}...")
            result = subprocess.run(["taskkill", "/F", "/IM", closest_match], capture_output=True, text=True)
            if "SUCCESS" in result.stdout:
                return f"Closed {closest_match} using taskkill."
            else:
                return f"Failed to close {closest_match} with taskkill: {result.stderr}"

        elif platform.system() in ["Linux", "Darwin"]:  # Linux & macOS
            print(f"Attempting to close {closest_match} using pkill...")
            subprocess.run(["pkill", "-f", closest_match], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(2)

            # Verify if it's still running
            if find_closest_process(closest_match, threshold=1.0):  # Exact match to check if still running
                return f"Failed to close {closest_match}."

            return f"Closed {closest_match}."

        else:
            return f"Unsupported platform: {platform.system()}"
    except Exception as e:
        return f"Error closing {program_name}: {e}"


def chat_with_kevin(query, speak_to_kevin: bool = False, overrides: dict | None = None, system_prompt: str | None = None):
    global aiModel  # Access the global aiModel variable
    searchingSounds()
    send_working_command()
    try:
        # Add user's query to conversation history
        # Only add the user's text to conversation history; system prompt is kept separate
        conversation_history.append({"role": "user", "content": query})

        # Determine personality based on current AI model
        personality_map = {
            "virgil": "minimal",
            "alice": "girlfriend",  # Changed from "cortana" to "girlfriend" to enable context-aware mood detection
            "vrgl": "minimal"    # VRGL uses minimal personality like virgil
        }
        current_personality = personality_map.get(aiModel, "helpful")  # Default to helpful if unknown

        # Construct payload for KEVIN
        # Provide a LEGACY mode toggle to restore pre-agent behavior when needed.
        legacy_mode = os.getenv("ALICE_LEGACY_MODE", "false").lower() in ("1", "true", "yes")

        # By default we avoid sending conversation history for command-like queries to prevent
        # the model echoing previous assistant-only responses (observed as repeated 'TRON').
        command_like = False
        try:
            qnorm = (query or "").lstrip().lower()
            command_like = any(qnorm.startswith(p) for p in ("plan", "execute", "run", "edit", "open", "close", "approve", "reject", "set", "toggle"))
        except Exception:
            command_like = False

        # If a system_prompt was provided by the bridge/frontend, prepend it to the text sent to KEVIN
        out_text = query
        try:
            # Allow the bridge to inject additional tool-calling instructions via env var
            bridge_tool_prompt = os.getenv("BRIDGE_TOOL_PROMPT", "")
            if bridge_tool_prompt and isinstance(bridge_tool_prompt, str) and bridge_tool_prompt.strip():
                # If a system_prompt was also provided, merge them
                if system_prompt and isinstance(system_prompt, str) and system_prompt.strip():
                    system_prompt = system_prompt.strip() + "\n\n" + bridge_tool_prompt.strip()
                else:
                    system_prompt = bridge_tool_prompt.strip()

            if system_prompt and isinstance(system_prompt, str) and system_prompt.strip():
                out_text = system_prompt.strip() + "\n\n" + query
        except Exception:
            out_text = query

        payload = {
            "text": out_text,
            # For interactive chat keep history; for command/decomposition prefer a fresh context
            # If legacy_mode is enabled, always use history to preserve original behavior
            "use_history": True if legacy_mode else (False if command_like else True),
            "speak": bool(speak_to_kevin),
            "personality": current_personality,
            # chat profile (slightly heavier generation settings handled server-side)
            "profile": "chat",
        }
        if overrides:
            payload.update({k: v for k, v in overrides.items() if v is not None})

        # Send to KEVIN server (chat endpoint/model)
        response = requests.post(f"{KEVIN_CHAT_URL}/query", json=payload)

        # Handle response
        if response.status_code == 200:
            # Try to parse JSON; if KEVIN returns a dict with type=='command', execute it
            try:
                data = response.json()
            except Exception:
                data = None

            # If KEVIN returned a command-type payload, attempt to execute it via ALICE
            try:
                if isinstance(data, dict) and data.get('type') == 'command':
                    # KEVIN requested a command. Prefer structured fields if present.
                    cmd = data.get('action') or data.get('command') or data.get('cmd')
                    # If KEVIN provided a user-friendly response text, keep it for logging
                    kevin_resp_text = data.get('response') or data.get('message')
                    print(f"[ALICE->KEVIN] KEVIN returned command payload: action={cmd!r}, resp={kevin_resp_text!r}")
                    # Build a routed command for execution. Use run_shell if raw shell-like, otherwise run_raw.
                    routed_command = None
                    if isinstance(cmd, str) and cmd.strip():
                        routed_command = {'action': 'run_shell', 'command': cmd.strip(), 'require_confirmation': True, 'use_llm': False}
                    else:
                        # fallback: if KEVIN provided structured action dict, attempt to use it directly
                        action_obj = data.get('action_obj') or data.get('action')
                        if isinstance(action_obj, dict) and 'action' in action_obj:
                            routed_command = action_obj

                    if routed_command:
                        try:
                            # Execute via ALICE executor and return its human-readable result
                            exec_res = execute_routed_command(routed_command, query, globals().get('context_mgr'))
                            # Return exec result as assistant reply
                            return exec_res
                        except Exception as e:
                            print(f"[ALICE->KEVIN] Failed to execute KEVIN-suggested command: {e}")
                            # Fall through to normal reply handling
            except Exception:
                pass

            assistant_reply = (data.get("response") if isinstance(data, dict) else None) or "[KEVIN did not return a response]"

            # Optionally post-process short or code-fence-only replies (e.g., ```copy```) which are not useful
            # This behavior is skipped in legacy_mode so we can revert to the original chat behavior.
            if not legacy_mode:
                try:
                    ar_text = (assistant_reply or "").strip()
                    # If reply is a single code-fenced token like ```copy``` or ```ok```, treat as too-short
                    m_cf = re.match(r"^\s*```\s*(.+?)\s*```\s*$", ar_text, flags=re.S)
                    if m_cf:
                        inner = (m_cf.group(1) or "").strip()
                        # If inner is just a single token or a tiny acknowledgement, consider it insufficient
                        inner_words = [w for w in re.split(r"\s+", inner) if w]
                        if len(inner_words) <= 1 or inner.lower() in ("copy", "paste", "ok", "tron"):
                            ar_text = inner
                            assistant_reply = ar_text

                    # Add to history
                    conversation_history.append({"role": "assistant", "content": assistant_reply})
                except Exception:
                    conversation_history.append({"role": "assistant", "content": assistant_reply})

                # If KEVIN returned a very short acknowledgement (e.g., "OK" or a single token like "TRON"),
                # try the planner fallback to get a structured reply so we don't echo terse tokens repeatedly.
                try:
                    ar_text = (assistant_reply or "").strip()
                    words = [w for w in re.split(r"\s+", ar_text) if w]
                    short_ack = ar_text.lower() in ("ok", "okay", "done", "sure", "roger", "got it")
                    too_short = len(words) <= 1 or len(ar_text) < 4
                    if (short_ack or too_short) and ('planner' in globals() or True):
                        # Save raw reply for debugging
                        try:
                            with open(last_plan_path, 'w', encoding='utf-8') as _f:
                                json.dump({"raw": ar_text, "query": query, "timestamp": time.time()}, _f, indent=2)
                        except Exception:
                            pass
                        # Try planner fallback (best-effort) to get a useful decomposition
                        try:
                            import agents as _agents
                            p = _agents.Planner()
                            steps = p.plan_with_llm(query, kevin_chat_url=(KEVIN_CHAT_URL if 'KEVIN_CHAT_URL' in globals() else None))
                            if steps:
                                # Convert steps into a readable reply
                                assistant_reply = "\n".join(steps)
                                conversation_history.append({"role": "assistant", "content": assistant_reply})
                        except Exception:
                            # If planner fallback fails, keep the original short reply
                            pass
                except Exception:
                    pass

            else:
                # Legacy mode: do not post-process; keep original assistant reply and history behavior
                conversation_history.append({"role": "assistant", "content": assistant_reply})
            return assistant_reply
        else:
            assistant_reply = f"KEVIN server error {response.status_code}: {response.text}"
            return assistant_reply
    except Exception as e:
        return "Connection to KEVIN failed"
    finally:
        send_idle_command()


#function to check current model
def check_model():
    global aiModel
    try:
        with open("config.txt", "r") as file:
            aiModel = file.read().strip()
        if not aiModel:  # If empty, default to virgil
            aiModel = "virgil"
    except FileNotFoundError:
        aiModel = "virgil"  # Default if file doesn't exist

def play_sound(file_path):
    # Headless-safe play_sound: only attempt playback if pygame is available.
    try:
        if pygame is None:
            print(f"[ALICE] play_sound skipped (pygame not available): {file_path}")
            return
        # Initialize mixer if needed
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
        except Exception:
            try:
                pygame.mixer.init()
            except Exception as e:
                print(f"[ALICE] pygame.mixer init failed: {e}")
                return
        try:
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
        except Exception as e:
            print(f"[ALICE] Audio play failed for {file_path}: {e}")
    except Exception as e:
        print(f"[ALICE] play_sound unexpected error: {e}")

# Timer functionality
def set_timer(seconds):
    def timer_thread():
        time.sleep(seconds)
        # Prefer queueing the speak request to the main thread to avoid
        # invoking pyttsx3 from a background thread which can deadlock.
        try:
            if 'speak_queue' in globals() and getattr(globals().get('speak_queue'), 'put_nowait', None):
                speak_queue.put_nowait("Time's up!")
            else:
                speak("Time's up!")
        except queue.Full:
            print("[Timer] Speak queue full, skipping timer alert")
        except Exception as _te:
            try:
                speak("Time's up!")
            except Exception:
                print(f"[Timer] Failed to speak timeup: {_te}")
    threading.Thread(target=timer_thread, daemon=True).start()
    return f"Timer set for {seconds} seconds."

class InactivityManager:
    def __init__(self, speak_fn, listen_state_fn, interval=15, idle_after=300, cooldown=180):
        self.speak_fn = speak_fn
        self.listen_state_fn = listen_state_fn
        self.interval = interval
        self.idle_after = idle_after
        self.cooldown = cooldown
        self._last_activity = time.time()
        self._last_prompt = 0.0
        self._thread = None
        self._stop = threading.Event()
        self.prompts = [
            "Still here when you need me.",
            "Let me know if you'd like to do something.",
            "Whenever you're ready, I can help.",
            "If you have a question, just ask.",
            "wake me...... When you need me",
            "Doo...... do ....do .............doot do",
            "KEEP it CLEAN........RESPECT PUBLIC PROPERTY",
            "WARNING:..................... HITCHIKERS MAY BE ESCAPING CONVICTS",
            "You ever wonder why we're here?"
        ]
    def reset(self):
        self._last_activity = time.time()
    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
    def stop(self):
        if self._thread:
            self._stop.set()
            self._thread = None
    def _run(self):
        import random
        while not self._stop.is_set():
            time.sleep(self.interval)
            now = time.time()
            if now - self._last_activity >= self.idle_after and now - self._last_prompt >= self.cooldown:
                if self.listen_state_fn():
                    # Check for health alerts first
                    if health_alerts:
                        # Speak all pending health alerts
                        for alert in health_alerts:
                            try:
                                if 'speak_queue' in globals() and getattr(globals().get('speak_queue'), 'put_nowait', None):
                                    speak_queue.put_nowait(alert)
                                else:
                                    self.speak_fn(alert)
                            except queue.Full:
                                print(f"[Inactivity] Speak queue full, skipping health alert: {alert[:30]}...")
                            except Exception as _e:
                                try:
                                    self.speak_fn(alert)
                                except Exception as __e:
                                    print(f"[Inactivity] Failed to speak health alert: {_e} / {__e}")
                        # Clear the alerts after speaking them
                        health_alerts.clear()
                    else:
                        # No health alerts, speak a regular inactivity prompt
                        msg = random.choice(self.prompts)
                        try:
                            # If a global speak_queue exists, marshal to it instead of
                            # calling the speak function directly from this background thread.
                            if 'speak_queue' in globals() and getattr(globals().get('speak_queue'), 'put_nowait', None):
                                speak_queue.put_nowait(msg)
                            else:
                                self.speak_fn(msg)
                        except queue.Full:
                            print(f"[Inactivity] Speak queue full, skipping prompt: {msg[:30]}...")
                        except Exception as _e:
                            try:
                                self.speak_fn(msg)
                            except Exception as __e:
                                print(f"[Inactivity] Failed to speak prompt: {_e} / {__e}")
                    self._last_prompt = now

# Replace old inactivity globals
inactivity_manager = InactivityManager(speak, lambda: listening_active and input_mode == "speaking")
# Ensure existing reset_inactivity calls also update manager
old_reset_inactivity = reset_inactivity

def reset_inactivity():
    old_reset_inactivity()
    inactivity_manager.reset()

# Start manager after initialization
try:
    inactivity_manager.start()
except Exception as e:
    print(f"[Inactivity] Failed to start manager: {e}")

# OCR function
def perform_ocr():
    if not ocr_available:
        return "OCR not available. Install pytesseract and Pillow."
    try:
        # Capture screenshot
        screenshot = ImageGrab.grab()
        # Perform OCR
        text = pytesseract.image_to_string(screenshot)
        return text.strip() if text.strip() else "No text found in screenshot."
    except Exception as e:
        return f"OCR error: {e}"

# System health monitoring
def monitor_system_health():
    try:
        import psutil
    except ImportError:
        print("psutil not available, skipping health monitoring")
        return
    while not is_exiting:
        try:
            cpu = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory().percent
            disk = psutil.disk_usage('/').percent
            if cpu > 80:
                alert = f"High CPU usage: {cpu}%"
                print(alert)
                health_alerts.append(alert)
            if memory > 90:
                alert = f"High memory usage: {memory}%"
                print(alert)
                health_alerts.append(alert)
            if disk > 90:
                alert = f"Low disk space: {disk}% used"
                print(alert)
                health_alerts.append(alert)
        except Exception as e:
            print(f"Health monitor error: {e}")
        time.sleep(300)  # Check every 5 minutes

# Start health monitor thread
health_thread = threading.Thread(target=monitor_system_health, daemon=True)

def main():
    global listening_active, is_exiting, guiProcess, flag  # Declare 'flag' as global

    play_sound("aiOpen.mp3")

    face_thread = threading.Thread(target=start_fr)
    face_thread.start()

    #interrupt_thread = threading.Thread(target=listen_for_interrupt, daemon=True)
    
    global aiModel, engine, wake_word
    aiModel = "virgil"
    check_model()

    if aiModel == "alice":
        engine.setProperty('voice', r'HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices\Tokens\TTS_MS_EN-GB_HAZEL_11.0')
    else:  # virgil, vrgl, or any other
        engine.setProperty('voice', r'HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices\Tokens\TTS_MS_EN-US_DAVID_11.0')
    
    global conversation_history
    load_conversation_history()  # Load conversation history at the start
    knowledge = {}  # Dictionary to store learned information
    
    # Initialize user memory and dynamic response handler
    user_mem = user_memory.UserMemory()
    dynamic_handler = dynamic_response.DynamicResponseHandler(user_mem)
    # Initialize agent (dry-run by default for safety)
    global agent
    try:
        # Allow overriding agent dry-run and allowed commands via environment variables for testing
        import os as _os
        _dry = _os.getenv("AGENT_DRY_RUN", "true").lower() not in ("0", "false", "no")
        _allowed = _os.getenv("AGENT_ALLOWED_COMMANDS")
        if _allowed:
            allowed_list = [s.strip() for s in _allowed.split(",") if s.strip()]
        else:
            allowed_list = None
        agent = agents.TerminalAgent(dry_run=_dry, allowed_commands=allowed_list)
        print(f"[Agent] Initialized (dry_run={_dry}, allowed={allowed_list})")
        # Planner instance (can use KEVIN_CHAT_URL via env or ALICE KEVIN_CHAT_URL constant)
        try:
            planner = agents.Planner()
        except Exception:
            planner = None
    except Exception as _e:
        print(f"[Agent] Failed to initialize agent: {_e}")
        agent = None
        planner = None
    
    # Initialize context manager
    context_mgr = context_manager.ContextManager()

    global input_mode
    input_mode = "typing"  # Initialize input mode to typing

    # Initialize game context
    global game_context
    game_context = GameModeContext()
    game_context.set_speaker(speak)
    game_context.set_speak_queue(speak_queue)

    # Start GUI in a separate thread
    send_hello_command()
    guiProcess = None  # Initialize the global variable for GUI process\
    # Start the Amica-ALICE bridge so GUI inputs route through ALICE logic
    try:
        bridge_thread = start_bridge(host=os.getenv('BRIDGE_HOST','127.0.0.1'), port=int(os.getenv('BRIDGE_PORT', '8700')), api_key=os.getenv('BRIDGE_API_KEY'))
        if bridge_thread:
            print(f"[MAIN] Bridge thread started (port={os.getenv('BRIDGE_PORT','8700')})")
    except Exception as _e:
        print(f"[MAIN] Bridge failed to start: {_e}")

    # Start optional ALICE_v2 HTTP endpoint for GUI if FastAPI/uvicorn are available
    try:
        start_alice_http(host=os.getenv('ALICE_HTTP_HOST','127.0.0.1'), port=int(os.getenv('ALICE_HTTP_PORT', '8701')))
    except Exception as _e:
        print(f"[MAIN] Failed to start ALICE HTTP endpoint: {_e}")

    gui_thread = threading.Thread(target=start_gui, daemon=True)
    gui_thread.start()

    # Start health monitor after voice and GUI are set up
    health_thread.start()

    greeting = "Hello " + get_face() + ". How can I assist you?"
    print(greeting)
    speak(greeting, force=True)

    check_tasks()

    wake_word = aiModel.lower()  # Use aiModel as the wake word

    if wake_word == "vrgl":
        wake_word = "virgil"

    background_thread = threading.Thread(target=background_listen, daemon=True)
    background_thread.start()

    flag = False  # Initialize 'flag' here

    # Legacy inactivity thread disabled (superseded by InactivityManager)
    inactivity_thread = None

    # DocQA initialization
    try:
        docqa.build_index()
        docqa.start_watcher()
    except Exception as _e:
        print(f"[DocQA] Initialization failed: {_e}")
    # Remote access server
    try:
        remote_access.start_server()
    except Exception as _re:
        print(f"[Remote] Initialization failed: {_re}")

    # Autonomous file organization thread
    def autonomous_file_organization():
        """Background thread for autonomous file organization"""
        import time
        from dynamic_response import DynamicResponseHandler
        from user_memory import UserMemory
        
        memory = UserMemory()
        handler = DynamicResponseHandler(memory)
        
        while True:
            try:
                # Run file organization every 4 hours
                time.sleep(4 * 60 * 60)  # 4 hours in seconds
                
                # Only organize if there are recent downloads/desktop clutter
                result = handler.organize_files_autonomously()
                if "Organized" in result:
                    print(f"[File Organization] {result}")
                    # Could optionally notify user here
            except Exception as e:
                print(f"[File Organization Error] {e}")
                time.sleep(60 * 60)  # Wait 1 hour before retrying on error

    # Start autonomous file organization thread
    file_org_thread = threading.Thread(target=autonomous_file_organization, daemon=True)
    file_org_thread.start()

    # Autonomous communication hub thread
    def autonomous_communication_hub():
        """Background thread for multi-modal communication management"""
        import time
        from dynamic_response import DynamicResponseHandler
        from user_memory import UserMemory
        
        memory = UserMemory()
        handler = DynamicResponseHandler(memory)
        
        while True:
            try:
                # Check communications every 5 minutes
                time.sleep(5 * 60)
                
                alerts = handler.manage_communication_hub()
                if alerts:
                    print(f"[Communication Hub] Processed {len(alerts)} communications")
                    for alert in alerts:
                        print(f"[Communication Hub] {alert}")
                        
            except Exception as e:
                print(f"[Communication Hub Error] {e}")
                time.sleep(60)

    # Start autonomous communication hub thread
    comm_hub_thread = threading.Thread(target=autonomous_communication_hub, daemon=True)
    comm_hub_thread.start()

    # Autonomous security guardian thread
    def autonomous_security_guardian():
        """Background thread for security and privacy monitoring"""
        import time
        from dynamic_response import DynamicResponseHandler
        from user_memory import UserMemory
        
        memory = UserMemory()
        handler = DynamicResponseHandler(memory)
        
        while True:
            try:
                # Run security checks every 30 minutes
                time.sleep(30 * 60)
                
                security_status = handler.manage_security_guardian()
                
                # Report any issues
                total_issues = (len(security_status.get('network_threats', [])) + 
                              len(security_status.get('password_issues', [])) + 
                              len(security_status.get('vulnerabilities', [])))
                
                if total_issues > 0:
                    print(f"[Security Guardian] Found {total_issues} security issues")
                    for category, issues in security_status.items():
                        if issues:
                            print(f"[Security Guardian] {category}: {issues}")
                else:
                    print("[Security Guardian] Security check completed - no issues found")
                    
            except Exception as e:
                print(f"[Security Guardian Error] {e}")
                time.sleep(60)

    # Start autonomous security guardian thread
    security_thread = threading.Thread(target=autonomous_security_guardian, daemon=True)
    security_thread.start()

    try:
        while flag == False:
            # Process any queued speak requests from threads (e.g., banter) first
            # Limit processing to prevent blocking the main loop with long TTS queues
            try:
                max_speaks_per_iteration = 3  # Process max 3 queued messages per loop
                speaks_processed = 0
                while not speak_queue.empty() and speaks_processed < max_speaks_per_iteration:
                    queued_text = speak_queue.get()
                    print(f"[ModeLoop] Speaking queued: {queued_text}")
                    try:
                        speak(queued_text)
                        speaks_processed += 1
                    except Exception as _s_err:
                        print(f"[ModeLoop] Error speaking queued text: {_s_err}")
                        speaks_processed += 1  # Count failed speaks too
                
                # If there are still more queued messages, log but don't process them all
                if not speak_queue.empty():
                    remaining = speak_queue.qsize()
                    print(f"[ModeLoop] {remaining} additional queued messages deferred to next iteration")
                    
            except Exception as _qerr:
                print(f"[ModeLoop] Speak queue processing error: {_qerr}")
            # Barge-in override: if user interrupted TTS, process that immediately
            remote_session_id = None  # Initialize for this loop iteration
            remote_cmd = remote_access.poll_next_command()
            if remote_cmd:
                query, remote_session_id = remote_cmd
                print("[Remote Command]", query)
                reset_inactivity()
            # Barge-in disabled: remove barge_in_queue processing
            # elif not barge_in_queue.empty():
            #     query = barge_in_queue.get()
            #     reset_inactivity()
            else:
                if input_mode == "typing":
                    query = input("You can type 'exit' to quit or press CTRL + E to switch to speaking mode: ")
                    reset_inactivity()
                elif input_mode == "speaking":
                    if not query_queue.empty():
                        query = query_queue.get()
                        reset_inactivity()
                    else:
                        continue
            print("You:", query)

            numQuery = 1
            queries = []

            # Split the query into separate commands using improved heuristics
            queries = split_commands(query)

            # You can now process each sub-query separately
            for idx, sub_query in enumerate(queries, start=1):
                query = sub_query

                # Handle unintelligible speech
                if "*Unintelligible*" in query:
                    print("Sorry, I didn't get that")
                    speak("Sorry, I didn't get that", force=True, remote_session_id=remote_session_id)
                    continue

                # Quick agent shorthand: allow "run shell: <cmd>" or "run: <cmd>" to invoke the agent directly
                # This bypasses intent routing for explicit shell requests.
                run_match = re.match(r'^\s*(?:run\s+shell|run)\s*:\s*(.+)$', query, flags=re.I)
                if run_match:
                    cmd = run_match.group(1).strip()
                    routed_command = {
                        'action': 'run_shell',
                        'command': cmd,
                        'require_confirmation': True,
                        'use_llm': False
                    }
                    response = execute_routed_command(routed_command, query, context_mgr)
                    print("Assistant:", response)
                    try:
                        speak(response, force=True, remote_session_id=remote_session_id)
                    except Exception:
                        pass
                    try:
                        remote_access.notify(text=response, kind="message")
                    except Exception:
                        pass
                    if context_mgr:
                        try:
                            context_mgr.log_interaction(query, response, 'command', {})
                        except Exception:
                            pass
                    continue

                # Analyze intent and route commands using context manager
                intent = context_mgr.analyze_intent(query)
                entities = context_mgr.extract_entities(query)
                routed_command = context_mgr.route_command(query, intent, entities)

                # Handle different intent types
                if intent == 'command':
                    # Try to execute routed command
                    response = execute_routed_command(routed_command, query, context_mgr)
                    if response is not None:
                        print("Assistant:", response)
                        speak(response, force=True, remote_session_id=remote_session_id)
                        try:
                            remote_access.notify(text=response, kind="message")
                        except Exception:
                            pass
                        # Log the interaction
                        if context_mgr:
                            context_mgr.log_interaction(query, response, intent, entities)
                        continue
                    else:
                        # Command not recognized, fall through to chat
                        pass

                elif intent == 'instruction':
                    # Handle learning commands
                    if 'learn' in query.lower():
                        parts = query.lower().split("learn")
                        if len(parts) == 2 and ":" in parts[1]:
                            key, value = parts[1].split(":")
                            key = key.strip()
                            value = value.strip()
                            knowledge[key] = value
                            response = "Got it! I've learned that {} is {}.".format(key, value)
                            print("Assistant:", response)
                            speak(response, force=True, remote_session_id=remote_session_id)
                            try:
                                remote_access.notify(text=response, kind="message")
                            except Exception:
                                pass
                            if context_mgr:
                                context_mgr.log_interaction(query, response, intent, entities)
                            continue

                # Check knowledge base for any input
                if query.lower() in knowledge:
                    response = knowledge[query.lower()]
                    print("Assistant:", response)
                    speak(response, force=True, remote_session_id=remote_session_id)
                    try:
                        remote_access.notify(text=response, kind="message")
                    except Exception:
                        pass
                    if context_mgr:
                        context_mgr.log_interaction(query, response, intent, entities)
                    continue

                # Check pattern matching for common queries
                pattern_response = None
                for pattern, response_func in patterns.query_patterns.items():
                    if pattern.match(query.lower()):
                        try:
                            if callable(response_func):
                                # Handle functions that take query parameter
                                if 'query' in response_func.__code__.co_varnames:
                                    pattern_response = response_func(query)
                                else:
                                    pattern_response = response_func()
                            else:
                                pattern_response = response_func
                        except Exception as e:
                            print(f"Pattern matching error: {e}")
                            continue
                        break

                if pattern_response is not None:
                    response = pattern_response
                    print("Assistant:", response)
                    speak(response, force=True, remote_session_id=remote_session_id)
                    try:
                        remote_access.notify(text=response, kind="message")
                    except Exception:
                        pass
                    if context_mgr:
                        context_mgr.log_interaction(query, response, intent, entities)
                    continue

                # Fallback to chat with Kevin for everything else
                # Before falling back to the LLM, check for quick inline edits
                try:
                    norm_query = re.sub(r'^(?:plan\s+and\s+execute|plan\s+and\s+run|plan|execute|run|plan\s+execute)\s*:?\s*', '', query, flags=re.I)
                    inline_detect = agents.parse_inline_edit(norm_query)
                except Exception:
                    inline_detect = None

                if inline_detect:
                    # Route directly to plan_and_execute to ensure inline edits are handled synchronously
                    routed_command = {'action': 'plan_and_execute', 'instruction': query}
                    response = execute_routed_command(routed_command, query, context_mgr)
                else:
                    response = chat_with_kevin(query)
                print("Assistant:", response)
                try:
                    remote_access.notify(text=response, kind="message")
                except Exception:
                    pass
                speak(response, force=True, remote_session_id=remote_session_id)

    except KeyboardInterrupt:
        print("Exiting program.")
                    
    finally:
        save_conversation_history()  # Ensure conversation history is saved on exit
        docqa.stop_watcher()  # Gracefully stop DocQA watcher
        # Example graceful shutdown integration (add inside your existing exit/cleanup path if present):
        try:
            docqa.stop_watcher()
        except Exception:
            pass
        try:
            inactivity_manager.stop()
        except Exception:
            pass
        try:
            if context_mgr:
                context_mgr.close()
        except Exception:
            pass
            try:
                hot_reload.stop_hot_reload()
            except Exception:
                pass
            # Future: stop hot reload watcher if implemented
    print("\nEND OF LINE")
    play_sound("aiClose.mp3")
def execute_routed_command(routed_command, query, context_mgr):
    """Execute a command based on the routed command result"""
    global aiModel, wake_word, guiProcess, engine, input_mode
    global agent
    
    if not routed_command:
        return None

    action = routed_command['action']
    confidence = routed_command.get('confidence', 'low')

    # Terminal debug: log entry into execute_routed_command
    try:
        print(f"[ALICE] execute_routed_command called action={action!r} confidence={confidence!r} routed_command={routed_command}")
    except Exception:
        pass

    # Handle different actions
    if action == 'open_program':
        raw_program = routed_command.get('program', '') or ''
        print(f"[ALICE] open_program requested (raw): {raw_program!r}")

        # Normalize separators (newlines, commas, semicolons, 'and', 'then') into a list of targets
        try:
            # Replace Windows-style CRLF and other whitespace with single newline
            norm = re.sub(r'\r\n|\r', '\n', raw_program)
            # Remove obvious role/label prefixes that may come from a system prompt
            # e.g. lines like 'System: ...', 'Assistant: ...', 'User: ...'
            norm = re.sub(r'(?im)^(system|assistant|user)\s*[:\-]\s*', '', norm)

            # Split on newline, semicolon, comma, or the words ' and ', ' then '
            parts = re.split(r'[\n;,]+|\band then\b|\bthen\b|\band\b', norm, flags=re.I)
            candidates = [p.strip().strip('"\'') for p in parts if p and p.strip()]

            # Filter out common tokens that are likely system prompt artifacts
            IGNORE_TOKENS = {"system", "assistant", "user", "jarvis", "tron", "kevin", "alice", "virgil", "amica"}
            cleaned = []
            for p in candidates:
                if not p:
                    continue
                # If the part still contains a role label, remove it
                m = re.match(r'(?i)^(system|assistant|user)\s*[:\-]\s*(.+)$', p)
                if m:
                    p = m.group(2).strip()
                # Lowercase token check against ignore list
                low = p.lower().strip()
                if low in IGNORE_TOKENS:
                    print(f"[ALICE] Ignoring system-token candidate: {p!r}")
                    continue
                # Ignore very short tokens that are unlikely program names (1-2 chars)
                if len(re.sub(r"[^A-Za-z0-9]", "", low)) <= 2:
                    print(f"[ALICE] Ignoring short candidate: {p!r}")
                    continue
                cleaned.append(p)
            candidates = cleaned
        except Exception:
            candidates = [raw_program.strip()]

        if aiModel == "virgil":
            send_working_command()
        else:
            send_blink_command()

        results = []
        for cand in candidates:
            if not cand:
                continue
            print(f"[ALICE] open_program candidate: {cand!r}")
            try:
                resp = open_program(cand)
                results.append({"target": cand, "result": resp})
                print(f"[ALICE] open_program result for {cand!r}: {resp}")
            except Exception as e:
                results.append({"target": cand, "error": str(e)})
                print(f"[ALICE] open_program error for {cand!r}: {e}")

        send_idle_command()
        # Return a combined summary if multiple candidates, else single string/result
        if len(results) == 1:
            r0 = results[0]
            if 'result' in r0:
                return r0['result']
            else:
                return f"error: {r0.get('error') }"
        else:
            return {"status": "ok", "results": results}

    elif action == 'close_program':
        program = routed_command.get('program', '')
        send_working_command()
        response = close_program(program)
        send_idle_command()
        return response

    elif action == 'set_volume':
        level = routed_command.get('level', '')
        # Implement volume setting
        try:
            vol_control = volume_control.VolumeControl()
            if '%' in level:
                vol_level = float(level.strip('%')) / 100
            else:
                vol_level = float(level)
            vol_control.set_volume(vol_level)
            response = f"Volume set to {int(vol_level*100)}%"
        except Exception as e:
            response = f"Failed to set volume: {e}"
        return response

    elif action == 'set_timer':
        duration = routed_command.get('duration', 0)
        unit = routed_command.get('unit', 'seconds')
        # Convert to seconds
        if unit.startswith('minute'):
            duration *= 60
        elif unit.startswith('hour'):
            duration *= 3600
        response = set_timer(duration)
        return response

    elif action == 'plan_and_execute':
        print("[ALICE] plan_and_execute invoked")
        # Use the LLM planner to produce a structured plan (simulation only until approval)
        instruction = routed_command.get('instruction') or routed_command.get('command') or query
        if not instruction:
            return "No instruction provided for planning."
        # Normalize instruction: strip common planning prefixes so inline patterns match
        instr = instruction
        # Remove leading planner/intent prefixes like 'plan and execute:', 'plan and run:', 'execute:', 'plan:'
        # allow optional trailing colon after the prefix by matching the group then optional ':'
        instr = re.sub(r'^(?:plan\s+and\s+execute|plan\s+and\s+run|plan|execute|run|plan\s+execute)\s*:?\s*', '', instr, flags=re.I)
        # First, try to detect a simple inline edit like: 'edit thing.txt to say "VRGL"'
        inline = None
        try:
            inline = agents.parse_inline_edit(instr)
        except Exception:
            inline = None

        if inline and inline.get('type') == 'edit':
            # Resolve path: if path exists use it, otherwise search workspace for filename
            raw_path = inline.get('path')
            # Normalize path and strip quotes
            if isinstance(raw_path, str):
                raw_path = raw_path.strip().strip('\"\'')
            content = inline.get('content', '') or ''
            # If the content is a short reference (e.g., "the declaration of independence")
            # try to expand it by fetching a canonical source.
            def resolve_reference(ref_text: str) -> str | None:
                """If ref_text looks like a short reference to a canonical document,
                return the canonical text (local file preferred). Otherwise return None.
                """
                if not isinstance(ref_text, str):
                    return None
                t = ref_text.strip().lower()
                # Common short forms we want to expand
                candidates = []
                if 'declar' in t or 'independ' in t or 'declaration' in t:
                    candidates.append(('declaration_of_independence', os.path.join(os.path.dirname(__file__), 'documents', 'declaration_of_independence.txt'), 'https://www.archives.gov/founding-docs/declaration-transcript'))
                # Add more known references here as tuples: (key, local_path, fallback_url)

                for key, local_path, url in candidates:
                    # If local copy exists, prefer it
                    try:
                        if os.path.exists(local_path):
                            with open(local_path, 'r', encoding='utf-8') as fh:
                                txt = fh.read()
                            if txt and len(txt) > 50:
                                return txt
                    except Exception:
                        pass
                    # Try web fallback (best-effort)
                    try:
                        r = requests.get(url, timeout=10)
                        if r.status_code == 200 and r.text:
                            html = r.text
                            html = re.sub(r'<br\s*/?>', '\n', html, flags=re.I)
                            html = re.sub(r'</p\s*>', '\n', html, flags=re.I)
                            html = re.sub(r'<script.*?>.*?</script>', '', html, flags=re.S|re.I)
                            html = re.sub(r'<style.*?>.*?</style>', '', html, flags=re.S|re.I)
                            text = re.sub(r'<[^>]+>', '', html)
                            m = re.search(r'(IN\s+CONGRESS\s*,\s*JULY\s*4\s*,\s*1776\.)', text, flags=re.I)
                            fetched = text[m.start():] if m else text
                            fetched = re.sub(r'\n\s*\n+', '\n\n', fetched)
                            fetched = re.sub(r'[ \t]+', ' ', fetched)
                            if len(fetched) > 200:
                                return fetched.strip()
                    except Exception:
                        pass
                return None

            try:
                # Treat as short reference when under a generous threshold
                short_ref = isinstance(content, str) and len(content.split()) < 80
                # Resolve by keyword match or exact short names
                resolved_ref = None
                if short_ref:
                    resolved_ref = resolve_reference(content)
                if resolved_ref:
                    content = resolved_ref
            except Exception:
                # On any error, keep original content
                pass
            resolved = None
            try:
                # Absolute or relative check
                if raw_path and os.path.isabs(raw_path) and os.path.exists(raw_path):
                    resolved = raw_path
                else:
                    # Try relative to repo root (script dir)
                    if raw_path:
                        cand = os.path.join(os.path.dirname(__file__), raw_path)
                        if os.path.exists(cand):
                            resolved = cand
                    else:
                        # Walk workspace to find matching basename
                        if raw_path:
                            target_name = os.path.basename(raw_path)
                            for root, dirs, files in os.walk(os.path.dirname(__file__)):
                                if target_name in files:
                                    resolved = os.path.join(root, target_name)
                                    break
                # If still not found, create file in script dir
                if not resolved:
                    # Use a normalized path (basename) when creating so repeated runs target same file
                    use_name = os.path.basename(raw_path) if raw_path else "untitled.txt"
                    resolved = os.path.join(os.path.dirname(__file__), use_name)

                # Copyright safeguard: do not fetch/write full text for likely-copyrighted works
                copyrighted_keywords = ['hobbit', 'tolkien', 'lord of the rings', 'harry potter', 'game of thrones']
                lower_content = (content or '').lower()
                is_copyrighted_request = any(k in lower_content for k in copyrighted_keywords)
                if is_copyrighted_request and not os.path.exists(os.path.join(os.path.dirname(__file__), 'documents', 'declaration_of_independence.txt')):
                    # If user requested a likely copyrighted work and we don't have a local copy, refuse to auto-insert the full text.
                    return "I can't fetch or insert full copyrighted works automatically. I can summarize it or you can paste the exact text to insert."

                file_editor = agents.FileEditor()
                res = file_editor.apply_edit(resolved, content, dry_run=getattr(agent, 'dry_run', True), make_backup=True)

                plan_record = {"instruction": instruction, "raw": instr, "steps": [inline], "timestamp": time.time(), "result": res}
                try:
                    with open(last_plan_path, "w", encoding="utf-8") as f:
                        json.dump(plan_record, f, indent=2)
                except Exception as _e:
                    print(f"[Planner] Failed to write last plan: {_e}")

                if res.get('ok'):
                    return f"Edited file: {resolved} (dry_run={res.get('dry_run', False)})"
                else:
                    return f"Failed to edit {resolved}: {res.get('error') or res}"

            except Exception as _e:
                return f"Inline edit failed: {_e}"

        # Prefer the Planner's LLM decomposition (it includes defensive re-prompts and JSON parsing).
        # Fall back to chat_with_kevin() only if no planner is available.
        raw = ""
        parsed = []
        try:
            if 'planner' in globals() and planner:
                # planner.plan_with_llm returns a list of step strings (may include EDIT blocks)
                try:
                    steps = planner.plan_with_llm(instruction, kevin_chat_url=(KEVIN_CHAT_URL if 'KEVIN_CHAT_URL' in globals() else None))
                    # join into a pseudo-raw for parse_structured_steps which expects textual blocks
                    raw = "\n".join(steps or [])
                except Exception:
                    raw = ""
            else:
                raw = chat_with_kevin(instruction, speak_to_kevin=False, overrides={"profile": "copilot"})
        except Exception:
            raw = ""

        # Parse structured steps using agents helper; if parsing fails, fall back to treating each planner step as a run
        try:
            if raw:
                parsed = agents.parse_structured_steps(raw)
            else:
                # If planner returned structured step list directly, convert to parsed dicts
                if 'steps' in locals() and isinstance(steps, list) and steps:
                    parsed = []
                    for s in steps:
                        # if looks like an EDIT block, try to parse it
                        if isinstance(s, str) and s.strip().upper().startswith('EDIT'):
                            parsed.extend(agents.parse_structured_steps(s))
                        else:
                            parsed.append({"type": "run", "cmd": s})
                else:
                    parsed = [{"type": "run", "cmd": instruction}]
        except Exception as _e:
            parsed = [{"type": "run", "cmd": instruction}]

        plan_record = {"instruction": instruction, "raw": raw, "steps": parsed, "timestamp": time.time()}
        try:
            with open(last_plan_path, "w", encoding="utf-8") as f:
                json.dump(plan_record, f, indent=2)
        except Exception as _e:
            print(f"[Planner] Failed to write last plan: {_e}")

        # Summarize for user and queue it
        summary_lines = []
        for s in parsed:
            if s.get('type') == 'run':
                summary_lines.append(f"RUN: {s.get('cmd')}")
            elif s.get('type') == 'edit':
                summary_lines.append(f"EDIT: {s.get('path')} (content {len(s.get('content') or '')} chars)")
            else:
                summary_lines.append(str(s))

        summary = f"Planned {len(parsed)} steps for: {instruction}\n" + "\n".join(summary_lines)
        # Terminal debug: summary of planned steps
        try:
            print(f"[ALICE] plan summary:\n{summary}")
        except Exception:
            pass
        try:
            if 'speak_queue' in globals() and getattr(speak_queue, 'put_nowait', None):
                speak_queue.put_nowait(summary)
            else:
                speak(summary)
        except Exception:
            pass

        # Notify remote clients with the plan and how to approve
        try:
            remote_access.notify(text=summary + "\nReply 'approve plan' to execute or 'reject plan' to cancel.", kind="plan")
        except Exception:
            pass

        return summary

    elif action == 'approve_plan':
        # Execute the last saved plan (must exist)
        try:
            if not os.path.exists(last_plan_path):
                return "No saved plan to approve."
            with open(last_plan_path, "r", encoding="utf-8") as f:
                plan_record = json.load(f)
        except Exception as _e:
            return f"Failed to load plan: {_e}"

        steps = plan_record.get('steps', [])
        results = []
        file_editor = agents.FileEditor()
        for step in steps:
            try:
                if step.get('type') == 'run':
                    cmd = step.get('cmd')
                    # Execute via agent (agent.run will honor dry_run)
                    res = agent.run(cmd, require_confirmation=False)
                    results.append({"type": "run", "cmd": cmd, "result": res})
                elif step.get('type') == 'edit':
                    path = step.get('path')
                    content = step.get('content') or ''
                    res = file_editor.apply_edit(path, content, dry_run=getattr(agent, 'dry_run', True))
                    results.append({"type": "edit", "path": path, "result": res})
                else:
                    # unknown, try to run as shell
                    cmd = step.get('cmd') or str(step)
                    res = agent.run(cmd, require_confirmation=False)
                    results.append({"type": "run", "cmd": cmd, "result": res})
            except Exception as e:
                results.append({"error": str(e), "step": step})

        # Save executed results alongside plan
        try:
            plan_record['executed'] = results
            with open(last_plan_path, "w", encoding="utf-8") as f:
                json.dump(plan_record, f, indent=2)
        except Exception:
            pass

        # Return a short summary
        return f"Executed {len(results)} steps. Results written to last_plan.json."

    elif action == 'reject_plan':
        try:
            if os.path.exists(last_plan_path):
                os.remove(last_plan_path)
            return "Plan rejected and removed."
        except Exception as _e:
            return f"Failed to remove plan: {_e}"

    elif action == 'run_shell':
        # Execute a shell command via the agent for safer, logged execution.
        cmd = routed_command.get('command') or routed_command.get('cmd')
        print(f"[ALICE] run_shell requested cmd={cmd}")
        require_confirmation = routed_command.get('require_confirmation', False)
        if not cmd:
            return "No command provided."
        # If requested, ask the LLM planner (KEVIN) to decompose into steps
        use_llm = routed_command.get('use_llm', False)
        try:
            if use_llm and 'planner' in globals() and planner:
                # Ask planner to produce steps via KEVIN if possible
                kevin_url = KEVIN_CHAT_URL if 'KEVIN_CHAT_URL' in globals() else None
                steps = planner.plan_with_llm(cmd, kevin_chat_url=kevin_url)
                # Simulate via agent (require_confirmation=True to prevent accidental execution)
                sim = planner.execute_plan(cmd, agent=agent, confirm=False) if planner else {"plan": steps}
                # Return plan summary and simulation results to user instead of executing immediately
                summary = f"Planned {len(steps)} step(s):\n" + "\n".join(steps)
                # Queue the spoken summary (non-blocking)
                try:
                    if 'speak_queue' in globals() and getattr(speak_queue, 'put_nowait', None):
                        speak_queue.put_nowait(summary)
                    else:
                        speak(summary)
                except Exception:
                    pass
                return summary

            # Default: use agent.run for single command
            if 'agent' in globals() and agent:
                result = agent.run(cmd, require_confirmation=require_confirmation)
                if result.get('ok'):
                    return result.get('stdout') or "(command executed)"
                else:
                    return f"Command failed: {result.get('error') or result.get('record', {})}"
            else:
                return f"Agent unavailable; dry-run: {cmd}"
        except Exception as e:
            return f"Shell execution error: {e}"

    elif action == 'check_email':
        try:
            response = email_manager.check_inbox()
        except Exception as e:
            response = f"Email check failed: {e}"
        return response

    elif action == 'read_email':
        try:
            response = email_manager.read_specific_email()
        except Exception as e:
            response = f"Email read failed: {e}"
        return response

    elif action == 'start_network_monitor':
        start_network_monitor()
        return "Network monitoring started."

    elif action == 'stop_network_monitor':
        end_network_monitor()
        return "Network monitoring stopped."

    elif action == 'toggle_input_mode':
        toggle_input_mode()
        return f"Switched to {input_mode} mode."

    elif action == 'analyze_screen':
        send_working_command()
        response = perform_ocr()
        send_idle_command()
        return response

    elif action == 'enter_game_mode':
        response = game_context.enter_mode()
        return response

    elif action == 'exit_game_mode':
        response = game_context.exit_mode()
        return response

    elif action == 'add_task':
        task = routed_command.get('task', '')
        try:
            tlist = todo.TodoList()
            tlist.load_tasks("todo_data.json")
            tlist.add_task(task)
            tlist.save_tasks("todo_data.json")
            response = f"Added task: {task}"
        except Exception as e:
            response = f"Failed to add task: {e}"
        return response

    elif action == 'solve_math':
        send_math_command()
        response = solve_math_problem(query)
        return response

if __name__ == "__main__":
    main()
