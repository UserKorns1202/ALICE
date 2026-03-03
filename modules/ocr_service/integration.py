"""Integration subscriber and Decision Engine for OCR events.

This module connects to the local bus, receives `ocr` events, scores them for
relevance and novelty, and emits decisions (speak/suggest/ignore) via a
callback supplied by the host (ALICE). It is intentionally lightweight and
config-driven so it can be extended later.
"""
from typing import Callable, Optional, Dict, Any
import threading
import time
import re
import json
import pathlib

from .bus import subscribe_forever

CONF_PATH = pathlib.Path(__file__).parent / 'config.json'
_DEFAULT_CONF = {
    'speak_threshold': 0.8,
    'suggest_threshold': 0.5,
    'novelty_ttl': 60.0,
    'per_app_cooldown': 30.0,
    'global_cooldown': 5.0,
    'per_app': {}
}

def _load_conf() -> dict:
    try:
        if CONF_PATH.exists():
            with open(CONF_PATH, 'r', encoding='utf-8') as f:
                c = json.load(f)
                cfg = _DEFAULT_CONF.copy()
                cfg.update(c or {})
                return cfg
    except Exception:
        pass
    return _DEFAULT_CONF.copy()


class DecisionEngine:
    def __init__(self, speak_threshold: float = 0.8, suggest_threshold: float = 0.5, novelty_ttl: float = 60.0, per_app_cooldown: float = 30.0, global_cooldown: float = 5.0):
        # thresholds
        self.speak_threshold = speak_threshold
        self.suggest_threshold = suggest_threshold
        self.novelty_ttl = novelty_ttl
        # cooldowns
        self.per_app_cooldown = per_app_cooldown
        self.global_cooldown = global_cooldown
        self.seen_hashes: Dict[str, float] = {}  # hash -> last_seen_ts
        self.keywords = [
            'error', 'exception', 'failed', 'warning', 'alert', 'critical',
            'low health', 'you died', 'out of memory', 'unauthorized', 'denied'
        ]
        self.keyword_re = re.compile('|'.join(re.escape(k) for k in self.keywords), re.IGNORECASE)
        self.last_action_ts_global = 0.0
        self.last_action_ts_per_app: Dict[str, float] = {}

    def score(self, payload: Dict[str, Any]) -> float:
        # Basic scoring combining OCR confidence, keyword hits, and novelty
        conf = float(payload.get('confidence', 0.0))
        text = (payload.get('text') or '')
        h = payload.get('hash') or ''

        # novelty: 1 if unseen recently
        now = time.time()
        last = self.seen_hashes.get(h)
        novelty = 1.0 if (not last or (now - last) > self.novelty_ttl) else 0.0

        # keyword relevance
        kws = 1.0 if self.keyword_re.search(text) else 0.0

        # Weighted sum (simple)
        score = 0.6 * conf + 0.3 * novelty + 0.4 * kws
        # normalize roughly to 0..1
        score = min(1.0, score / 1.3)

        # record seen
        if h:
            self.seen_hashes[h] = now

        return score

    def allowed_by_rate(self, payload: Dict[str, Any]) -> bool:
        """Check per-app and global cooldowns to avoid spamming."""
        now = time.time()
        app = payload.get('app') or 'default'
        # global cooldown
        if (now - self.last_action_ts_global) < self.global_cooldown:
            return False
        # per-app cooldown
        last = self.last_action_ts_per_app.get(app, 0.0)
        if (now - last) < self.per_app_cooldown:
            return False
        return True

    def record_action(self, payload: Dict[str, Any]) -> None:
        now = time.time()
        app = payload.get('app') or 'default'
        self.last_action_ts_global = now
        self.last_action_ts_per_app[app] = now


class IntegrationService:
    def __init__(self, host: str = '127.0.0.1', port: int = 8765):
        self.host = host
        self.port = port
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable[[Dict[str, Any]], None]] = None
        conf = _load_conf()
        self.engine = DecisionEngine(
            speak_threshold=conf.get('speak_threshold', 0.8),
            suggest_threshold=conf.get('suggest_threshold', 0.5),
            novelty_ttl=conf.get('novelty_ttl', 60.0),
            per_app_cooldown=conf.get('per_app_cooldown', 30.0),
            global_cooldown=conf.get('global_cooldown', 5.0),
        )
        self.conf = conf

    def start(self, callback: Callable[[Dict[str, Any]], None]):
        """Start the integration service. `callback` will be invoked when a
        decision to speak or suggest is made. The callback receives a dict with
        keys: `action`, `score`, `payload`.
        """
        self._callback = callback
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    def _run(self):
        def _cb(msg: Dict[str, Any]):
            try:
                topic = msg.get('topic')
                payload = msg.get('payload') or {}
            except Exception:
                return

            if topic != 'ocr':
                return

            score = self.engine.score(payload)
            action = 'ignore'
            if score >= self.engine.speak_threshold:
                action = 'speak'
            elif score >= self.engine.suggest_threshold:
                action = 'suggest'

            # Rate limiting: if not allowed, downgrade or ignore
            if action != 'ignore' and not self.engine.allowed_by_rate(payload):
                # if within cooldown, downgrade speak->suggest, or suggest->ignore
                if action == 'speak':
                    action = 'suggest'
                else:
                    action = 'ignore'

            out = {
                'action': action,
                'score': score,
                'payload': payload,
            }

            if action != 'ignore' and self._callback:
                try:
                    self._callback(out)
                except Exception:
                    pass
                # record action time to enforce cooldowns
                try:
                    self.engine.record_action(payload)
                except Exception:
                    pass

        # Block until stop_event is set
        subscribe_forever(self.host, self.port, _cb, stop_event=self._stop_event)


def start_integration(callback: Callable[[Dict[str, Any]], None], host: str = '127.0.0.1', port: int = 8765) -> IntegrationService:
    svc = IntegrationService(host=host, port=port)
    svc.start(callback)
    return svc
