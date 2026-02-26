"""Simple conversation manager for ALICE.

Provides a small API to store role-based messages and stream partial assistant
responses via callbacks. This is intentionally synchronous and lightweight so
it can be integrated incrementally.
"""
from __future__ import annotations
import time
import json
from typing import List, Dict, Callable, Optional


class ConversationManager:
    def __init__(self, max_history: int = 200):
        self.history: List[Dict[str, str]] = []
        self.max_history = max_history

    def add(self, role: str, content: str):
        self.history.append({"role": role, "content": content, "ts": time.time()})
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def recent(self, n: int = 10) -> List[Dict[str, str]]:
        return list(self.history[-n:])

    def to_json(self) -> str:
        return json.dumps(self.history, indent=2)

    def save(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    def load(self, path: str):
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.history = json.load(f)
        except Exception:
            self.history = []


class Streamer:
    """Utility to stream tokens to callbacks.

    Usage: create with a callback fn(token:str), call `send(token)` repeatedly,
    and `finish()` when done.
    """
    def __init__(self, on_token: Optional[Callable[[str], None]] = None):
        self.on_token = on_token
        self._buffer = []

    def send(self, token: str):
        if self.on_token:
            try:
                self.on_token(token)
            except Exception:
                pass
        else:
            # default: accumulate
            self._buffer.append(token)

    def finish(self) -> str:
        return "".join(self._buffer)


__all__ = ["ConversationManager", "Streamer"]
