import os
import json
import time
import logging
from typing import List, Dict, Any

try:
    from .embeddings import EmbeddingClient
    from .vector_store import VectorStore
    from .obsidian_ingest import ingest_vault as obsidian_ingest
except Exception:
    # fall back to absolute imports if package import fails
    from tools.embeddings import EmbeddingClient
    from tools.vector_store import VectorStore
    from tools.obsidian_ingest import ingest_vault as obsidian_ingest

import requests

log = logging.getLogger("tools.rag")


class RagManager:
    def __init__(self, store_path: str | None = None, embeddings_client: EmbeddingClient | None = None):
        self.store_path = store_path or os.path.join(os.path.dirname(__file__), "..", "data", "rag_store.npz")
        self.store_path = os.path.abspath(self.store_path)
        self.embeddings = embeddings_client or EmbeddingClient()
        self.vector_store = VectorStore()

        # try to load existing store if present
        try:
            if os.path.exists(self.store_path):
                self.vector_store.load(self.store_path)
                log.info(f"Loaded vector store from {self.store_path}")
        except Exception:
            log.debug("No existing vector store to load or failed to load.")

    def ingest_vault(self, vault_path: str, chunk_size_chars: int = 2000, overlap_chars: int = 200, persist: bool = True, embed: bool = False) -> List[Dict[str, Any]]:
        """Ingest an Obsidian vault into the vector store or produce chunk metadata.

        By default `embed=False` to avoid requiring an embedding backend; set `embed=True`
        to attempt embedding into the configured `VectorStore`.
        Returns list of chunk metadata (lightweight when embedding).
        """
        vault_path = os.path.abspath(vault_path)
        docs = obsidian_ingest(vault_path, chunk_size_chars=chunk_size_chars, overlap_chars=overlap_chars,
                               embed=embed, embeddings_client=(self.embeddings if embed else None), vector_store=(self.vector_store if embed else None))
        if persist:
            os.makedirs(os.path.dirname(self.store_path), exist_ok=True)
            try:
                self.vector_store.save(self.store_path)
            except Exception as e:
                log.warning(f"Failed to save vector store: {e}")
        return docs

    def save(self):
        os.makedirs(os.path.dirname(self.store_path), exist_ok=True)
        self.vector_store.save(self.store_path)

    def query(self, query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Return top_k retrieved documents (dicts with text and metadata)."""
        qvec = self.embeddings.embed_texts([query_text])
        if not qvec:
            return []
        qv = qvec[0]
        results = self.vector_store.query(qv, top_k=top_k)
        return results

    def _call_local_ollama(self, prompt: str, model: str | None = None, timeout: int = 15) -> str:
        OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
        OLLAMA_MODEL = model or os.getenv("OLLAMA_MODEL", "llama3.2")
        try:
            payload = {"model": OLLAMA_MODEL, "prompt": prompt}
            resp = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=timeout)
            try:
                j = resp.json()
                # try common shapes
                if isinstance(j, dict):
                    if "results" in j:
                        parts = []
                        for r in j.get("results", []):
                            for c in r.get("content", []):
                                if isinstance(c, dict) and c.get("type") == "output_text":
                                    parts.append(c.get("text", ""))
                        if parts:
                            return "".join(parts).strip()
                    if "choices" in j:
                        return "\n".join([c.get("text", "") for c in j.get("choices", []) if isinstance(c, dict)])
                    for k in ("text", "response", "output"):
                        if k in j and isinstance(j[k], str):
                            return j[k].strip()
            except ValueError:
                pass
            # fallback to raw text
            return (resp.text or "").strip()
        except Exception as e:
            log.debug(f"Local Ollama call failed: {e}")
            return ""

    def answer_with_notes(self, query_text: str, top_k: int = 5, model: str | None = None) -> Dict[str, Any]:
        """Retrieve relevant chunks and ask local LLM to compose an answer with inline citations.

        Returns: {answer: str, sources: List[dict], retrieved: List[dict]}
        """
        retrieved = self.query(query_text, top_k=top_k)

        # Build context block with simple citation markers
        ctx_parts = []
        sources = []
        for i, r in enumerate(retrieved):
            text = r.get("text") or r.get("content") or r.get("chunk") or ""
            meta = r.get("meta") or r.get("metadata") or {}
            src = {
                "id": meta.get("id") or r.get("id") or f"chunk-{i}",
                "path": meta.get("path") or meta.get("source") or None,
                "start": meta.get("start"),
                "end": meta.get("end")
            }
            sources.append(src)
            header = f"[SOURCE {i+1}] {src.get('path') or src.get('id') or 'unknown'}\n"
            ctx_parts.append(header + text + "\n---\n")

        prompt = """Use the following retrieved context to answer the question. Cite sources inline as [SOURCE n].

CONTEXT:
%s

QUESTION: %s

Answer concisely and include a Sources section listing the referenced source paths and brief notes.""" % ("\n".join(ctx_parts), query_text)

        answer = self._call_local_ollama(prompt, model=model)

        if not answer:
            # fallback: return joined retrieved texts
            answer = "\n\n".join([f"[SOURCE {i+1}]\n" + (r.get("text") or "") for i, r in enumerate(retrieved)])

        return {"answer": answer, "sources": sources, "retrieved": retrieved}


# Register with central registry if available
try:
    import tools.registry as registry
    try:
        registry.register("rag.answer_with_notes", lambda q, **kw: RagManager().answer_with_notes(q, **kw))
    except Exception:
        pass
except Exception:
    pass


__all__ = ["RagManager"]
