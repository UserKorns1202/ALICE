from tools.rag import RagManager
from tools import obsidian_ingest
import sys
import os

vault = r"C:\Users\troyk\Documents\Personal"
query = "Tell me about Korns Industries"
if len(sys.argv) > 1:
    query = " ".join(sys.argv[1:])

mgr = RagManager()
print("Building lightweight retrieval index (no embeddings)...")
chunks = obsidian_ingest.ingest_vault(vault, chunk_size_chars=1200, overlap_chars=200, embed=False)
print(f"Chunks available: {len(chunks)}")

qtokens = set([t for t in query.lower().split() if len(t) > 2])
scores = []
for c in chunks:
    text = (c.get('text') or '').lower()
    toks = set([t for t in text.split() if len(t) > 2])
    score = len(qtokens & toks)
    if score > 0:
        scores.append((score, c))

scores.sort(key=lambda x: x[0], reverse=True)
top = [c for _, c in scores[:5]]
print(f"Found {len(scores)} matching chunks; showing top {len(top)}")

ctx_parts = []
for i, r in enumerate(top):
    header = f"[SOURCE {i+1}] {r.get('path')}\n"
    ctx_parts.append(header + r.get('text', '') + "\n---\n")

prompt = f"Use the context below to answer the question and cite sources.\n\nCONTEXT:\n{''.join(ctx_parts)}\nQUESTION: {query}\n\nAnswer concisely and list Sources." 

print("\n--- PROMPT (truncated) ---\n")
print(prompt[:2000])

ans = mgr._call_local_ollama(prompt)
if ans:
    print("\n--- ANSWER ---\n")
    print(ans)
else:
    print("\nNo local LLM available; printing retrieved snippets:\n")
    for i, r in enumerate(top):
        print(f"{i+1}. {r.get('path')} - {r.get('text')[:400].replace('\n',' ')}\n")
