import os
import json
import re
import requests
from typing import Any, Dict, Optional, Tuple

username = os.getenv("USERNAME") or os.getlogin()

# Optional tool registry to allow tool-style invocation; fall back safely
try:
    from tools import registry as tool_registry
except Exception:
    try:
        import importlib
        tool_registry = importlib.import_module("tools.registry")
    except Exception:
        # Last-resort: load the local tools/registry.py by path to avoid conflicts
        try:
            import importlib.util, pathlib
            root = pathlib.Path(__file__).resolve().parent
            candidate = root / "tools" / "registry.py"
            if candidate.exists():
                spec = importlib.util.spec_from_file_location("local_tools_registry", str(candidate))
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                tool_registry = mod
            else:
                tool_registry = None
        except Exception:
            tool_registry = None
# Ensure tool_registry exposes expected API; if not, ignore it
if tool_registry is not None and not hasattr(tool_registry, "call_tool"):
    tool_registry = None
# Use the same default as ALICE, but allow standalone usage
KEVIN_URL = os.getenv("KEVIN_URL", "http://127.0.0.1:5000")
# Optional lightweight classifier service (e.g., smaller model on another port)
KEVIN_CLASSIFIER_URL = os.getenv("KEVIN_CLASSIFIER_URL", KEVIN_URL)

# We import pattern handlers lazily to avoid circular imports during ALICE import
_patterns = None

def _patterns_module():
    global _patterns
    if _patterns is None:
        import patterns as _p
        _patterns = _p
    return _patterns

# Command registry: name -> spec
# description informs the LLM; handler is resolved at runtime from patterns
COMMAND_SPECS: Dict[str, Dict[str, Any]] = {
    "get_time": {"description": "Tell the current date and time.", "handler": "get_time", "args": {}},
    "get_date": {"description": "Tell today's date.", "handler": "get_date", "args": {}},
    "start_timer": {
        "description": "Start a timer for a duration.",
        "handler": "start_timer",
        "args": {"duration": "string like '10 minutes', '30 seconds', or a number of seconds"},
    },
    "set_volume": {
        "description": "Set system volume to a level (0-100 or 0.0-1.0).",
        "handler": "volume_control_helper",
        "args": {"volume": "number"},
    },
    "mute": {"description": "Mute the system volume.", "handler": "mute_command", "args": {}},
    "lock_computer": {"description": "Lock the current computer immediately.", "handler": "lock_computer", "args": {}},
    "analyze_screen": {"description": "Analyze the current screen for objects and text.", "handler": "analyze_screen", "args": {}},
    "open_menu": {"description": "Open the meal planner menu.", "handler": "open_menu", "args": {}},
    "check_inbox": {"description": "Check email inbox for messages.", "handler": "check_inbox", "args": {}},
    "read_email": {"description": "Read a specific email (last or matching).", "handler": "read_specific_email", "args": {}},
    "send_email": {"description": "Compose and send an email.", "handler": "send_email", "args": {}},
    "scan_email": {"description": "Start watching inbox for new emails.", "handler": "scan_email", "args": {}},
    "start_game_detection": {
        "description": "Start the game detection loop.",
        "handler": "start_game_detection_loop",
        "args": {},
    },
    # Game mode management
    "enter_game_mode": {
        "description": "Activate game mode for stratagem input (Helldivers style).",
        "handler": "enter_game_mode",
        "args": {},
    },
    "exit_game_mode": {
        "description": "Exit the active game mode.",
        "handler": "exit_game_mode",
        "args": {},
    },
    "list_stratagems": {
        "description": "List available stratagem commands in game mode.",
        "handler": "list_stratagems",
        "args": {},
    },
    "import_documents": {
        "description": "Open a file picker to import local text/markdown documents for semantic search (deduplicated).",
        "handler": "import_documents",
        "args": {},
    },
    # Task management
    "add_task": {
        "description": "Add a task to the to-do list (natural language).",
        "handler": "add_task_command",
        "args": {"task": "task description"},
    },
    "list_tasks": {
        "description": "List current tasks in the to-do list.",
        "handler": "list_tasks_command",
        "args": {},
    },
    "remove_task": {
        "description": "Remove a task by number.",
        "handler": "remove_task_command",
        "args": {"number": "task number (1-based)"},
    },
    "clear_tasks": {
        "description": "Clear all tasks after confirmation.",
        "handler": "clear_tasks_command",
        "args": {},
    },
    "test_notification": {
        "description": "Send a test notification to connected remote clients (phone).",
        "handler": "test_notification_command",
        "args": {"message": "optional message text"},
    },
    "organize_files": {
        "description": "Automatically organize files in Downloads and Desktop based on type and usage patterns.",
        "handler": "organize_files_command",
        "args": {},
    },
}
# Extend manifest with search commands
COMMAND_SPECS.update({
    "search_web": {
        "description": "Search the web and open the top result.",
        "handler": "search_web_command",
        "args": {"query": "string query"},
    },
    "search_youtube": {
        "description": "Search YouTube and open the top video.",
        "handler": "search_youtube_command",
        "args": {"query": "string query"},
    },
    "doc_query": {
        "description": "Answer a question using local documents (semantic search).",
        "handler": "doc_query_command",
        "args": {"question": "string natural language question"},
    },
})

_CLASSIFIER_INSTRUCTIONS = (
    "You are an intent classifier for a voice assistant. Decide if the user's text is a COMMAND "
    "(to execute one of the listed actions) or CHIT_CHAT (general conversation). Return ONLY a single JSON object\n"
    "with keys: intent ('command'|'chit_chat'), action (string|null), arguments (object), confidence (0..1), reasoning (string).\n"
    "Choose an action from this list only and extract arguments when applicable.\n"
)


def _commands_manifest() -> str:
    lines = []
    for name, spec in COMMAND_SPECS.items():
        args_desc = ", ".join(f"{k}: {v}" for k, v in spec.get("args", {}).items()) or "(no args)"
        lines.append(f"- {name}: {spec['description']} Args: {args_desc}")
    return "\n".join(lines)


def _build_classify_prompt(user_text: str) -> str:
    manifest = _commands_manifest()
    return (
        f"Instruction: {_CLASSIFIER_INSTRUCTIONS}\n"
        f"Commands:\n{manifest}\n\n"
        f"User: {user_text}\n"
        f"Assistant: Return JSON only."
    )


def _extract_json(s: str) -> Optional[Dict[str, Any]]:
    # Try direct parse
    try:
        return json.loads(s)
    except Exception:
        pass
    # Try to find the first {...} block
    m = re.search(r"\{[\s\S]*\}", s)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def classify_intent(user_text: str) -> Dict[str, Any]:
    prompt = _build_classify_prompt(user_text)
    payload = {
        "text": prompt,
        "use_history": False,
        # classification profile (fast/lightweight)
        "profile": "classify",
        "max_tokens": 48,
        "temp": 0.0,
        "top_p": 0.8,
        "top_k": 20,
        "repeat_penalty": 1.0,
    }
    try:
        r = requests.post(f"{KEVIN_CLASSIFIER_URL}/query", json=payload, timeout=8)
        r.raise_for_status()
        resp = r.json()
        raw = resp.get("response", "")
        data = _extract_json(raw) or {}
    except Exception:
        data = {}
    # Defaults
    intent = str(data.get("intent", "")).lower()
    if intent not in ("command", "chit_chat"):
        intent = "chit_chat"
    return {
        "intent": intent,
        "action": data.get("action"),
        "arguments": data.get("arguments", {}) or {},
        "confidence": float(data.get("confidence", 0.0) or 0.0),
        "reasoning": data.get("reasoning", ""),
    }


def _is_information_query(text: str) -> bool:
    t = text.lower().strip()
    # Phrases indicating definitional / informational queries
    if re.match(r"^(what\s+is|who\s+is|what\s+are|define|explain|tell\s+me\s+about|how\s+does|how\s+do|why\s+is)\b", t):
        # If it also includes strong device-control keywords, don't suppress
        control_keywords = ("timer", "volume", "mute", "lock", "open", "close", "shutdown", "restart")
        if not any(ck in t for ck in control_keywords):
            return True
    # Specific safe terms that previously collided (e.g., 'blockchain' contains 'lock')
    if "blockchain" in t or "block chain" in t:
        return True
    return False


def _is_potential_command(text: str) -> bool:
    t = text.lower()
    if _is_information_query(t):
        return False
    verbs = [
    "set", "start", "begin", "create", "make", "turn", "increase", "raise", "decrease", "lower", "search", "google", "youtube", "enter", "activate",
        "open", "lock", "check", "read", "send", "scan", "analyze"
    ]
    keywords = [
        "timer", "volume", "mute", "unmute", "menu", "inbox", "email", "screen", "computer", "device"
    ]
    # game mode related keywords should also hint it's a command
    if "game mode" in t:
        return True
    # Use word boundaries to avoid substring collisions (e.g., 'lock' inside 'blockchain')
    if any(re.search(rf"\b{re.escape(v)}\b", t) for v in verbs):
        return True
    if any(re.search(rf"\b{re.escape(k)}\b", t) for k in keywords):
        return True
    return False


def _fast_preclassify(user_text: str) -> Optional[Dict[str, Any]]:
    """Heuristic intent detection to avoid model calls for common commands."""
    t = user_text.lower().strip()

    # Common generic question setups -> treat explicitly as chit-chat (NOT a command)
    if re.match(r"^(what|who|when|where|why|how)\b", t):
        return {"intent": "chit_chat", "action": None, "arguments": {}, "confidence": 0.7}

    # Volume and mute
    if any(w in t for w in ("volume", "louder", "softer", "mute", "unmute", "raise", "lower", "increase", "decrease")):
        if "mute" in t and "unmute" not in t:
            return {"intent": "command", "action": "mute", "arguments": {}, "confidence": 0.95}
        vol_args = _extract_volume_args(user_text)
        if vol_args:
            return {"intent": "command", "action": "set_volume", "arguments": vol_args, "confidence": 0.85}

    # Timer
    if "timer" in t or re.search(r"\b(remind me|alarm)\b", t):
        dur = _extract_timer_duration_text(user_text)
        return {
            "intent": "command",
            "action": "start_timer",
            "arguments": ({"duration": dur} if dur else {}),
            "confidence": 0.85,
        }

    # Date/time
    if re.search(r"what(\s+is)?\s+the\s+time|what\s*time\s*is\s*it|time\s*please", t):
        return {"intent": "command", "action": "get_time", "arguments": {}, "confidence": 0.9}
    if re.search(r"what(\s+is)?\s+today'?s?\s+date|what\s*day\s*is\s*it|date\s*please", t):
        return {"intent": "command", "action": "get_date", "arguments": {}, "confidence": 0.9}

    # Screen analysis
    if any(phrase in t for phrase in ("what's on my screen", "what is on my screen", "analyze screen", "scan screen")):
        return {"intent": "command", "action": "analyze_screen", "arguments": {}, "confidence": 0.9}

    # Lock
    if re.search(r"\block(\s+(computer|pc|device))?\b", t):
        return {"intent": "command", "action": "lock_computer", "arguments": {}, "confidence": 0.9}

    # Menu
    if re.search(r"\b(menu|menu planner|food planner|recipes|recipe book)\b", t):
        if any(v in t for v in ("open", "start", "launch", "show")):
            return {"intent": "command", "action": "open_menu", "arguments": {}, "confidence": 0.8}

    # Game mode (enter / exit / list)
    if re.search(r"\b(enter|start|activate) game mode\b", t):
        return {"intent": "command", "action": "enter_game_mode", "arguments": {}, "confidence": 0.92}
    if re.search(r"\b(exit|leave|stop|cancel) game mode\b", t):
        return {"intent": "command", "action": "exit_game_mode", "arguments": {}, "confidence": 0.92}
    if "list stratagems" in t or ("list commands" in t and "game" in t):
        return {"intent": "command", "action": "list_stratagems", "arguments": {}, "confidence": 0.85}

    # Email
    if "inbox" in t or "email" in t:
        if any(v in t for v in ("check", "watch", "scan")):
            return {"intent": "command", "action": "scan_email", "arguments": {}, "confidence": 0.8}
        if any(v in t for v in ("read", "expand")):
            return {"intent": "command", "action": "read_email", "arguments": {}, "confidence": 0.8}
        if "send" in t:
            return {"intent": "command", "action": "send_email", "arguments": {}, "confidence": 0.8}

    # Web/YouTube search quick path
    if re.search(r"\bsearch (?:the )?web for\b", t):
        q = _extract_search_query(user_text)
        return {"intent": "command", "action": "search_web", "arguments": ({"query": q} if q else {}), "confidence": 0.9}
    if re.search(r"\bsearch on youtube for\b", t):
        q = _extract_search_query(user_text)
        return {"intent": "command", "action": "search_youtube", "arguments": ({"query": q} if q else {}), "confidence": 0.9}

    # Doc query heuristic
    if re.search(r"\b(search|look) (?:my )?(documents|docs|notes) for\b", t) or re.search(r"\bfrom my (documents|docs|notes)\b", t):
        # Extract portion after the trigger phrase; fallback to full text
        m = re.search(r"(?:search|look)(?: in| through)? (?:my )?(?:documents|docs|notes) for (.+)$", t)
        question = m.group(1).strip() if m else user_text.strip()
        return {"intent": "command", "action": "doc_query", "arguments": {"question": question}, "confidence": 0.85}

    # Import documents heuristic
    if re.search(r"\b(import|add|ingest|load) (?:my )?(documents|docs|files)\b", t):
        return {"intent": "command", "action": "import_documents", "arguments": {}, "confidence": 0.9}

    # Task heuristics
    # Add task: "add <something> (to (my) (tasks|todo list))" or "remember to <do X>"
    m_add = re.search(r"\badd (.+?) (?:to )?(?:my )?(?:to-?do|tasks?|list)\b", t)
    if m_add:
        task_txt = m_add.group(1).strip()
        return {"intent": "command", "action": "add_task", "arguments": {"task": task_txt}, "confidence": 0.9}
    m_add2 = re.search(r"remember to (.+)$", t)
    if m_add2:
        task_txt = m_add2.group(1).strip()
        return {"intent": "command", "action": "add_task", "arguments": {"task": task_txt}, "confidence": 0.85}
    # List tasks
    if re.search(r"\b(what (do i|do we) (have|need) (to do)?( today)?|list (my )?tasks|show (me )?(my )?tasks|what's on (my )?to-?do|to-?do list)\b", t):
        return {"intent": "command", "action": "list_tasks", "arguments": {}, "confidence": 0.9}
    # Remove task by number
    m_rem = re.search(r"\b(remove|delete) (?:task )?(\d+)\b", t)
    if m_rem:
        num = int(m_rem.group(2))
        return {"intent": "command", "action": "remove_task", "arguments": {"number": num}, "confidence": 0.9}
    # Clear tasks
    if re.search(r"\b(clear|delete|remove) (all )?(tasks|to-?do list)\b", t):
        return {"intent": "command", "action": "clear_tasks", "arguments": {}, "confidence": 0.85}

    # Notification test heuristic
    if re.search(r"\b(test (the )?(vrgl )?notification|notify my phone)\b", t):
        # Extract optional message after 'notify my phone'
        m_msg = re.search(r"notify my phone(?: about| with| that)? (.+)$", t)
        args = {"message": m_msg.group(1).strip()} if m_msg else {}
        return {"intent": "command", "action": "test_notification", "arguments": args, "confidence": 0.95}

    return None


### Helper: invoke via registry when available, otherwise call function directly.
_DANGEROUS_ACTIONS = set(["lock_computer", "clear_tasks"])

def _invoke_handler(handler_name: str, func, *args, action: str | None = None, **kwargs):
    """Try calling a registered tool first, then fall back to direct function call.
    For dangerous actions, require environment flag `ALICE_ALLOW_DANGEROUS=1` to proceed.
    Returns the result or an error string.
    """
    # Permission gating for dangerous actions
    if action and action in _DANGEROUS_ACTIONS:
        if os.getenv("ALICE_ALLOW_DANGEROUS", "0") != "1":
            return f"Action '{action}' requires confirmation before execution. Set ALICE_ALLOW_DANGEROUS=1 to allow."

    # Try registry if available
    if tool_registry is not None:
        # Try multiple candidate tool names; registry may have either the bare handler name
        # or namespaced entries like 'intent.<name>' depending on registration approach.
        candidates = [handler_name, f"intent.{handler_name}", f"patterns.{handler_name}"]
        for name in candidates:
            try:
                res = tool_registry.call_tool(name, *args, **kwargs)
            except Exception as e:
                res = {"ok": False, "result": None, "error": str(e)}
            if res and isinstance(res, dict):
                if res.get("ok"):
                    return res.get("result")
                # If registry reports 'not found', continue to next candidate; otherwise return error
                if res.get("error") and "not found" not in (res.get("error") or ""):
                    return f"Tool error: {res.get('error')}"

    # Fall back to direct function call
    if callable(func):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            return f"Error executing {handler_name}: {e}"
    return None

# Improve duration extractor to catch "in 10 minutes" and shorthand
def _extract_timer_duration_text(user_text: str) -> Optional[str]:
    text = user_text.lower()
    m = re.search(r"(\d+\s*(?:seconds?|secs?|minutes?|mins?|hours?|hrs?))", text)
    if m:
        return m.group(1)
    m = re.search(r"(?:for|in)\s+(\d+\s*(?:seconds?|secs?|minutes?|mins?|hours?|hrs?))", text)
    if m:
        return m.group(1)
    return None


def _extract_volume_args(user_text: str) -> Dict[str, float]:
    """Return either {"volume": abs_0_1} or {"delta": signed_0_1} if detectable; else {}."""
    text = user_text.lower().strip()
    # Detect direction words
    up_words = ("up", "increase", "raise", "louder", "boost")
    down_words = ("down", "decrease", "lower", "softer", "reduce")
    is_up = any(w in text for w in up_words)
    is_down = any(w in text for w in down_words)

    # Percent specified
    m_pct = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if m_pct:
        val_pct = float(m_pct.group(1))
        frac = max(0.0, min(1.0, val_pct / 100.0))
        if is_up or is_down:
            return {"delta": frac if is_up else -frac}
        # If phrasing contains 'to' or 'at', treat as absolute
        if re.search(r"\b(to|at)\b", text):
            return {"volume": frac}
        # Default to absolute percent when no direction
        return {"volume": frac}

    # Plain number could be 0-100 or 0-1
    m_num = re.search(r"\b(\d+(?:\.\d+)?)\b", text)
    if m_num:
        val = float(m_num.group(1))
        if val > 1.0:
            frac = max(0.0, min(1.0, val / 100.0))
        else:
            frac = max(0.0, min(1.0, val))
        if is_up or is_down:
            return {"delta": frac if is_up else -frac}
        if re.search(r"\b(to|at)\b", text):
            return {"volume": frac}
        # ambiguous; prefer absolute
        return {"volume": frac}

    # Words like "max", "minimum"
    if "max" in text or "maximum" in text:
        return {"volume": 1.0}
    if "min" in text or "minimum" in text or "mute" in text:
        return {"volume": 0.0}

    # Direction with no amount: small step
    if is_up:
        return {"delta": 0.05}
    if is_down:
        return {"delta": -0.05}

    return {}


def _coerce_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        s = str(value).strip()
        if s.endswith("%"):
            return float(s[:-1])
        return float(s)
    except Exception:
        return None


def _extract_search_query(user_text: str) -> Optional[str]:
    t = user_text.strip()
    # Web search phrasings
    for pat in [
        r"\bsearch (?:the )?web for (.+)$",
        r"\bsearch for (.+)$",
        r"\bsearch\s+(.+)$",
        r"\bgoogle\s+(.+)$",
        r"\blook up\s+(.+)$",
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            q = m.group(1).strip()
            # Strip leading stopwords like 'for'
            q = re.sub(r"^(for|about)\s+", "", q, flags=re.IGNORECASE)
            return q
    # YouTube search phrasings
    for pat in [
        r"\bsearch (?:on )?youtube for (.+)$",
        r"\byoutube search for (.+)$",
        r"\byoutube\s+(.+)$",
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            q = m.group(1).strip()
            q = re.sub(r"^(for|about)\s+", "", q, flags=re.IGNORECASE)
            return q
    return None


def route_and_execute(user_text: str) -> Optional[str]:
    """Classify with KEVIN and execute mapped command if confident. Returns response or None."""
    # If game mode is active, let it attempt to interpret any input first (stratagem names etc.)
    try:
        p = _patterns_module()
        gm_interp = getattr(p, "game_mode_interpret", None)
        if callable(gm_interp):
            gm_resp = gm_interp(user_text)
            if gm_resp:
                return gm_resp
    except Exception:
        pass
    # Fast heuristic path first
    fast = _fast_preclassify(user_text)
    if fast:
        # If heuristic says it's chit-chat (or anything not a command), skip command routing
        if fast.get("intent") != "command":
            return None
        action = fast.get("action")
        if action in COMMAND_SPECS:
            # Extra guard: ensure lock command only fires on explicit 'lock' word, not substrings
            if action == "lock_computer" and not re.search(r"\block\b", user_text.lower()):
                pass  # treat as not a valid command trigger
            else:
                p = _patterns_module()
                handler_name = COMMAND_SPECS[action]["handler"]
                handler = getattr(p, handler_name, None)
                if callable(handler):
                    args = fast.get("arguments", {}) or {}
                    try:
                        if action in ("search_web", "search_youtube"):
                            q = args.get("query") or _extract_search_query(user_text)
                            return _invoke_handler(handler_name, handler, query=q) if q else _invoke_handler(handler_name, handler)
                        if action == "doc_query":
                            q = args.get("question")
                            return _invoke_handler(handler_name, handler, question=q) if q else _invoke_handler(handler_name, handler)
                        if action == "start_timer":
                            dur = args.get("duration")
                            return _invoke_handler(handler_name, handler) if not dur else _invoke_handler(handler_name, handler, duration=str(dur))
                        if action == "set_volume":
                            if "delta" in args:
                                return _invoke_handler(handler_name, handler, delta=float(args["delta"]))
                            if "volume" in args:
                                return _invoke_handler(handler_name, handler, volume=float(args["volume"]))
                            return _invoke_handler(handler_name, handler)
                        if action == "test_notification":
                            msg = args.get("message") if args else None
                            return _invoke_handler(handler_name, handler, msg) if msg else _invoke_handler(handler_name, handler)
                        return _invoke_handler(handler_name, handler, action=action)
                    except Exception as e:
                        return f"Error executing {action}: {e}"

    # If it doesn't look like a command at all, skip KEVIN classification (let chat handle it)
    if not _is_potential_command(user_text):
        return None

    # Ambiguous commands: ask KEVIN to classify
    result = classify_intent(user_text)
    if result.get("intent") != "command" or result.get("confidence", 0.0) < 0.6:
        return None
    action = result.get("action")
    if not action or action not in COMMAND_SPECS:
        return None
    # Guard lock command again post-classification
    if action == "lock_computer" and not re.search(r"\block(\s+(computer|pc|device))?\b", user_text.lower()):
        return None
    p = _patterns_module()
    spec = COMMAND_SPECS[action]
    handler_name = spec["handler"]
    func = getattr(p, handler_name, None)
    if not callable(func):
        return None
    args = result.get("arguments", {}) or {}
    try:
        if action in ("search_web", "search_youtube"):
            q = args.get("query") or _extract_search_query(user_text)
            return _invoke_handler(handler_name, func, query=q) if q else _invoke_handler(handler_name, func)
        if action == "doc_query":
            q = args.get("question")
            return _invoke_handler(handler_name, func, question=q) if q else _invoke_handler(handler_name, func)
        if action == "start_timer":
            duration = args.get("duration") or _extract_timer_duration_text(user_text)
            return _invoke_handler(handler_name, func) if not duration else _invoke_handler(handler_name, func, duration=str(duration))
        if action == "set_volume":
            vol_args = _extract_volume_args(user_text)
            if not vol_args:
                vol = _coerce_number(args.get("volume"))
                if vol is not None:
                    vol_args = {"volume": vol}
            if "delta" in vol_args:
                return _invoke_handler(handler_name, func, delta=float(vol_args["delta"]))
            if "volume" in vol_args:
                return _invoke_handler(handler_name, func, volume=float(vol_args["volume"]))
            return _invoke_handler(handler_name, func)
        if action == "test_notification":
            msg = args.get("message") if args else None
            return _invoke_handler(handler_name, func, msg) if msg else _invoke_handler(handler_name, func)
        # No-arg commands
        return _invoke_handler(handler_name, func, action=action)
    except Exception as e:
        return f"Error executing {action}: {e}"
