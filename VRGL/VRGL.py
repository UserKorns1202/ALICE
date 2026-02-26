import threading
import sys
import subprocess
import random
import speech_recognition as sr
import datetime
import sympy as sp
import time
import keyboard  # Added for keyboard event handling
import patterns
# missing json import required for conversation history
import json
#import intent_patterns
import todo
import os
import platform
# Dynamic username for path construction
username = os.getenv("USERNAME") or os.getlogin()
script_dir = os.path.dirname(__file__)
import piper_tts

# Portable Piper helper for VRGL: keep Piper usage local and tolerant to API differences
def piper_speak(text: str, voice: str | None = None, play: bool = True, block: bool = False) -> str | None:
    """Wrapper around the local `VRGL/piper_tts.py` that mirrors how ALICE uses Piper.
    This allows VRGL to remain portable while handling variations in the `piper_tts.speak`
    signature (some versions accept `voice=`; others don't).
    Returns path to WAV or None on failure.
    """
    try:
        # ensure runtime PIPER_URL (piper_tts reads env at import; allow dynamic update)
        env_url = os.environ.get('PIPER_URL')
        if env_url:
            try:
                piper_tts.PIPER_URL = env_url
            except Exception:
                pass

        try:
            # prefer calling with voice if available
            return piper_tts.speak(text, voice=voice, play=play, block=block)
        except TypeError:
            # older wrappers may not accept `voice=` kwarg
            try:
                if voice is not None:
                    return piper_tts.speak(text, f"{voice}", play=play, block=block)
                return piper_tts.speak(text, play=play, block=block)
            except Exception:
                return None
        except Exception:
            return None
    except Exception:
        return None
try:
    import pytesseract
    from PIL import ImageGrab
    ocr_available = True
except ImportError:
    ocr_available = False
    print("OCR not available, install pytesseract and Pillow")
import search
import queue
import pygame
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
from urllib.parse import urlparse
import agents

# Add missing imports for volume_control and email_manager
import volume_control
import email_manager

# KEVIN server configuration
KEVIN_URL = os.getenv("KEVIN_URL", "http://100.118.18.122:5000")
# Optional separate chat URL (heavier model); falls back to KEVIN_URL
KEVIN_CHAT_URL = os.getenv("KEVIN_CHAT_URL", KEVIN_URL)
# Local Ollama (VRGL) configuration - fallback when KEVIN is unavailable
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

def query_vrgl(prompt: str, timeout: int = 10) -> str:
    """Query local Ollama/VRGL instance with a simple prompt and return text.
    This is intentionally minimal: send only the user's question (no KEVIN wrappers).
    The Ollama API variants differ; try multiple common response shapes.
    """
    try:
        payload = {"model": OLLAMA_MODEL, "prompt": prompt}
        resp = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=timeout)
        text = ""
        # Try to parse JSON shapes commonly returned by Ollama variants
        parts = []
        parsed = False
        try:
            j = resp.json()
            parsed = True
            # Newer Ollama: results -> content -> text
            if isinstance(j, dict):
                if "results" in j:
                    try:
                        for r in j.get("results", []):
                            for c in r.get("content", []):
                                if isinstance(c, dict) and c.get("type") == "output_text":
                                    parts.append(c.get("text", ""))
                    except Exception:
                        pass
                # older shape: choices -> [{text: ...}]
                if not parts and "choices" in j:
                    try:
                        for c in j.get("choices", []):
                            if isinstance(c, dict) and isinstance(c.get("text"), str):
                                parts.append(c.get("text"))
                    except Exception:
                        pass
                # some wrappers: 'text' or 'response'
                if not parts:
                    for k in ("text", "response", "output"):
                        if k in j and isinstance(j[k], str):
                            parts.append(j[k])
        except ValueError:
            parsed = False

        # If not parsed as a single JSON document, try streaming / newline-delimited JSON lines
        if not parsed:
            raw = resp.text or ""
            # Split into non-empty lines; handle SSE 'data:' prefixes
            for line in [ln.strip() for ln in raw.splitlines() if ln.strip()]:
                if line.startswith("data:"):
                    line = line[len("data:"):].strip()
                try:
                    obj = json.loads(line)
                except Exception:
                    # If line isn't a valid JSON object, skip
                    continue
                if isinstance(obj, dict):
                    # streaming fragments often have a 'response' field
                    if "response" in obj and isinstance(obj["response"], str):
                        parts.append(obj["response"])
                    elif "text" in obj and isinstance(obj["text"], str):
                        parts.append(obj["text"])
                    else:
                        # try nested shapes
                        if "results" in obj:
                            try:
                                for r in obj.get("results", []):
                                    for c in r.get("content", []):
                                        if isinstance(c, dict) and c.get("type") == "output_text":
                                            parts.append(c.get("text", ""))
                            except Exception:
                                pass

        # Join streaming fragments without additional separators to preserve spacing/punctuation
        if parts:
            text = "".join(parts)
        else:
            # Final fallback: raw response text
            text = resp.text or ""

        # Normalize and return
        return (text or "").strip()
    except Exception as e:
        return f"VRGL (Ollama) query failed: {e}"

# Requirements and auto-install disabled in the VRGL clone to avoid network
# side-effects on import. If you need to generate a `requirements.txt` or
# install dependencies, run the helper script `scripts/install_requirements.py`
# or install packages manually. This keeps importing `VRGL.py` safe and
# deterministic (no unexpected pip/network activity).

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

# Playback queue holds tuples (text, wav_path, remote_session_id)
playback_queue = queue.Queue()

# TTS background threads (generator and player)
_tts_generator_thread = None
_tts_player_thread = None

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
    print(f"[Background] Wake word: '{wake_word}'")
    while not is_exiting:
        if input_mode == "speaking":
            query = listen()
            if query:
                print(f"[Background] Heard: '{query}', checking for wake word '{wake_word}'")
                wake_detected = False
                if wake_word == "virgil":
                    # vrgl model uses both "virgil" and "vergil" as wake words
                    wake_detected = "virgil" in query.lower() or "vergil" in query.lower()
                else:
                    wake_detected = wake_word and wake_word in query.lower()
                
                if wake_detected:
                    # Extract command after wake word
                    query_lower = query.lower()
                    if "virgil" in query_lower:
                        query = query_lower.split("virgil", 1)[1].strip()
                    elif "vergil" in query_lower:
                        query = query_lower.split("vergil", 1)[1].strip()
                    else:
                        query = query_lower.split(wake_word, 1)[1].strip()
                    print(f"[Background] Processed query: '{query}'")
                    play_sound("aiAffirmative.mp3")
                    reset_inactivity()
                    query_queue.put(query)
                else:
                    print(f"[Background] Wake word '{wake_word}' not found in '{query}', ignoring")
        else:
            time.sleep(1)

game_context = GameModeContext()
game_context.set_speak_queue(speak_queue)

conversation_history = []

def save_conversation_history():
    with open(os.path.join(script_dir, "conversation_history.json"), "w") as file:
        json.dump(conversation_history, file)

def load_conversation_history():
    global conversation_history
    try:
        with open(os.path.join(script_dir, "conversation_history.json"), "r") as file:
            conversation_history = json.load(file)
    except FileNotFoundError:
        conversation_history = []

# Piper-based TTS: audio generated via local Piper server
global input_mode
input_mode = "typing"
global aiModel
global wake_word


def speak(response, force=False, remote_session_id=None):
    """Enqueue a TTS request. Generation and playback are handled by background threads.

    - `force` currently reserved for future immediate playback behavior.
    - `remote_session_id` will be forwarded to remote audio generator while generation occurs.
    """
    # Sanitize text for TTS: remove markdown emphasis and inline code backticks
    def sanitize_for_tts(text: str) -> str:
        try:
            if not isinstance(text, str):
                return text
            text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text, flags=re.S)
            text = re.sub(r"(\*|_)(.*?)\1", r"\2", text, flags=re.S)
            text = re.sub(r"`(.*?)`", r"\1", text, flags=re.S)
            text = re.sub(r"[ \t]+", " ", text)
            return text.strip()
        except Exception:
            return text

    cleaned = sanitize_for_tts(response)
    item = (cleaned, remote_session_id)
    try:
        speak_queue.put_nowait(item)
    except queue.Full:
        print(f"[Speak] Queue full, dropping response: {cleaned[:50]}...")
        return


def _tts_generator_loop():
    """Background thread: take (text, remote_session_id) from speak_queue, generate WAV (no play), put into playback_queue."""
    while not is_exiting:
        try:
            item = speak_queue.get()
            if not item:
                continue
            try:
                text, remote_id = (item if isinstance(item, tuple) else (item, None))
            except Exception:
                text = str(item)
                remote_id = None

            # Generate WAV file without playing
            try:
                try:
                    wav = piper_speak(text, voice=current_tts_voice, play=False)
                except Exception as e:
                    print(f"[TTS gen] Piper generation wrapper failed: {e}")
                    wav = None
            except Exception as e:
                print(f"[TTS gen] Piper generation failed: {e}")
                wav = None

            # Send remote audio if requested (do not block playback)
            if remote_id:
                try:
                    import remote_access
                    remote_access.generate_audio_response(remote_id, text)
                except Exception as e:
                    print(f"[Remote] Failed to generate audio response: {e}")

            # enqueue for playback (wav may be None)
            playback_queue.put((text, wav))
        except Exception:
            time.sleep(0.1)


def _tts_player_loop():
    """Background thread: play WAVs from playback_queue sequentially. Sets `is_speaking` while playing."""
    global is_speaking
    while not is_exiting:
        try:
            text, wav = playback_queue.get()
            with speak_lock:
                is_speaking = True
                send_speaking_command()
            try:
                if wav and os.path.exists(wav):
                    try:
                        _ensure = None
                        try:
                            pygame.mixer.init()
                        except Exception:
                            pass
                        sound = pygame.mixer.Sound(wav)
                        ch = sound.play()
                        if ch is not None:
                            while ch.get_busy():
                                pygame.time.delay(50)
                    except Exception as e:
                        print(f"[TTS play] Playback failed: {e}")
                else:
                    # fallback: try direct piper speak (blocking)
                    try:
                        _ = piper_speak(text, voice=current_tts_voice, play=True, block=True)
                    except Exception as e:
                        print(f"[TTS fallback] Piper speak failed: {e}")
                        # Try pyttsx3 as a local offline TTS fallback
                        try:
                            import pyttsx3
                            try:
                                engine = pyttsx3.init()
                                engine.say(text)
                                engine.runAndWait()
                            except Exception as _py_e:
                                print(f"[TTS pyttsx3 fallback] playback failed: {_py_e}")
                        except Exception as _imp_e:
                            print(f"[TTS pyttsx3 fallback] import/init failed: {_imp_e}")
            finally:
                with speak_lock:
                    is_speaking = False
                    if get_current_input_mode() == "typing":
                        send_idle_command()
                    else:
                        send_listening_command()
                # cleanup wav file if temporary
                try:
                    if wav and os.path.exists(wav):
                        os.remove(wav)
                except Exception:
                    pass
        except Exception:
            time.sleep(0.1)

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
#
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
        # Stop any pygame playback instead of pyttsx3 engine loop
        try:
            pygame.mixer.stop()
        except Exception:
            pass
    except RuntimeError:
        pass



def listen_for_interrupt():
    """Function to listen for an interrupt command to stop speech."""
    global stop_speaking, interrupt_thread_running
    recognizer = sr.Recognizer()

    while interrupt_thread_running.is_set():
        try:
            with sr.Microphone() as source:
                print("Listening for an interrupt...")
                audio = recognizer.listen(source, timeout=5)

                # Convert audio to text
                command = recognizer.recognize_google(audio).lower()
                print(f"Recognized command: {command}")  # Debugging output
                if "stop" in command or "pause" in command:  # Define interrupt words
                    print("Interrupt command detected. Stopping speech.")
                    stop_speaking.set()  # Signal to stop speaking
                    return  # Return after stopping speech
        except sr.UnknownValueError:
            continue  # No valid speech recognized
        except sr.RequestError:
            print("Speech recognition service is unavailable.")
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
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        send_listening_command()
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)

    try:
        print("Recognizing...")
        query = recognizer.recognize_google(audio)
        send_idle_command()
        return query
    except sr.UnknownValueError:
        return "*Unintelligible*"
    except sr.RequestError:
        return "Sorry, there was an error with the speech recognition service."
    except ListenInterrupt:
        return None


def searchingSounds():
    reset_inactivity()
    sounds = ["aiAffirmative.mp3", "aiCameraSound.mp3", "aiSearch.mp3", "aiSwap.mp3"]
    sound = random.choice(sounds)
    play_sound(sound)




def interrupt_listening():
    raise ListenInterrupt()

def update_gui_model(new_charDir):
    with open(os.path.join(script_dir, "config.txt"), "w") as file:
        file.write(new_charDir)
    # Immediately update runtime voice to match the new GUI model selection
    try:
        nm = (new_charDir or "").strip().lower()
        # Normalize VRGL to virgil for internal logic
        if nm == 'vrgl':
            nm = 'virgil'
        global aiModel, wake_word
        aiModel = nm
        wake_word = nm
        try:
            change_voice(nm)
        except Exception as _e:
            print(f"[GUI] change_voice failed: {_e}")
    except Exception:
        pass

# Global flag to control network monitoring
network_monitoring_flag = False
network_monitor_thread = None

# Function to start gui.py in a separate thread
def start_gui():
    global guiProcess
    try:
        print("[GUI] Starting GUI process...")
        # Try original ALICE GUI in parent folder (portable clone may not have it)
        parent_dir = os.path.abspath(os.path.join(script_dir, os.pardir))
        candidates = [
            os.path.join(parent_dir, 'gui.py'),
            os.path.join(script_dir, 'gui.py'),
        ]
        started = False
        for candidate in candidates:
            if os.path.exists(candidate):
                gui_cmd = [sys.executable, candidate]
                gui_cwd = os.path.dirname(candidate)
                # Do not swallow stdout/stderr so errors are visible
                try:
                    guiProcess = subprocess.Popen(gui_cmd, cwd=gui_cwd)
                    print(f"[GUI] Launched GUI: {candidate}")
                    started = True
                    break
                except Exception as ex:
                    print(f"[GUI] Failed to start {candidate}: {ex}")
        if not started:
            print("[GUI] No GUI found to start")
    except Exception as e:
        print(f"[GUI] Failed to start GUI: {e}")
        guiProcess = None


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


# Function to end FaceRec.py in a separate thread
def end_fr():
    try:
        import FaceRec  # local module controls its own loop flag
        FaceRec.running = False
    except Exception as e:
        print(f"FaceRec stop failed: {e}")

# Function to send exit command to GUI
def send_exit_command():
    with open(os.path.join(script_dir, "gui_command.txt"), "w") as f:
        f.write("exit")
    

# Function to send idle command to GUI
def send_idle_command():
    global is_speaking
    if not is_speaking:  # Only send idle if not currently speaking
        with open(os.path.join(script_dir, "gui_command.txt"), "w") as f:
            f.write("idle")

# Function to send speaking command to GUI
def send_speaking_command():
    with open(os.path.join(script_dir, "gui_command.txt"), "w") as f:
        f.write("speaking")

# Function to send working command to GUI
def send_working_command():
    global is_speaking
    if not is_speaking:  # Only send working if not currently speaking
        with open(os.path.join(script_dir, "gui_command.txt"), "w") as f:
            f.write("working")

# Function to send math command to GUI
def send_math_command():
    with open(os.path.join(script_dir, "gui_command.txt"), "w") as f:
        f.write("math")

# Function to send listening command to GUI
def send_listening_command():
    global is_speaking
    if not is_speaking:  # Only send listening if not currently speaking
        with open(os.path.join(script_dir, "gui_command.txt"), "w") as f:
            f.write("listening")

# Function to send angry command to GUI
def send_angry_command():
    with open(os.path.join(script_dir, "gui_command.txt"), "w") as f:
        f.write("angry")

# Function to send hello command to GUI
def send_hello_command():
    with open(os.path.join(script_dir, "gui_command.txt"), "w") as f:
        f.write("hello")

def send_blink_command():
    with open(os.path.join(script_dir, "gui_command.txt"), "w") as f:
        f.write("blink")

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
    with open(os.path.join(script_dir, "face_command.txt"), "r") as f:
        command = f.read().strip()
    if command.lower() == "troy korns":
        command = "Sir"
    return command

# Function to clear current face from recognizer
def clearFace():
    with open(os.path.join(script_dir, "face_command.txt"), "w") as f:
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
            try:
                import pythoncom
                import win32com.client
                pythoncom.CoInitialize()
                try:
                    shell = win32com.client.Dispatch("WScript.Shell")
                    shortcut = shell.CreateShortcut(shortcut_path)
                    target_path = shortcut.TargetPath
                finally:
                    try:
                        del shortcut
                        del shell
                    except Exception:
                        pass
                    try:
                        pythoncom.CoUninitialize()
                    except Exception:
                        pass
            except Exception:
                try:
                    import win32com.client
                    shell = win32com.client.Dispatch("WScript.Shell")
                    shortcut = shell.CreateShortcut(shortcut_path)
                    target_path = shortcut.TargetPath
                except Exception:
                    target_path = None

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
                                try:
                                    import pythoncom
                                    import win32com.client
                                    pythoncom.CoInitialize()
                                    try:
                                        shell = win32com.client.Dispatch("WScript.Shell")
                                        shortcut = shell.CreateShortcut(full_path)
                                        target_path = shortcut.TargetPath
                                    finally:
                                        try:
                                            del shortcut
                                            del shell
                                        except Exception:
                                            pass
                                        try:
                                            pythoncom.CoUninitialize()
                                        except Exception:
                                            pass
                                except Exception:
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


def chat_with_kevin(query, speak_to_kevin: bool = False, overrides: dict | None = None):
    global aiModel  # Access the global aiModel variable
    searchingSounds()
    send_working_command()
    try:
        # Add user's query to conversation history
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
        legacy_mode = os.getenv("VRGL_LEGACY_MODE", "false").lower() in ("1", "true", "yes")

        # By default we avoid sending conversation history for command-like queries to prevent
        # the model echoing previous assistant-only responses (observed as repeated 'TRON').
        command_like = False
        try:
            qnorm = (query or "").lstrip().lower()
            command_like = any(qnorm.startswith(p) for p in ("plan", "execute", "run", "edit", "open", "close", "approve", "reject", "set", "toggle"))
        except Exception:
            command_like = False

        payload = {
            "text": query,
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

        # Send to KEVIN server (chat endpoint/model) with a short timeout
        try:
            response = requests.post(f"{KEVIN_CHAT_URL}/query", json=payload, timeout=4)
            # Handle response
            if response.status_code == 200:
                data = response.json()
                assistant_reply = data.get("response", "[KEVIN did not return a response]")

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
                # KEVIN returned non-200; try VRGL (local Ollama) as a fallback
                try:
                    vrgl_text = query_vrgl(query)
                    assistant_reply = (vrgl_text or f"KEVIN server error {response.status_code}: {response.text}")
                    # Mark source as VRGL when used
                    if vrgl_text:
                        assistant_reply = f"{assistant_reply} [via VRGL]"
                    conversation_history.append({"role": "assistant", "content": assistant_reply})
                    return assistant_reply
                except Exception:
                    assistant_reply = f"KEVIN server error {response.status_code}: {response.text}"
                    return assistant_reply
        except requests.exceptions.RequestException:
            # KEVIN didn't respond in time - fall back to local Ollama (VRGL)
            try:
                vrgl_text = query_vrgl(query)
                assistant_reply = (vrgl_text or "Connection to KEVIN failed")
                if vrgl_text:
                    assistant_reply = f"{assistant_reply} [via VRGL]"
                conversation_history.append({"role": "assistant", "content": assistant_reply})
                return assistant_reply
            except Exception:
                return "Connection to KEVIN failed"
    except Exception as e:
        return "Connection to KEVIN failed"
    finally:
        send_idle_command()


#function to check current model
def check_model():
    global aiModel
    try:
        with open(os.path.join(script_dir, "config.txt"), "r") as file:
            aiModel = file.read().strip()
        if not aiModel:  # If empty, default to virgil
            aiModel = "vrgl"
    except FileNotFoundError:
        aiModel = "vrgl"  # Default if file doesn't exist

def play_sound(file_path):
    # Initialize the pygame mixer
    try:
        pygame.mixer.init()
        # Resolve common assets/sounds path when a bare filename is passed
        if not os.path.isabs(file_path) and not os.path.exists(file_path):
            alt = os.path.join(script_dir, 'assets', 'sounds', file_path)
            if os.path.exists(alt):
                file_path = alt
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
    except Exception as e:
        print(f"Audio play failed for {file_path}: {e}")

# Function to change the voice based on the model
def change_voice(model):
    """Set the preferred TTS voice token for Piper and play a searching sound."""
    global current_tts_voice
    searchingSounds()
    # Map high-level model names to Piper ONNX filenames
    if model in ("virgil", "vrgl"):
        # Use the danny voice for VRGL (high-quality male)
        current_tts_voice = 'en_US-danny-low.onnx'
    elif model == "alice":
        # Default Alice voice (female US medium)
        current_tts_voice = 'en_US-hfc_female-medium.onnx'
    else:
        # Fallback to a general-purpose voice if unknown
        current_tts_voice = 'ljspeech.onnx'
    print(f"Voice changed to: {current_tts_voice}")
    return current_tts_voice

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
    
    global aiModel, wake_word, current_tts_voice
    aiModel = "vrgl"
    check_model()

    # Ensure a local Piper server is running (start one from local `piper` folder if necessary)
    try:
        def start_piper():
            """Start a local Piper node server if not already responding.
            Returns True if a Piper server is running or was started successfully.
            """
            # First, scan common Piper ports for an already-running server (/voices endpoint)
            candidates_ports = []
            env_url = os.environ.get('PIPER_URL')
            if env_url:
                try:
                    parsed = urlparse(env_url)
                    if parsed.port:
                        candidates_ports.append(parsed.port)
                except Exception:
                    pass
            candidates_ports.extend([5001, 5002, 5003, 5004, 5005, 3000])

            for port in dict.fromkeys(candidates_ports):
                try:
                    test_url = f'http://127.0.0.1:{port}/voices'
                    r = requests.get(test_url, timeout=0.8)
                    if r.status_code == 200:
                        url = f'http://127.0.0.1:{port}'
                        os.environ['PIPER_URL'] = url
                        try:
                            piper_tts.PIPER_URL = url
                        except Exception:
                            pass
                        print(f"[PIPER] Detected running Piper at {url}")
                        return True
                except Exception:
                    pass

            # locate server.js in likely locations
            script_dir = os.path.dirname(__file__)
            # Prefer a Piper installation located inside the VRGL folder (portable)
            candidates = [
                os.path.join(script_dir, 'piper'),
            ]
            piper_dir = None
            for c in candidates:
                if os.path.exists(os.path.join(c, 'server.js')):
                    piper_dir = c
                    break
            if not piper_dir:
                print('[PIPER] Piper server.js not found in expected locations; not starting Piper.')
                return False

            node_cmd = shutil.which('node') or 'node'
            env = os.environ.copy()
            # If caller set a PIPER_URL with port, set process env PORT so server binds there
            try:
                if env_url:
                    parsed = urlparse(env_url)
                    if parsed.port:
                        env.setdefault('PORT', str(parsed.port))
            except Exception:
                pass

            piper_log_path = os.path.join(piper_dir, 'piper_stdout.log')
            try:
                piper_log = open(piper_log_path, 'ab')
            except Exception:
                piper_log = subprocess.DEVNULL

            try:
                print(f"[PIPER] Starting Piper from {piper_dir} using {node_cmd}")
                if platform.system() == 'Windows':
                    proc = subprocess.Popen([node_cmd, 'server.js'], cwd=piper_dir, stdout=piper_log, stderr=subprocess.STDOUT, env=env, creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    proc = subprocess.Popen([node_cmd, 'server.js'], cwd=piper_dir, stdout=piper_log, stderr=subprocess.STDOUT, env=env)

                # Wait a short while then scan common ports again for /voices
                timeout = 8.0
                interval = 0.6
                elapsed = 0.0
                found = False
                while elapsed < timeout:
                    for port in [5001,5002,5003,5004,5005,3000]:
                        try:
                            test_url = f'http://127.0.0.1:{port}/voices'
                            r = requests.get(test_url, timeout=0.6)
                            if r.status_code == 200:
                                url = f'http://127.0.0.1:{port}'
                                os.environ['PIPER_URL'] = url
                                try:
                                    piper_tts.PIPER_URL = url
                                except Exception:
                                    pass
                                print(f"[PIPER] Piper started and responding at {url} (PID {getattr(proc, 'pid', 'unknown')})")
                                found = True
                                break
                        except Exception:
                            pass
                    if found:
                        break
                    time.sleep(interval)
                    elapsed += interval

                if not found:
                    # Try to parse the piper_stdout.log for explicit listen lines
                    try:
                        with open(piper_log_path, 'rb') as lf:
                            data = lf.read().decode(errors='ignore')
                            m = re.search(r'Server listening on http://[^:]+:(\d+)', data)
                            if m:
                                port = int(m.group(1))
                                url = f'http://127.0.0.1:{port}'
                                os.environ['PIPER_URL'] = url
                                try:
                                    piper_tts.PIPER_URL = url
                                except Exception:
                                    pass
                                print(f"[PIPER] Found Piper log binding at {url}")
                                found = True
                    except Exception:
                        pass

                if not found:
                    print('[PIPER] Piper did not respond after starting; check logs.')
                return True
            except Exception as e:
                print(f"[PIPER] Failed to start Piper: {e}")
                return False

        start_piper()
    except Exception as _sp:
        print(f"[PIPER] start_piper helper failure: {_sp}")

    # Start TTS background threads (generator and player)
    global _tts_generator_thread, _tts_player_thread
    if _tts_generator_thread is None or not getattr(_tts_generator_thread, 'is_alive', lambda: False)():
        _tts_generator_thread = threading.Thread(target=_tts_generator_loop, daemon=True)
        _tts_generator_thread.start()
    if _tts_player_thread is None or not getattr(_tts_player_thread, 'is_alive', lambda: False)():
        _tts_player_thread = threading.Thread(target=_tts_player_loop, daemon=True)
        _tts_player_thread.start()
    

    # Set a preferred Piper voice filename for VRGL
    current_tts_voice = 'en_US-danny-low.onnx'

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
        # Planner instance (can use KEVIN_CHAT_URL via env or VRGL KEVIN_CHAT_URL constant)
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
            # Background TTS threads handle queued speech; just log if items are pending
            try:
                if not speak_queue.empty():
                    remaining = speak_queue.qsize()
                    print(f"[ModeLoop] {remaining} queued speech items waiting for background TTS threads")
            except Exception as _qerr:
                print(f"[ModeLoop] Speak queue status error: {_qerr}")
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

    # Handle different actions
    if action == 'open_program':
        program = routed_command.get('program', '')
        if aiModel == "virgil":
            send_working_command()
        else:
            send_blink_command()
        response = open_program(program)
        send_idle_command()
        return response

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

    elif action == 'change_model':
        send_working_command()
        if aiModel == "vrgl":
            aiModel = "vrgl"
        elif aiModel == "alice":
            aiModel = "vrgl"
        wake_word = aiModel.lower()
        if wake_word == "vrgl":
            wake_word = "virgil"  # vrgl uses "virgil" as wake word
        send_exit_command()
        play_sound("aiSwap.mp3")
        # Terminate the GUI process
        if guiProcess:
            guiProcess.terminate()
            guiProcess.wait()
        update_gui_model(aiModel)
        # Start GUI in a separate thread
        send_idle_command()
        searchingSounds()
        gui_thread = threading.Thread(target=start_gui, daemon=True)
        gui_thread.start()
        # Change the voice based on the new model
        engine = change_voice(aiModel)
        return f"Switched to {aiModel} model."

    elif action == 'switch_to_alice':
        send_working_command()
        aiModel = "vrgl"
        wake_word = aiModel.lower()
        send_exit_command()
        play_sound("aiSwap.mp3")
        # Terminate the GUI process
        if guiProcess:
            guiProcess.terminate()
            guiProcess.wait()
        update_gui_model(aiModel)
        # Start GUI in a separate thread
        send_idle_command()
        searchingSounds()
        gui_thread = threading.Thread(target=start_gui, daemon=True)
        gui_thread.start()
        # Change the voice based on the new model
        engine = change_voice(aiModel)
        return f"Switched to {aiModel} model."

    elif action == 'switch_to_vrgl':
        send_working_command()
        aiModel = "vrgl"
        wake_word = aiModel.lower()
        send_exit_command()
        play_sound("aiSwap.mp3")
        # Terminate the GUI process
        if guiProcess:
            guiProcess.terminate()
            guiProcess.wait()
        update_gui_model(aiModel)
        # Start GUI in a separate thread
        send_idle_command()
        searchingSounds()
        gui_thread = threading.Thread(target=start_gui, daemon=True)
        gui_thread.start()
        # Change the voice based on the new model
        engine = change_voice(aiModel)
        return f"Switched to {aiModel} model."

    elif action == 'switch_to_virgil':
        send_working_command()
        aiModel = "vrgl"
        wake_word = aiModel.lower()
        send_exit_command()
        play_sound("aiSwap.mp3")
        # Terminate the GUI process
        if guiProcess:
            guiProcess.terminate()
            guiProcess.wait()
        update_gui_model(aiModel)
        # Start GUI in a separate thread
        send_idle_command()
        searchingSounds()
        gui_thread = threading.Thread(target=start_gui, daemon=True)
        gui_thread.start()
        # Change the voice based on the new model
        engine = change_voice(aiModel)
        return f"Switched to {aiModel} model."

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
