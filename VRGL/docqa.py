import os, json, re, threading, time, hashlib, shutil
from typing import List, Dict, Tuple, Optional

# Optional GUI imports for file selection
try:  # pragma: no cover - GUI environment dependent
    import tkinter as _tk
    from tkinter import filedialog as _filedialog
except Exception:  # pragma: no cover
    _tk = None
    _filedialog = None

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
except Exception:
    SentenceTransformer = None
    np = None

_EMBED_MODEL = None
_INDEX: List[Tuple[str, List[float]]] = []  # (chunk, embedding)
_INDEX_LOCK = threading.Lock()
_DOCQA_DIR = os.getenv("ALICE_DOCS", os.path.join(os.getcwd(), "documents"))
_CHUNK_SIZE = 800
_OVERLAP = 120
_META_FILE = os.path.join(_DOCQA_DIR, ".docqa_meta.json")  # stores hash -> filename mapping


def _ensure_doc_dir():
    try:
        os.makedirs(_DOCQA_DIR, exist_ok=True)
    except Exception:
        pass


def _load_meta() -> Dict[str, str]:
    if not os.path.isfile(_META_FILE):
        return {}
    try:
        with open(_META_FILE, 'r', encoding='utf-8') as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _save_meta(meta: Dict[str, str]):
    try:
        with open(_META_FILE, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2)
    except Exception:
        pass


def _load_embed_model():
    global _EMBED_MODEL
    if _EMBED_MODEL is None and SentenceTransformer:
        _EMBED_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _EMBED_MODEL


def _iter_files():
    if not os.path.isdir(_DOCQA_DIR):
        return
    for root, _, files in os.walk(_DOCQA_DIR):
        for f in files:
            if f.lower().endswith(('.txt', '.md')):
                yield os.path.join(root, f)


def _hash_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def import_files_via_dialog(allow_multiple: bool = True) -> Dict[str, str]:
    """Open a file picker to import .txt/.md files into the documents directory with dedup.

    Returns a summary dict with counts:
        {'imported': int, 'skipped': int, 'errors': int, 'message': str}
    """
    _ensure_doc_dir()
    if _filedialog is None:
        return {"imported": 0, "skipped": 0, "errors": 0, "message": "GUI not available (tkinter missing)."}
    try:  # Create hidden root window
        root = _tk.Tk()
        root.withdraw()
    except Exception:
        return {"imported": 0, "skipped": 0, "errors": 0, "message": "Failed to init tkinter root."}

    if allow_multiple and hasattr(_filedialog, 'askopenfilenames'):
        paths = _filedialog.askopenfilenames(title="Select text/markdown files to ingest",
                                             filetypes=[("Text / Markdown", "*.txt *.md"), ("All", "*.*")])
    else:
        p = _filedialog.askopenfilename(title="Select a file to ingest",
                                        filetypes=[("Text / Markdown", "*.txt *.md"), ("All", "*.*")])
        paths = [p] if p else []
    root.destroy()
    if not paths:
        return {"imported": 0, "skipped": 0, "errors": 0, "message": "No files selected."}

    meta = _load_meta()
    imported = skipped = errors = 0
    for src in paths:
        if not os.path.isfile(src):
            errors += 1
            continue
        try:
            with open(src, 'rb') as f:
                data = f.read()
        except Exception:
            errors += 1
            continue
        content_hash = _hash_bytes(data)
        if content_hash in meta:
            skipped += 1
            continue
        # Enforce extension to .txt if unsupported
        ext = os.path.splitext(src)[1].lower()
        if ext not in ('.txt', '.md'):
            # Try decode & save as .txt
            try:
                text = data.decode('utf-8', errors='ignore')
            except Exception:
                skipped += 1
                continue
            base_name = os.path.splitext(os.path.basename(src))[0] + ".txt"
            dest = os.path.join(_DOCQA_DIR, base_name)
            i = 1
            while os.path.exists(dest):
                dest = os.path.join(_DOCQA_DIR, f"{base_name}_{i}.txt")
                i += 1
            try:
                with open(dest, 'w', encoding='utf-8') as f:
                    f.write(text)
            except Exception:
                errors += 1
                continue
        else:
            # Copy preserving name; add numeric suffix if conflict & different hash
            base = os.path.basename(src)
            dest = os.path.join(_DOCQA_DIR, base)
            if os.path.exists(dest):
                # If exact same content, treat as duplicate; else unique name
                try:
                    with open(dest, 'rb') as df:
                        if _hash_bytes(df.read()) == content_hash:
                            skipped += 1
                            continue
                except Exception:
                    pass
                stem, ext2 = os.path.splitext(base)
                n = 1
                while os.path.exists(dest):
                    dest = os.path.join(_DOCQA_DIR, f"{stem}_{n}{ext2}")
                    n += 1
            try:
                shutil.copy2(src, dest)
            except Exception:
                errors += 1
                continue
        meta[content_hash] = os.path.basename(dest)
        imported += 1
    _save_meta(meta)
    if imported:
        # Trigger rebuild (synchronously) so new docs available immediately
        build_index()
    return {"imported": imported, "skipped": skipped, "errors": errors,
            "message": f"Imported {imported}, skipped {skipped} duplicates, {errors} errors."}


def import_files_programmatic(paths: List[str]) -> Dict[str, str]:
    """Programmatic variant of import (no GUI). Accepts list of absolute paths."""
    _ensure_doc_dir()
    meta = _load_meta()
    imported = skipped = errors = 0
    for src in paths:
        if not src:
            continue
        if not os.path.isfile(src):
            errors += 1
            continue
        try:
            with open(src, 'rb') as f:
                data = f.read()
        except Exception:
            errors += 1
            continue
        content_hash = _hash_bytes(data)
        if content_hash in meta:
            skipped += 1
            continue
        ext = os.path.splitext(src)[1].lower()
        if ext not in ('.txt', '.md'):
            try:
                text = data.decode('utf-8', errors='ignore')
            except Exception:
                skipped += 1
                continue
            base_name = os.path.splitext(os.path.basename(src))[0] + ".txt"
            dest = os.path.join(_DOCQA_DIR, base_name)
            i = 1
            while os.path.exists(dest):
                dest = os.path.join(_DOCQA_DIR, f"{base_name}_{i}.txt")
                i += 1
            try:
                with open(dest, 'w', encoding='utf-8') as f:
                    f.write(text)
            except Exception:
                errors += 1
                continue
        else:
            base = os.path.basename(src)
            dest = os.path.join(_DOCQA_DIR, base)
            if os.path.exists(dest):
                try:
                    with open(dest, 'rb') as df:
                        if _hash_bytes(df.read()) == content_hash:
                            skipped += 1
                            continue
                except Exception:
                    pass
                stem, ext2 = os.path.splitext(base)
                n = 1
                while os.path.exists(dest):
                    dest = os.path.join(_DOCQA_DIR, f"{stem}_{n}{ext2}")
                    n += 1
            try:
                shutil.copy2(src, dest)
            except Exception:
                errors += 1
                continue
        meta[content_hash] = os.path.basename(dest)
        imported += 1
    _save_meta(meta)
    if imported:
        build_index()
    return {"imported": imported, "skipped": skipped, "errors": errors,
            "message": f"Imported {imported}, skipped {skipped} duplicates, {errors} errors."}


def _chunk(text: str) -> List[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + _CHUNK_SIZE)
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        start = max(end - _OVERLAP, end)
    return chunks


def build_index():
    model = _load_embed_model()
    if model is None:
        print("[DocQA] sentence-transformers not installed; skipping index build.")
        return 0
    docs = list(_iter_files())
    local_index = []
    for path in docs:
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
        except Exception:
            continue
        for chunk in _chunk(text):
            emb = model.encode([chunk])[0].tolist()
            local_index.append((chunk, emb))
    with _INDEX_LOCK:
        _INDEX.clear()
        _INDEX.extend(local_index)
    print(f"[DocQA] Indexed {len(_INDEX)} chunks from {len(docs)} files.")
    return len(_INDEX)


def _cosine(a: List[float], b: List[float]) -> float:
    import math
    dot = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a)) + 1e-9
    nb = math.sqrt(sum(x*x for x in b)) + 1e-9
    return dot/(na*nb)


def query_docs(question: str, top_k: int = 3) -> List[str]:
    model = _load_embed_model()
    if model is None or not _INDEX:
        return []
    q_emb = model.encode([question])[0].tolist()
    with _INDEX_LOCK:
        scored = [(_cosine(q_emb, emb), chunk) for chunk, emb in _INDEX]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]


class DocWatcher(threading.Thread):
    def __init__(self, interval: float = 5.0):
        super().__init__(daemon=True)
        self.interval = interval
        self._last_state: Dict[str, float] = {}
        self._stop = threading.Event()

    def run(self):
        while not self._stop.is_set():
            changed = False
            current = {}
            for path in _iter_files():
                try:
                    mtime = os.path.getmtime(path)
                except Exception:
                    continue
                current[path] = mtime
                if path not in self._last_state or self._last_state[path] != mtime:
                    changed = True
            if changed or set(current.keys()) != set(self._last_state.keys()):
                build_index()
                self._last_state = current
            self._stop.wait(self.interval)

    def stop(self):
        self._stop.set()


_watcher: DocWatcher | None = None

def start_watcher():
    global _watcher
    if _watcher is None:
        _watcher = DocWatcher()
        _watcher.start()
        print("[DocQA] Watcher started.")


def stop_watcher():
    global _watcher
    if _watcher:
        _watcher.stop()
        _watcher = None


if __name__ == '__main__':
    build_index()
    start_watcher()
    print("Type :import to open file dialog (if available). Type :quit to exit.")
    while True:
        q = input('Q: ')
        if not q or q.strip().lower() in (':quit', ':q', 'exit'):
            break
        if q.strip().lower() == ':import':
            summary = import_files_via_dialog()
            print(summary.get('message'))
            continue
        hits = query_docs(q)
        print('\n--- Context ---')
        for h in hits:
            print(h[:200].replace('\n',' ') + '...')
        print('--------------')
