"""speech_io: encapsulate speaking/listening logic for ALICE.

This module provides a limited, safe replacement of speaking/listening
helpers from the main file. It exposes an `integrate(globals_dict)`
function which copies the exported names into the caller's globals.

Keep this file small and defensive so it can be iterated on safely.
"""
from __future__ import annotations
import threading
import queue
import time
import re
import random
from typing import Any

try:
    import speech_recognition as sr
except Exception:
    sr = None

try:
    import pygame
    _have_pygame = True
except Exception:
    pygame = None
    _have_pygame = False


class DeduplicatingQueue:
    """A small queue that deduplicates recent messages.

    Keeps a timestamp map of recently-seen strings to avoid repeats.
    """
    def __init__(self, maxsize: int = 10, dedup_window: int = 300):
        self._q = queue.Queue(maxsize=maxsize)
        self._seen = {}  # text -> last_time
        self._dedup_window = dedup_window
        self._lock = threading.Lock()

    def put_nowait(self, item: Any):
        text = (item[0] if isinstance(item, (list, tuple)) and item else str(item))
        now = time.time()
        with self._lock:
            last = self._seen.get(text)
            if last and now - last < self._dedup_window:
                return
            self._seen[text] = now
        self._q.put_nowait(item)

    def get(self, timeout: float | None = None):
        return self._q.get(timeout=timeout) if timeout is not None else self._q.get()

    def empty(self):
        return self._q.empty()

    def qsize(self):
        return self._q.qsize()


# Public queues and simple flags
speak_queue = DeduplicatingQueue(maxsize=10)
playback_queue = queue.Queue()

is_speaking = False
speak_lock = threading.Lock()
stop_speaking = threading.Event()
interrupt_thread_running = threading.Event()
interrupt_thread = None


def _sanitize_for_tts(text: str) -> str:
    try:
        t = re.sub(r"[`*_]{1,3}", "", text)
        # Collapse excessive whitespace
        t = re.sub(r"\s+", " ", t).strip()
        return t
    except Exception:
        return text


def speak(response: str, force: bool = False, remote_session_id: Any = None) -> None:
    """Enqueue a spoken response.

    This implementation enqueues the sanitized text. A background player
    will consume `playback_queue` and attempt local playback.
    """
    cleaned = _sanitize_for_tts(response)
    try:
        speak_queue.put_nowait((cleaned, remote_session_id))
    except queue.Full:
        print(f"[speech_io] speak queue full, dropping: {cleaned[:60]}")


def _tts_generator_loop():
    """Move items from speak_queue into playback_queue as simple text entries."""
    while True:
        try:
            text, rid = speak_queue.get()
            # In a more complete implementation, generate a WAV here.
            playback_queue.put((text, rid))
        except Exception:
            time.sleep(0.1)


def _tts_player_loop():
    """Play back items from `playback_queue`. Uses pygame when available.

    If pygame isn't available, fallback to printing text to stdout.
    """
    global is_speaking
    if _have_pygame:
        try:
            pygame.mixer.init()
        except Exception:
            pass

    while True:
        try:
            text, rid = playback_queue.get()
            if not text:
                continue
            with speak_lock:
                is_speaking = True
                try:
                    if _have_pygame and False:
                        # Placeholder: actual WAV playback logic could go here
                        pass
                    else:
                        # Minimal, non-blocking audible fallback
                        print(f"[TTS] {text}")
                finally:
                    is_speaking = False
        except Exception:
            time.sleep(0.1)


def listen(timeout: float | None = None) -> str | None:
    """Listen once from the microphone and return recognized text.

    If `speech_recognition` is unavailable return a placeholder string.
    """
    if sr is None:
        return "*SpeechRecognition not available*"
    r = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            r.adjust_for_ambient_noise(source, duration=0.5)
            audio = r.listen(source, timeout=timeout)
        # Prefer Whisper (if available), then PocketSphinx (offline), then Google
        return transcribe_audio(audio, recognizer=r, verbose=True)
    except sr.UnknownValueError:
        return "*Unintelligible*"
    except sr.RequestError:
        return "*Speech service error*"
    except Exception:
        return None


def interrupt_listening():
    raise KeyboardInterrupt()


def listen_for_interrupt():
    """Background listener to allow interrupting speech (best-effort).

    This function uses `speech_recognition` to try to detect words like
    'stop' or 'cancel' and sets the `stop_speaking` event.
    """
    if sr is None:
        return
    r = sr.Recognizer()
    while interrupt_thread_running.is_set():
        try:
            with sr.Microphone() as source:
                audio = r.listen(source, timeout=1, phrase_time_limit=4)
            text = transcribe_audio(audio, recognizer=r, verbose=False)
            if not text:
                time.sleep(0.2)
                continue
            text = (text or "").lower()
            if any(k in text for k in ("stop", "cancel", "interrupt")):
                stop_speaking.set()
        except Exception:
            time.sleep(0.2)


def transcribe_audio(audio, recognizer=None, prefer_whisper: bool = True, verbose: bool = True):
    """Transcribe an AudioData object using a whisper-first strategy.

    Order: Recognizer.recognize_whisper (if available) -> recognize_sphinx -> recognize_google
    Prints to terminal when falling back.
    """
    if sr is None:
        return None
    r = recognizer or sr.Recognizer()
    # Try Recognizer's Whisper binder if present
    if prefer_whisper and hasattr(r, 'recognize_whisper'):
        try:
            if verbose:
                print('[speech_io] Attempting Whisper transcription (recognize_whisper)')
            return r.recognize_whisper(audio)
        except Exception as e:
            if verbose:
                print(f"[speech_io] Whisper (recognize_whisper) failed: {e}; falling back")
    # Try PocketSphinx (offline)
    if hasattr(r, 'recognize_sphinx'):
        try:
            if verbose:
                print('[speech_io] Attempting PocketSphinx (offline) transcription')
            return r.recognize_sphinx(audio)
        except Exception as e:
            if verbose:
                print(f"[speech_io] PocketSphinx failed: {e}; falling back")
    # Finally, try Google (online)
    try:
        if verbose:
            print('[speech_io] Attempting Google speech recognition (online)')
        return r.recognize_google(audio)
    except Exception as e:
        if verbose:
            print(f"[speech_io] Google recognizer failed: {e}")
        return None


def start_interrupt_thread():
    global interrupt_thread
    if interrupt_thread is None or not getattr(interrupt_thread, "is_alive", lambda: False)():
        interrupt_thread_running.set()
        interrupt_thread = threading.Thread(target=listen_for_interrupt, daemon=True)
        interrupt_thread.start()


def stop_interrupt_thread():
    global interrupt_thread
    interrupt_thread_running.clear()
    try:
        if interrupt_thread and interrupt_thread.is_alive():
            interrupt_thread.join(timeout=1)
    except Exception:
        pass


_gen_thread = None
_player_thread = None

def start_background_threads():
    """Start speech_io's internal generator/player threads.

    Note: these threads are NOT started automatically on import to avoid
    interfering with a host program (like `ALICE.py`) that manages its
    own TTS generator/player loops and GUI state. Call this only when you
    want speech_io to run its own minimal playback pipeline.
    """
    global _gen_thread, _player_thread
    if _gen_thread is None or not getattr(_gen_thread, "is_alive", lambda: False)():
        _gen_thread = threading.Thread(target=_tts_generator_loop, daemon=True)
        _gen_thread.start()
    if _player_thread is None or not getattr(_player_thread, "is_alive", lambda: False)():
        _player_thread = threading.Thread(target=_tts_player_loop, daemon=True)
        _player_thread.start()


def integrate(globals_dict: dict):
    """Copy exported symbols into the provided globals dictionary.

    This lets the main program keep referencing the same names.
    """
    names = [
        'DeduplicatingQueue', 'speak_queue', 'playback_queue', 'speak', 'listen',
        'is_speaking', 'speak_lock', 'stop_speaking', 'start_interrupt_thread',
        'stop_interrupt_thread', 'listen_for_interrupt', 'interrupt_listening'
    ]
    for n in names:
        globals_dict[n] = globals()[n]


__all__ = [
    'DeduplicatingQueue', 'speak_queue', 'playback_queue', 'speak', 'listen',
    'is_speaking', 'speak_lock', 'stop_speaking', 'start_interrupt_thread',
    'stop_interrupt_thread', 'listen_for_interrupt', 'interrupt_listening', 'integrate'
]
