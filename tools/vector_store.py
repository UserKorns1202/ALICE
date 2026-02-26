"""Simple disk-backed vector store using NumPy (FAISS optional).

API:
- VectorStore(path=None) -> instance
- add(id, embedding, metadata=None)
- add_documents(docs: list[dict])  # dict: {id, embedding, metadata}
- query(embedding, top_k=5) -> list of (id, score, metadata)
- save(path), load(path)
"""
from __future__ import annotations

import os
import pickle
import math
from typing import List, Dict, Any, Tuple

try:
    import numpy as np
except Exception:
    np = None

try:
    import faiss
    _HAVE_FAISS = True
except Exception:
    faiss = None
    _HAVE_FAISS = False


class VectorStore:
    def __init__(self, path: str | None = None):
        self.path = path
        self.ids: List[str] = []
        self.embeddings = None  # numpy array (N, D)
        self.metadatas: Dict[str, Dict[str, Any]] = {}
        self.dim = None
        self._faiss_index = None

    def _ensure_numpy(self):
        if np is None:
            raise RuntimeError('numpy is required for VectorStore')

    def add(self, id: str, embedding: List[float], metadata: Dict[str, Any] | None = None):
        self._ensure_numpy()
        emb = np.array(embedding, dtype=np.float32)
        if self.embeddings is None:
            self.embeddings = emb.reshape(1, -1)
            self.dim = emb.shape[0]
        else:
            if emb.shape[0] != self.dim:
                raise ValueError('Embedding dimension mismatch')
            self.embeddings = np.vstack([self.embeddings, emb.reshape(1, -1)])
        self.ids.append(id)
        if metadata:
            self.metadatas[id] = metadata

    def add_documents(self, docs: List[Dict[str, Any]]):
        for d in docs:
            self.add(d['id'], d['embedding'], d.get('metadata'))

    def save(self, path: str | None = None):
        p = path or self.path
        if not p:
            raise RuntimeError('No path provided for saving vector store')
        data = {'ids': self.ids, 'metadatas': self.metadatas}
        if self.embeddings is not None:
            data['embeddings'] = self.embeddings.tolist()
        with open(p, 'wb') as f:
            pickle.dump(data, f)

    def load(self, path: str | None = None):
        p = path or self.path
        if not p or not os.path.exists(p):
            raise RuntimeError('No vector store found at path')
        with open(p, 'rb') as f:
            data = pickle.load(f)
        self.ids = data.get('ids', [])
        self.metadatas = data.get('metadatas', {})
        emb = data.get('embeddings')
        if emb is not None:
            self._ensure_numpy()
            self.embeddings = np.array(emb, dtype=np.float32)
            self.dim = self.embeddings.shape[1]

    def _cosine_sim(self, a: np.ndarray, b: np.ndarray) -> float:
        # expects 1D arrays
        denom = (np.linalg.norm(a) * np.linalg.norm(b))
        if denom == 0:
            return 0.0
        return float(np.dot(a, b) / denom)

    def query(self, embedding: List[float], top_k: int = 5) -> List[Tuple[str, float, Dict[str, Any]]]:
        self._ensure_numpy()
        if self.embeddings is None or len(self.ids) == 0:
            return []
        q = np.array(embedding, dtype=np.float32)
        # compute cosine similarities
        sims = []
        for i, emb in enumerate(self.embeddings):
            s = self._cosine_sim(q, emb)
            sims.append((self.ids[i], s))
        sims.sort(key=lambda x: x[1], reverse=True)
        out = []
        for id_, score in sims[:top_k]:
            out.append((id_, score, self.metadatas.get(id_, {})))
        return out


if __name__ == '__main__':
    # small sanity check
    vs = VectorStore()
    vs.add('a', [0.1, 0.2, 0.3], {'source': 'test'})
    vs.add('b', [0.0, 0.9, 0.1], {'source': 'test2'})
    print(vs.query([0.05, 0.1, 0.2], top_k=2))
