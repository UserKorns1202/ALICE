import os, sys, time, threading, importlib, traceback
from types import ModuleType
from typing import Dict

WATCH_INTERVAL = 1.0
_EXCLUDE = {"__pycache__"}
_WATCHED_EXT = {".py"}

class HotReloader(threading.Thread):
    def __init__(self, target_packages=None, on_reload=None, interval=WATCH_INTERVAL):
        super().__init__(daemon=True)
        self.interval = interval
        self.on_reload = on_reload
        self.target_packages = set(target_packages or [])
        self._mtimes: Dict[str, float] = {}
        self._stop = threading.Event()

    def run(self):
        while not self._stop.is_set():
            try:
                self.scan()
            except Exception:
                traceback.print_exc()
            self._stop.wait(self.interval)

    def stop(self):
        self._stop.set()

    def scan(self):
        for module in list(sys.modules.values()):
            if not isinstance(module, ModuleType):
                continue
            name = getattr(module, "__name__", "")
            if not name:
                continue
            if self.target_packages and not any(name.startswith(pkg) for pkg in self.target_packages):
                continue
            path = getattr(module, "__file__", None)
            if not path or not os.path.isfile(path):
                continue
            if any(seg in _EXCLUDE for seg in path.split(os.sep)):
                continue
            if os.path.splitext(path)[1] not in _WATCHED_EXT:
                continue
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                continue
            old = self._mtimes.get(path)
            if old is None:
                self._mtimes[path] = mtime
                continue
            if mtime > old:
                self._mtimes[path] = mtime
                # Attempt reload
                try:
                    importlib.reload(module)
                    if self.on_reload:
                        self.on_reload(name, path)
                except Exception:
                    traceback.print_exc()

_reloader: HotReloader | None = None

def start_hot_reload(packages=None, callback=None):
    global _reloader
    if _reloader is None:
        _reloader = HotReloader(target_packages=packages, on_reload=callback)
        _reloader.start()
        print("[HotReload] watcher started")


def stop_hot_reload():
    global _reloader
    if _reloader:
        _reloader.stop()
        _reloader = None
