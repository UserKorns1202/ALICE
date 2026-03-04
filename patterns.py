import datetime
import email_manager
import Timer
import random
# import ALICE
import re
import volume_control
import ctypes
import os
import screen_analysis
import menuplanner
import threading
import asyncio
import search
import web_search
import music_control
import docqa
import todo
import importlib
import remote_access  # for notification testing
try:
    # Prefer tools.system_tools when available in package layout
    from tools import system_tools
except Exception:
    try:
        import system_tools
        system_tools = system_tools
    except Exception:
        system_tools = None
# Game mode integration
try:
    import game_mode
    _GAME_MODE_CTX = game_mode.GameModeContext()
    # Inject ALICE.speak if available after import (ALICE imported above)
    try:
        pass  # _GAME_MODE_CTX.set_speaker(ALICE.speak)
    except Exception:
        pass
except Exception:
    game_mode = None
    _GAME_MODE_CTX = None
#from hubspace_control import HubspaceController

username = os.getenv("USERNAME") or os.getlogin()

# Function to provide the current date and time
def get_time():
    now = datetime.datetime.now()
    return now.strftime("Today is %A, %d %B %Y. The time is %I:%M %p.")

# Function to respond to a question about the user's name
def respond_name():
    names = ["My name is ALICE. ", "I'm called ALICE. ", "You can call me ALICE. "]
    return random.choice(names) + "That stands for \"Advanced Learning Isolated Companion Entity\""

# Function to respond to a question about the user's age
def respond_age():
    ages = ["I don't have an age.", "I'm ageless.", "I exist beyond the concept of age."]
    return random.choice(ages)

# Function to respond to a question about the user's location
def respond_location():
    locations = ["I'm wherever you need me to be.", "I exist in the digital realm.", "My location is wherever my code is running."]
    return random.choice(locations)

# Function to respond to a question about the user's purpose
def respond_purpose():
    purposes = ["I'm here to assist you with your tasks and questions.", "My purpose is to help you.", "I exist to make your life easier."]
    return random.choice(purposes)

# Function to respond to a question about the meaning of life
def respond_meaning_of_life():
    meanings = ["The meaning of life is subjective and can vary from person to person.", "The meaning of life is to find purpose and fulfillment.", "The meaning of life is to seek happiness and make meaningful connections."]
    return random.choice(meanings)

# Function to provide the current date
def get_date():
    now = datetime.datetime.now()
    return now.strftime("Today is %A, %d %B %Y.")

# Function to respond with a feeling
def respond_feeling():
    feelings = ["I'm doing well, thank you!", "I'm feeling great today!", "I'm feeling wonderful, thanks for asking!"]
    return random.choice(feelings)

# Function to respond with a greeting
def respond_greeting():
    greetings = ["Hello!", "Hi there!", "Hey!", "Greetings!"]
    return random.choice(greetings)

# Function to respond with a farewell
def respond_farewell():
    farewells = ["Goodbye!", "See you later!", "Farewell!", "Take care!"]
    return random.choice(farewells)

# Function to respond with a thank you
def respond_thanks():
    thanks = ["You're welcome!", "No problem!", "My pleasure!", "Anytime!"]
    return random.choice(thanks)

# Function to respond with an affirmation
def respond_affirmative():
    affirmatives = ["Yes?", "What's up?", "How can I help?", "Go ahead!"]
    return random.choice(affirmatives)

# Function to respond with a joke
def respond_joke():
    jokes = ["Why don't scientists trust atoms? Because they make up everything!", "I told my wife she was drawing her eyebrows too high. She looked surprised!", "Why did the scarecrow win an award? Because he was outstanding in his field!"]
    return random.choice(jokes)

# Function to respond with a random fact
def respond_fact():
    facts = ["A group of flamingos is called a flamboyance.", "The shortest war in history lasted only 38 minutes.", "Bananas are berries, but strawberries are not."]
    return random.choice(facts)

# Function to respond with encouragement
def respond_encouragement():
    encouragements = ["You've got this!", "Keep going!", "Believe in yourself!", "You're doing great!", "Never give up!"]
    return random.choice(encouragements)

# Function to respond with weather information
def respond_weather():
    # You can implement weather API integration here to provide real-time weather information
    return "The weather is currently sunny with a temperature of 25°C."

# Function to respond with a quote
def respond_quote():
    quotes = ["The only way to do great work is to love what you do. - Steve Jobs", "A sword wields no strength unless the hand that holds it has courage. - Hero's Shade", "In the end, it's not the years in your life that count. It's the life in your years. - Abraham Lincoln", "Believe you can and you're halfway there. - Theodore Roosevelt"]
    return random.choice(quotes)

# Helper function to call check_inbox()
def check_inbox():
    return email_manager.check_inbox()

def read_specific_email():
    return email_manager.read_specific_email()

def send_email():
    return email_manager.send_email()

def auth_email():
    return email_manager.authenticate_gmail()

def scan_email():
    return email_manager.check_for_new_emails()

# Convert duration to seconds
def convert_to_seconds(duration):
    match = re.match(r'(\d+)\s*(seconds?|minutes?|hours?)?', duration.lower().strip())
    if match:
        value, unit = match.groups()
        value = int(value)
        if unit in ['second', 'seconds', None, '']:
            return value
        elif unit in ['minute', 'minutes']:
            return value * 60
        elif unit in ['hour', 'hours']:
            return value * 3600
    else:
        raise ValueError("Invalid duration format")

def start_timer(duration: str | None = None):
    duration = duration or input("How long? ")

    try:
        duration_seconds = convert_to_seconds(duration)
    except ValueError:
        return "Invalid duration. Please specify a valid time."

    Timer.set_timer(duration_seconds)
    return f"Timer set for {duration_seconds} seconds."

def volume_control_helper(volume: float | None = None, delta: float | None = None):
    volume = volume or input("What should I set the volume to?  ")

    try:
        vol_control = volume_control.VolumeControl()
        if delta is not None:
            # Relative change
            current = vol_control.get_volume()
            new_level = max(0.0, min(1.0, current + float(delta)))
            vol_control.set_volume(new_level)
            return f"Volume set to {int(new_level*100)}%."
        volume = float(volume)
        if volume > 1:
            volume = volume / 100
        vol_control.set_volume(volume)
        return f"Volume set to {int(volume*100)}%."
    except ValueError:
        print("Please enter a valid number between 0.0 and 1.0 or between 0 and 100")
        return "Invalid volume level. Please enter a number between 0 and 100 or a decimal between 0.0 and 1.0."
    except Exception as e:
        print(f"An error occurred: {e}")
        return f"An error occurred: {e}"

def mute_command():
    vol_control = volume_control.VolumeControl()
    vol_control.set_volume(0);

def lock_computer():
    """Lock the computer similar to pressing WIN + L."""
    try:
        ctypes.windll.user32.LockWorkStation()
        return "Locking Up"
    except Exception as e:
        print(f"An error occurred: {e}")
        return f"An error occured: {e}"
    
def analyze_screen():
    screen_analysis.identify_screen()
    return "Object and Text Scan Complete"

def start_game_detection_loop():
    try:
        pass  # screen_analysis.game_detection_loop(listen, speak)
    except KeyboardInterrupt:
        print("Game detection interrupted by user.")

def open_menu():
    menu_thread = threading.Thread(target=menuplanner.start, daemon=True)
    menu_thread.start()

def import_documents():
    """Invoke doc import dialog with dedup and return summary message."""
    try:
        summary = docqa.import_files_via_dialog()
        return summary.get('message', 'Import complete.')
    except Exception as e:
        return f"Document import failed: {e}"

# ---------- Task Management Handlers ----------
def _ensure_todo_helpers():
    try:
        if not hasattr(todo, "nl_add"):
            importlib.reload(todo)
    except Exception:
        pass

def add_task_command(task: str | None = None):
    _ensure_todo_helpers()
    if hasattr(todo, "nl_add"):
        return todo.nl_add(task)
    # Fallback to add_task_text if hot reload missed
    if task:
        return getattr(todo, "add_task_text", lambda _: "Task system not ready.")(task)
    return "Task system not ready."

def list_tasks_command():
    _ensure_todo_helpers()
    if hasattr(todo, "nl_list"):
        return todo.nl_list()
    return "No tasks or task system not ready."

def remove_task_command(number: int | None = None):
    _ensure_todo_helpers()
    if number is not None and hasattr(todo, "remove_task_index"):
        return todo.remove_task_index(number-1)
    if hasattr(todo, "nl_remove"):
        return todo.nl_remove()
    return "Task removal not available."

def clear_tasks_command():
    _ensure_todo_helpers()
    if hasattr(todo, "nl_clear"):
        return todo.nl_clear()
    return "Task clear not available."

# --- Remote notification test command ---
def test_notification_command(message: str | None = None):
    """Send a test notification to connected remote clients (phone)."""
    msg = (message or "VRGL test notification").strip() or "VRGL test notification"
    try:
        remote_access.notify(text=msg, kind="test")
        return f"Sent notification: {msg}"
    except Exception as e:
        return f"Notification failed: {e}"

# Instantiate once at startup
#hubspace = HubspaceController('troykorns@gmail.com', 'User_Flynn1202')
#asyncio.run(hubspace.initialize())

# Provide a safe default for hubspace controller when not configured
hubspace = None

def process_hubspace_command(query):
    # Guard when hubspace controller is not configured
    if hubspace is None:
        return "Hubspace is not configured. Please set up your Hubspace credentials first."
    query = query.lower().strip()

    # Match patterns
    if query.startswith("turn on ") or query.startswith("power on "):
        device_name = query.split("on ", 1)[-1]
        return asyncio.run(hubspace.control(device_name, True))

    elif query.startswith("turn off ") or query.startswith("power off "):
        device_name = query.split("off ", 1)[-1]
        return asyncio.run(hubspace.control(device_name, False))

    # Return message if no command matches
    return "No valid Hubspace command found. Please specify a device to control."


def describe_system_tools() -> str:
    if system_tools is None:
        return "System tools are not available."
    items = [
        "List running programs: 'what programs are running' or 'list processes'",
        "Open an app: 'open chrome' or 'open C:/path/to/app.exe'",
        "Close an app: 'close chrome' or 'close 1234'",
        "Bluetooth status: 'bluetooth status' or 'is bluetooth on'",
        "Toggle Bluetooth: 'turn bluetooth on' or 'turn bluetooth off'",
    ]
    return "You can ask me to: " + "; ".join(items)


def list_processes_command(query: str | None = None):
    if system_tools is None:
        return "System tools not available."
    try:
        procs = system_tools.list_processes(50)
        if not procs:
            return "No running processes found."
        lines = [f"{p.get('pid')} {p.get('name')}" for p in procs[:12]]
        return "Running: " + ", ".join(lines)
    except Exception as e:
        return f"Process listing failed: {e}"


def bluetooth_status_command(query: str | None = None):
    if system_tools is None:
        return "System tools not available."
    try:
        res = system_tools.bluetooth_status()
        if not res.get('ok'):
            return f"Bluetooth query failed: {res.get('error')}"
        adapters = res.get('adapters') or []
        if not adapters:
            return "No Bluetooth adapters found."
        return "; ".join([f"{a['name']} is {a['status']}" for a in adapters])
    except Exception as e:
        return f"Bluetooth status failed: {e}"


def toggle_bluetooth_command(query: str | None = None):
    if system_tools is None:
        return "System tools not available."
    q = (query or "").lower()
    enable = True if 'on' in q or 'enable' in q else False
    try:
        res = system_tools.toggle_bluetooth(enable)
        if isinstance(res, dict):
            return res.get('message') or (', '.join(f"{k}:{v}" for k, v in res.items()))
        return str(res)
    except Exception as e:
        return f"Bluetooth toggle failed: {e}"


def open_app_command(query: str | None = None):
    if system_tools is None:
        return "System tools not available."
    q = (query or '').strip()
    # extract the target after 'open '
    import re as _re
    m = _re.search(r"open (?:the )?(?P<t>.+)", q, flags=_re.IGNORECASE)
    target = m.group('t').strip() if m else q
    try:
        res = system_tools.open_app(target)
        if isinstance(res, dict):
            return res.get('message') or str(res)
        return str(res)
    except Exception as e:
        return f"Open app failed: {e}"


def close_app_command(query: str | None = None):
    if system_tools is None:
        return "System tools not available."
    q = (query or '').strip()
    import re as _re
    m = _re.search(r"close (?:the )?(?P<t>.+)", q, flags=_re.IGNORECASE)
    target = m.group('t').strip() if m else q
    try:
        res = system_tools.close_app(target)
        if isinstance(res, dict):
            return res.get('message') or str(res)
        return str(res)
    except Exception as e:
        return f"Close app failed: {e}"

        
        

def _prompt_for_query(prompt_text: str) -> str | None:
    try:
        return input(prompt_text + " ")
    except Exception:
        return None


def search_web_command(query: str | None = None):
    q = (query or "").strip()
    if not q:
        q = _prompt_for_query("What should I search the web for?")
    if not q:
        return "No search query provided."
    try:
        return web_search.web_search_answer(q)
    except Exception as e:
        return f"Web search failed: {e}"


def search_youtube_command(query: str | None = None):
    q = (query or "").strip()
    if not q:
        q = _prompt_for_query("What should I search on YouTube?")
    if not q:
        return "No YouTube query provided."
    try:
        search.search_youtube(q)
        return f"Searching YouTube for '{q}'."
    except Exception as e:
        return f"YouTube search failed: {e}"

def play_song_command(song: str | None = None):
    s = (song or "").strip()
    if not s:
        s = _prompt_for_query("What song should I play?")
    if not s:
        return "No song specified."
    return music_control.search_and_play_song(s)

def play_playlist_command(playlist: str | None = None):
    p = (playlist or "").strip()
    if not p:
        p = _prompt_for_query("What playlist should I play?")
    if not p:
        return "No playlist specified."
    return music_control.play_playlist(p)

def skip_song_command():
    return music_control.skip_song()

def pause_music_command():
    return music_control.pause_play()

def check_mood_command():
    global context_aware
    if 'context_aware' in globals():
        return context_aware.analyze_conversation(conversation_history)
    return "Context awareness not available."

def doc_query_command(question: str | None = None):
    q = (question or '').strip()
    if not q:
        q = input('Document question: ')
    if not q:
        return 'No question provided.'
    hits = docqa.query_docs(q, top_k=3)
    if not hits:
        return 'I did not find relevant content in your documents.'
    summary = ' '.join(h[:200] for h in hits)
    return f"Based on your documents: {summary}"  # Simple stitching; could be improved with model summarization

# ---------- Game Mode Handlers ----------
def enter_game_mode():
    if _GAME_MODE_CTX is None:
        return "Game mode module unavailable."
    if _GAME_MODE_CTX.active:
        return "Game mode already active."
    return _GAME_MODE_CTX.enter_mode()

def exit_game_mode():
    if _GAME_MODE_CTX is None:
        return "Game mode module unavailable."
    if not _GAME_MODE_CTX.active:
        return "Game mode not active."
    return _GAME_MODE_CTX.exit_mode()

def list_stratagems():
    if _GAME_MODE_CTX is None:
        return "Game mode module unavailable."
    if not _GAME_MODE_CTX.active:
        return "Game mode not active."
    return ", ".join(_GAME_MODE_CTX.list_commands()) or "No stratagems loaded."

def game_mode_interpret(text: str):
    """Interpret raw text while game mode active; returns spoken string or None."""
    if _GAME_MODE_CTX and _GAME_MODE_CTX.active:
        try:
            r = _GAME_MODE_CTX.interpret(text)
            if r and isinstance(r, dict):
                return r.get("spoken")
        except Exception as e:
            return f"Game mode error: {e}"
    return None


# --- Register safe handlers as tools for intent_router to call via tools.registry ---
REGISTRATION_WHITELIST = [
    "get_time",
    "get_date",
    "start_timer",
    "volume_control_helper",
    "mute_command",
    "lock_computer",
    "analyze_screen",
    "open_menu",
    "check_inbox",
    "read_specific_email",
    "send_email",
    "scan_email",
    "start_game_detection_loop",
    "enter_game_mode",
    "exit_game_mode",
    "list_stratagems",
    "import_documents",
    "add_task_command",
    "list_tasks_command",
    "remove_task_command",
    # "clear_tasks_command",  # intentionally omitted (destructive)
    "test_notification_command",
    "search_web_command",
    "search_youtube_command",
    "doc_query_command",
    "play_song_command",
    "play_playlist_command",
    "skip_song_command",
    "pause_music_command",
    "describe_system_tools",
]


def _load_local_registry():
    """Robustly load the local tools.registry module.
    Returns module or None.
    """
    try:
        from tools import registry as _reg
        return _reg
    except Exception:
        try:
            import importlib
            _reg = importlib.import_module("tools.registry")
            return _reg
        except Exception:
            # Fallback: load by file path
            try:
                import importlib.util, pathlib
                root = pathlib.Path(__file__).resolve().parent
                candidate = root / "tools" / "registry.py"
                if candidate.exists():
                    spec = importlib.util.spec_from_file_location("local_tools_registry", str(candidate))
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)  # type: ignore
                    return mod
            except Exception:
                return None
    return None


try:
    _registry = _load_local_registry()
    if _registry is not None and hasattr(_registry, "register"):
        for _name in REGISTRATION_WHITELIST:
            fn = globals().get(_name)
            if callable(fn):
                try:
                    # register with a namespaced and bare name for flexibility
                    try:
                        _registry.register(f"intent.{_name}", fn)
                    except Exception:
                        pass
                    try:
                        _registry.register(_name, fn)
                    except Exception:
                        pass
                except Exception:
                    # keep going if registration for one handler fails
                    pass
    else:
        # No registry available; continue silently
        _registry = None
except Exception:
    _registry = None

def organize_files_command():
    """Organize files autonomously based on usage patterns"""
    try:
        from dynamic_response import DynamicResponseHandler
        from user_memory import UserMemory

        memory = UserMemory()
        handler = DynamicResponseHandler(memory)
        result = handler.organize_files_autonomously()
        return result
    except Exception as e:
        return f"File organization failed: {e}"

# Dictionary mapping patterns to response functions
query_patterns = {
    re.compile(r".*\bwhat time is it\b.*"): get_time,
    re.compile(r".*\bwhat is the time\b.*"): get_time,
    re.compile(r".*\bshow me the time\b.*"): get_time,
    re.compile(r".*\bwhat day is it\b.*"): get_date,
    re.compile(r".*\bwhat is today's date\b.*"): get_date,
    re.compile(r".*\bshow me today's date\b.*"): get_date,
    re.compile(r".*\bhow are you\b.*"): respond_feeling,
    re.compile(r".*\bhello\b.*"): respond_greeting,
    re.compile(r".*\bhi\b.*"): respond_greeting,
    re.compile(r".*\bhey\b.*"): respond_greeting,
    re.compile(r".*\bhow are you\b.*"): respond_feeling,
    re.compile(r".*\bwhat's up\b.*"): respond_affirmative,
    re.compile(r".*\bthank you\b.*"): respond_thanks,
    re.compile(r".*\bthanks\b.*"): respond_thanks,
    re.compile(r".*\bgoodbye\b.*"): respond_farewell,
    re.compile(r".*\bsee you\b.*"): respond_farewell,
    re.compile(r".*\btell me a joke\b.*"): respond_joke,
    re.compile(r".*\btell me something interesting\b.*"): respond_fact,
    re.compile(r".*\bencourage me\b.*"): respond_encouragement,
    re.compile(r".*\bwhat's the weather\b.*"): respond_weather,
    re.compile(r".*\bgive me a quote\b.*"): respond_quote,
    re.compile(r".*\bwhat is your name\b.*"): respond_name,
    re.compile(r".*\bwho are you\b.*"): respond_name,
    re.compile(r".*\bhow old are you\b.*"): respond_age,
    re.compile(r".*\bwhere are you\b.*"): respond_location,
    re.compile(r".*\bwhat is your purpose\b.*"): respond_purpose,
    re.compile(r".*\bwhat is the meaning of life\b.*"): respond_meaning_of_life,
    re.compile(r".*\bcheck my inbox\b.*"): check_inbox,
    re.compile(r".*\bany new emails\b.*"): check_inbox,
    re.compile(r".*\bread email\b.*"): read_specific_email,
    re.compile(r".*\bexpand email\b.*"): read_specific_email,
    re.compile(r".*\bsend an email\b.*"): send_email,
    re.compile(r".*\bstart a timer\b.*"): start_timer,
    re.compile(r".*\bstart timer\b.*"): start_timer,
    re.compile(r".*\bset timer\b.*"): start_timer,
    re.compile(r".*\bset a timer\b.*"): start_timer,
    re.compile(r".*\bchange volume\b.*"): volume_control_helper,
    re.compile(r".*\bset volume\b.*"): volume_control_helper,
    re.compile(r".*\bauthenticate email\b.*"): auth_email,
    re.compile(r".*\bscan for emails\b.*"): scan_email,
    re.compile(r".*\bwatch my email\b.*"): scan_email,
    re.compile(r".*\bkeep an eye on my email\b.*"): scan_email,
    re.compile(r".*\bmute device\b.*"): mute_command,
    re.compile(r".*\bmute volume\b.*"): mute_command,
    re.compile(r".*\bmute sound\b.*"): mute_command,
    re.compile(r".*\bmute\b.*"): mute_command,
    re.compile(r".*\block device\b.*"): lock_computer,
    re.compile(r".*\block computer\b.*"): lock_computer,
    re.compile(r".*\block\b.*"): lock_computer,
    re.compile(r".*\bwhat is on my screen\b.*"): analyze_screen,
    re.compile(r".*\bwhat's on my screen\b.*"): analyze_screen,
    re.compile(r".*\bwhat am I looking at\b.*"): analyze_screen,
    re.compile(r".*\bwhat do I have pulled up\b.*"): analyze_screen,
    re.compile(r".*\bwhat do I have on my screen\b.*"): analyze_screen,
    re.compile(r".*\bdetect games\b.*"): start_game_detection_loop,
    re.compile(r".*\bdetect game\b.*"): start_game_detection_loop,
    re.compile(r".*\bstart game detection\b.*"): start_game_detection_loop,
    re.compile(r".*\bstart game detection loop\b.*"): start_game_detection_loop,
    re.compile(r".*\bstart detecting games\b.*"): start_game_detection_loop,
    re.compile(r".*\bstart detecting for games\b.*"): start_game_detection_loop,
    # Refined menu patterns (avoid 'documents' containing 'men')
    re.compile(r".*\bmenu\b.*"): open_menu,
    re.compile(r".*\bmenu planner\b.*"): open_menu,
    re.compile(r".*\bfood planner\b.*"): open_menu,
    re.compile(r".*\brecipes?\b.*"): open_menu,
    re.compile(r".*\brecipe book\b.*"): open_menu,
    # Document import patterns
    re.compile(r".*\b(import|add|ingest|load) (?:my )?(documents|docs|files)\b.*"): import_documents,
    # Game mode
    re.compile(r".*\b(enter|start|activate) game mode\b.*"): enter_game_mode,
    re.compile(r".*\b(exit|leave|stop|cancel) game mode\b.*"): exit_game_mode,
    re.compile(r".*\blist stratagems\b.*"): list_stratagems,
    re.compile(r".*\blist game commands\b.*"): list_stratagems,
    # matches for hubspace commands
    # Specific system-level toggles should match before Hubspace generic commands
    re.compile(r".*\bturn bluetooth (on|off)\b.*"): lambda q=None: toggle_bluetooth_command(q),
    re.compile(r".*\bturn on bluetooth\b.*"): lambda q=None: toggle_bluetooth_command(q),
    re.compile(r".*\bturn off bluetooth\b.*"): lambda q=None: toggle_bluetooth_command(q),
    re.compile(r".*\bpower bluetooth (on|off)\b.*"): lambda q=None: toggle_bluetooth_command(q),
    # Hubspace/general device control (fallback)
    re.compile(r".*\bturn on\b .*"): lambda query: process_hubspace_command(query),
    re.compile(r".*\bpower on\b .*"): lambda query: process_hubspace_command(query),
    re.compile(r".*\bturn off\b .*"): lambda query: process_hubspace_command(query),
    re.compile(r".*\bpower off\b .*"): lambda query: process_hubspace_command(query),
    re.compile(r".*\bswitch on\b .*"): lambda query: process_hubspace_command(query),
    re.compile(r".*\bswitch off\b .*"): lambda query: process_hubspace_command(query),
    re.compile(r".*\bactivate\b .*"): lambda query: process_hubspace_command(query),
    re.compile(r".*\bdeactivate\b .*"): lambda query: process_hubspace_command(query),
    # --- System tools patterns ---
    re.compile(r".*\b(what|which) (programs|processes) (are )?running\b.*"): lambda q=None: list_processes_command(q),
    re.compile(r".*\blist (running )?(programs|processes)\b.*"): lambda q=None: list_processes_command(q),
    re.compile(r".*\bwhat'?s running\b.*"): lambda q=None: list_processes_command(q),
    re.compile(r".*\bbluetooth status\b.*"): lambda q=None: bluetooth_status_command(q),
    re.compile(r".*\bis bluetooth (on|off)\b.*"): lambda q=None: bluetooth_status_command(q),
    re.compile(r".*\bturn bluetooth (on|off)\b.*"): lambda q=None: toggle_bluetooth_command(q),
    re.compile(r".*\b(open|launch) (.+)\b.*"): lambda q=None: open_app_command(q),
    re.compile(r".*\b(close|kill|terminate) (.+)\b.*"): lambda q=None: close_app_command(q),
    re.compile(r".*\bwhat can you do for me\b.*"): lambda q=None: describe_system_tools(),
    re.compile(r".*\bwhat can you do\b.*"): lambda q=None: describe_system_tools(),
    re.compile(r".*search the web for .*"): search_web_command,
    re.compile(r".*search on youtube for .*"): search_youtube_command,
    # Music control patterns
    re.compile(r".*\bplay (.+) on youtube music\b.*"): lambda query=None: play_song_command(re.sub(r".*\bplay (.+) on youtube music\b.*", r"\1", (query or ""))),
    re.compile(r".*\bplay song (.+)\b.*"): lambda query=None: play_song_command(re.sub(r".*\bplay song (.+)\b.*", r"\1", (query or ""))),
    re.compile(r".*\bplay playlist (.+)\b.*"): lambda query=None: play_playlist_command(re.sub(r".*\bplay playlist (.+)\b.*", r"\1", (query or ""))),
    re.compile(r".*\bskip song\b.*"): skip_song_command,
    re.compile(r".*\bnext song\b.*"): skip_song_command,
    re.compile(r".*\bpause music\b.*"): pause_music_command,
    re.compile(r".*\bplay music\b.*"): pause_music_command,
    re.compile(r".*\bset volume to (\d+)\b.*"): lambda q: set_volume_command(re.findall(r"(\d+)", q)[0] if re.findall(r"(\d+)", q) else None),
    re.compile(r".*search my documents for .*" ): doc_query_command,
    re.compile(r".*from my documents .*" ): doc_query_command,
    re.compile(r".*from my notes .*" ): doc_query_command,
    re.compile(r".*in my notes .*" ): doc_query_command,
    # Task natural language fallbacks (beyond heuristic router)
    re.compile(r".*add (.+) to (my )?(to-?do|tasks?).*" ): lambda q: add_task_command(re.sub(r".*add (.+) to (my )?(to-?do|tasks?).*", r"\1", q)),
    re.compile(r".*list (my )?tasks.*" ): list_tasks_command,
    re.compile(r".*show (me )?(my )?tasks.*" ): list_tasks_command,
    re.compile(r".*what's on (my )?to-?do.*" ): list_tasks_command,
    re.compile(r".*remove task (\d+).*" ): lambda q: remove_task_command(int(re.findall(r"(\d+)", q)[0])),
    re.compile(r".*delete task (\d+).*" ): lambda q: remove_task_command(int(re.findall(r"(\d+)", q)[0])),
    re.compile(r".*remove task (one|two|three|four|five|six|seven|eight|nine|ten).*" ): lambda q: remove_task_command(re.findall(r"remove task (one|two|three|four|five|six|seven|eight|nine|ten)", q)[0]),
    re.compile(r".*delete task (one|two|three|four|five|six|seven|eight|nine|ten).*" ): lambda q: remove_task_command(re.findall(r"delete task (one|two|three|four|five|six|seven|eight|nine|ten)", q)[0]),
    re.compile(r".*clear (all )?(tasks|to-?do).*" ): clear_tasks_command,
    re.compile(r".*what do i have to do.*" ): list_tasks_command,
    re.compile(r".*what do we have to do.*" ): list_tasks_command
    # Add more patterns and responses as needed
    ,
    # --- Notification test patterns ---
    re.compile(r".*test (?:the )?(?:vrgl )?notification.*"): lambda q: test_notification_command(),
    re.compile(r".*notify my phone$" ): lambda q: test_notification_command(),
    re.compile(r".*notify my phone (about |with |that )?(?P<msg>.+)" ): lambda q: test_notification_command(re.sub(r".*notify my phone (about |with |that )?(?P<msg>.+)", r"\1", q, flags=re.IGNORECASE)),
    re.compile(r".*\borganize (my )?files\b.*"): organize_files_command,
    re.compile(r".*\bclean up (my )?downloads\b.*"): organize_files_command,
    re.compile(r".*\bclean up (my )?desktop\b.*"): organize_files_command,
    re.compile(r".*\bsort (my )?files\b.*"): organize_files_command,
}


# Dynamically wire patterns from tools/tool_catalog.py to call into tools.registry
try:
    from tools import tool_catalog
    import importlib
    # ensure tool modules are imported so they can register themselves with registry
    for entry in getattr(tool_catalog, 'TOOL_CATALOG', []):
        tid = entry.get('id') or ''
        prefix = tid.split('.', 1)[0] if '.' in tid else tid
        if not prefix:
            continue
        candidates = [f"tools.{prefix}_tools", f"tools.{prefix}tools", f"tools.{prefix}"]
        for cand in candidates:
            try:
                importlib.import_module(cand)
                break
            except Exception:
                continue

    # ensure we have a registry reference from earlier loader
    if _registry is not None and hasattr(_registry, 'call_tool'):
        for entry in getattr(tool_catalog, 'TOOL_CATALOG', []):
            tid = entry.get('id')
            for pat in entry.get('patterns', []):
                try:
                    cre = re.compile(pat)
                    # closure to capture tid
                    def make_handler(tool_id):
                        def handler(query=None, _tool_id=tool_id):
                            try:
                                # If query is empty/None, call without args
                                if query is None or (isinstance(query, str) and not query.strip()):
                                    r = _registry.call_tool(_tool_id)
                                else:
                                    # Try calling with the query; if tool expects no args, retry without
                                    r = _registry.call_tool(_tool_id, query)
                                    # If registry returned an error about positional args, retry below
                                if isinstance(r, dict) and not r.get('ok') and r.get('error') and 'too many positional' in str(r.get('error')):
                                    r = _registry.call_tool(_tool_id)
                                # r is the registry envelope: {ok, result, error}
                                if isinstance(r, dict):
                                    if not r.get('ok'):
                                        return f"Tool error: {r.get('error') or r.get('result')}"
                                    res = r.get('result')
                                    # If tool returned a dict, convert to a spoken-friendly summary
                                    if isinstance(res, dict):
                                        if 'path' in res:
                                            return f"Saved to {res.get('path')}"
                                        if 'message' in res:
                                            return str(res.get('message'))
                                        if 'percent' in res and 'plugged' in res:
                                            return f"Battery at {res.get('percent')}%, plugged in: {res.get('plugged')}"
                                        if 'interfaces' in res:
                                            ifaces = [f"{i.get('iface')}: {'up' if i.get('is_up') else 'down'}" for i in res.get('interfaces')[:6]]
                                            return ", ".join(ifaces) or str(res)
                                        if 'results' in res:
                                            items = res.get('results') or []
                                            return f"Found {len(items)} files, e.g. {items[0]}" if items else "No files found"
                                        return str(res)
                                    # If tool returned a list or string, return readable form
                                    if isinstance(res, list):
                                        return ", ".join(str(x) for x in res[:12])
                                    return str(res)
                                return str(r)
                            except Exception as e:
                                return f"Tool invocation failed: {e}"
                        return handler
                    # do not overwrite existing patterns added earlier; add only if missing
                    if cre not in query_patterns:
                        query_patterns[cre] = make_handler(tid)
                except Exception:
                    continue
except Exception:
    pass
