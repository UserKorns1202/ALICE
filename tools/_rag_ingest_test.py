from tools.rag import RagManager
import os

vault = r"C:\Users\troyk\Documents\Personal"
mgr = RagManager()
docs = mgr.ingest_vault(vault, chunk_size_chars=1200, overlap_chars=200, persist=False)
print('ingested', len(docs))
for d in docs[:10]:
    print(d.get('path'), d.get('start'), d.get('end'))
