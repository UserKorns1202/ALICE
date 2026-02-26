import os
import uuid
import requests
import tempfile
import pygame

PIPER_URL = os.environ.get("PIPER_URL", "http://127.0.0.1:3000")


def _ensure_pygame_mixer():
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
    except Exception:
        try:
            pygame.init()
            pygame.mixer.init()
        except Exception:
            pass


def speak(text: str, voice: str | None = None, play: bool = True, block: bool = False) -> str | None:
    """Request audio from a Piper server.
    If `play` is True, plays via pygame; if False, saves WAV and returns path without playing.
    If `block` is True and playing, blocks until playback finishes.
    Returns the path to the saved WAV file (or a remote URL) on success, else None.
    """
    try:
        params = {"text": text}
        if voice:
            params["voice"] = voice
        # prefer a GET endpoint compatible with existing Piper wrappers
        r = requests.get(f"{PIPER_URL.rstrip('/')}/tts", params=params, timeout=120)
        if r.status_code != 200:
            return None

        ctype = r.headers.get("content-type", "")
        # If server returned JSON with a url, fetch that
        if "application/json" in ctype:
            try:
                j = r.json()
                url = j.get("url") or j.get("path")
                if url:
                    rr = requests.get(url, timeout=60)
                    if rr.status_code == 200:
                        tmp = os.path.join(tempfile.gettempdir(), f"piper_{uuid.uuid4().hex}.wav")
                        with open(tmp, "wb") as f:
                            f.write(rr.content)
                        if play:
                            _ensure_pygame_mixer()
                            try:
                                s = pygame.mixer.Sound(tmp)
                                ch = s.play()
                                if block and ch is not None:
                                    while ch.get_busy():
                                        pygame.time.delay(50)
                            except Exception:
                                pass
                        return tmp
            except Exception:
                return None

        # Otherwise assume audio bytes (wav) returned directly
        tmp = os.path.join(tempfile.gettempdir(), f"piper_{uuid.uuid4().hex}.wav")
        with open(tmp, "wb") as f:
            f.write(r.content)

        if play:
            _ensure_pygame_mixer()
            try:
                sound = pygame.mixer.Sound(tmp)
                ch = sound.play()
                if block and ch is not None:
                    while ch.get_busy():
                        pygame.time.delay(50)
            except Exception:
                pass
        return tmp
    except Exception:
        return None
