"""Obsidian vault ingestion: chunk markdown files into retrievable passages.

Usage:
  from tools.obsidian_ingest import ingest_vault
  chunks = ingest_vault('C:/Users/.../Vault', chunk_size_chars=2000, embed=False)

Each chunk: {id, path, title, heading, text, start, end}
"""
from __future__ import annotations

import os
import re
import json
import hashlib
from typing import Iterator, Dict, Any


def _chunk_text(text: str, chunk_size: int = 2000, overlap: int = 200) -> Iterator[Dict[str, Any]]:
    """Yield character-window chunks from `text` to avoid large allocations.

    Yields dicts: {'id', 'text', 'start', 'end'}
    """
    # Simple sliding window over characters (streaming)
    n = len(text)
    if n == 0:
        return
    i = 0
    idx = 0
    while i < n:
        end = min(i + chunk_size, n)
        chunk_text = text[i:end]
        chunk_id = hashlib.sha256((str(idx) + chunk_text).encode('utf-8')).hexdigest()[:16]
        yield {'id': chunk_id, 'text': chunk_text, 'start': i, 'end': end}
        i = max(end - overlap, end)
        idx += 1


def ingest_vault(vault_path: str, chunk_size_chars: int = 2000, overlap_chars: int = 200, embed: bool = False, embeddings_client=None, vector_store=None) -> List[Dict[str, Any]]:
    """Walk an Obsidian vault and return chunk metadata list.

    If `embed` is True, `embeddings_client` and `vector_store` must be provided
    and chunks will be embedded and added to the store.
    """
    chunks_all: List[Dict[str, Any]] = []
    for root, _, files in os.walk(vault_path):
        for fn in files:
            if not fn.lower().endswith('.md'):
                continue
            path = os.path.join(root, fn)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    raw = f.read()
            except Exception:
                continue
            # Heuristic: use first H1/H2 as title
            title_match = re.search(r'^#\s+(.+)$', raw, flags=re.M)
            title = title_match.group(1).strip() if title_match else fn

            # Prepare chunks for this file only (avoid keeping entire vault in memory)
            file_chunks = _chunk_text(raw, chunk_size=chunk_size_chars, overlap=overlap_chars)
            # If embedding is requested, embed per-file and add to vector_store immediately
            if embed and embeddings_client is not None and vector_store is not None:
                texts = [c['text'] for c in file_chunks]
                try:
                    embs = embeddings_client.embed_texts(texts)
                except Exception:
                    embs = [None] * len(texts)

                docs = []
                for c, e in zip(file_chunks, embs):
                    doc = {'id': hashlib.sha256((path + str(c['start'])).encode('utf-8')).hexdigest()[:16],
                           'embedding': e,
                           'metadata': {'path': os.path.relpath(path, vault_path), 'title': title, 'start': c['start'], 'end': c['end']}}
                    docs.append(doc)
                    # For return value keep lightweight metadata (no full text)
                    chunks_all.append({'id': doc['id'], 'path': doc['metadata']['path'], 'title': title, 'start': c['start'], 'end': c['end']})

                # add documents to vector store in one batch
                try:
                    vector_store.add_documents(docs)
                except Exception:
                    pass
            else:
                # Not embedding: keep textual chunks but still per-file to limit memory spikes
                for c in file_chunks:
                    entry = {
                        'id': hashlib.sha256((path + str(c['start'])).encode('utf-8')).hexdigest()[:16],
                        'path': os.path.relpath(path, vault_path),
                        'title': title,
                        'text': c['text'],
                        'start': c['start'],
                        'end': c['end']
                    }
                    chunks_all.append(entry)

    # Optionally embed and add to vector store
    if embed and embeddings_client is not None and vector_store is not None and chunks_all:
        texts = [c['text'] for c in chunks_all]
        embs = embeddings_client.embed_texts(texts)
        docs = []
        for c, e in zip(chunks_all, embs):
            docs.append({'id': c['id'], 'embedding': e, 'metadata': {'path': c['path'], 'title': c['title'], 'start': c['start'], 'end': c['end']}})
        vector_store.add_documents(docs)

    return chunks_all


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('vault')
    p.add_argument('--out', default='obsidian_chunks.json')
    p.add_argument('--chunk', type=int, default=2000)
    p.add_argument('--overlap', type=int, default=200)
    args = p.parse_args()
    res = ingest_vault(args.vault, chunk_size_chars=args.chunk, overlap_chars=args.overlap)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=2)
    print(f'Wrote {len(res)} chunks to {args.out}')

# Register with tools.registry if available
try:
    from tools import registry
    registry.register('rag.ingest_vault', ingest_vault)
except Exception:
    pass
