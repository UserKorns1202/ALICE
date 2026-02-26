"""Embedding adapter: Ollama (local) first, fallback to OpenAI.

Provides EmbeddingClient.embed_texts(texts: List[str]) -> List[List[float]]
with lightweight error handling and caching helper.
"""
from __future__ import annotations

import os
import hashlib
import time
import requests
from typing import List

OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11434')
# Default to Nomic lightweight embedder for speed/size; can be overridden with OLLAMA_EMBEDDING_MODEL
OLLAMA_MODEL = os.environ.get('OLLAMA_EMBEDDING_MODEL', 'nomic-embed-text')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
EMBED_BATCH_SIZE = int(os.environ.get('EMBED_BATCH_SIZE', '128'))
EMBED_NORMALIZE = os.environ.get('EMBED_NORMALIZE', '1') in ('1', 'true', 'True')


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


class EmbeddingClient:
    def __init__(self, ollama_url: str | None = None, ollama_model: str | None = None):
        self.ollama_url = ollama_url or OLLAMA_URL
        self.ollama_model = ollama_model or OLLAMA_MODEL

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        # Helper: batch iterator
        def batches(seq, n):
            for i in range(0, len(seq), n):
                yield seq[i:i+n]

        # Try Ollama local embeddings (preferred). Use batching and retries.
        if self.ollama_url:
            url = self.ollama_url.rstrip('/') + '/api/embeddings'
            results = []
            for batch in batches(texts, EMBED_BATCH_SIZE):
                payload = {"model": self.ollama_model, "input": batch}
                backoff = 1.0
                for attempt in range(4):
                    try:
                        resp = requests.post(url, json=payload, timeout=30)
                        resp.raise_for_status()
                        j = resp.json()
                        # common shape: {data: [{embedding: [...]}, ...]}
                        if isinstance(j, dict) and 'data' in j:
                            for item in j['data']:
                                emb = item.get('embedding') or item.get('vector') or item.get('emb') or item.get('values')
                                results.append(list(emb))
                            break
                        # sometimes returns list directly
                        if isinstance(j, list) and len(j) == len(batch):
                            results.extend([list(x) for x in j])
                            break
                        # unexpected shape: try to extract arrays from any dict entries
                        if isinstance(j, dict):
                            data = j.get('data') or j.get('embeddings') or j.get('result')
                            if isinstance(data, list) and len(data) == len(batch):
                                for item in data:
                                    if isinstance(item, dict):
                                        emb = item.get('embedding') or item.get('vector') or item.get('emb')
                                        results.append(list(emb))
                                    else:
                                        results.append(list(item))
                                break
                    except Exception:
                        time.sleep(backoff)
                        backoff *= 2
                        continue

            # If HTTP path succeeded for all inputs, return.
            if len(results) == len(texts):
                if EMBED_NORMALIZE:
                    # L2 normalize embeddings
                    try:
                        import numpy as _np
                        arr = _np.array(results, dtype=_np.float32)
                        norms = _np.linalg.norm(arr, axis=1, keepdims=True)
                        norms[norms==0] = 1.0
                        arr = arr / norms
                        return arr.tolist()
                    except Exception:
                        return results
                return results

            # If HTTP path didn't yield results (some models don't expose embeddings over HTTP),
            # fall back to using the Ollama CLI `ollama run <model>` which prints embedding arrays.
            try:
                import subprocess, json as _json
                results = []
                for txt in texts:
                    cmd = ["ollama", "run", self.ollama_model, "--format", "json", txt]
                    proc = subprocess.run(cmd, capture_output=True, timeout=30)
                    out = b""
                    if proc.stdout:
                        out = proc.stdout
                    elif proc.stderr:
                        out = proc.stderr
                    out = out.decode('utf-8', errors='replace').strip()
                    try:
                        obj = _json.loads(out)
                        # If model prints the vector directly (array), accept that
                        if isinstance(obj, list):
                            results.append(obj)
                            continue
                        # If a dict with 'embedding' or similar
                        if isinstance(obj, dict):
                            emb = obj.get('embedding') or obj.get('emb') or obj.get('vector')
                            if emb:
                                results.append(emb)
                                continue
                    except Exception:
                        # Try to extract a python-like list from output by searching for '['
                        idx = out.find('[')
                        if idx != -1:
                            try:
                                obj = _json.loads(out[idx:])
                                if isinstance(obj, list):
                                    results.append(obj)
                                    continue
                            except Exception:
                                pass
                    # If we reach here, embedding not produced for this item
                    raise RuntimeError(f"Ollama CLI failed to produce embedding for input: {txt[:40]}")

                if EMBED_NORMALIZE:
                    import numpy as _np
                    arr = _np.array(results, dtype=_np.float32)
                    norms = _np.linalg.norm(arr, axis=1, keepdims=True)
                    norms[norms==0] = 1.0
                    arr = arr / norms
                    return arr.tolist()
                return results
            except Exception:
                pass

        # Fallback to OpenAI embeddings (if key available)
        if OPENAI_API_KEY:
            try:
                headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
                url = "https://api.openai.com/v1/embeddings"
                # prefer text-embedding-3-small for cost/perf if available
                payload = {"model": "text-embedding-3-small", "input": texts}
                resp = requests.post(url, json=payload, headers=headers, timeout=10)
                resp.raise_for_status()
                j = resp.json()
                data = j.get('data', [])
                return [d.get('embedding') for d in data]
            except Exception:
                pass

        raise RuntimeError('No embedding provider available (Ollama unreachable and OPENAI_API_KEY unset)')


if __name__ == '__main__':
    ec = EmbeddingClient()
    print(ec.embed_texts(["hello world", "test embedding"]))
