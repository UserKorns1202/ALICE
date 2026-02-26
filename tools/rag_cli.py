"""Simple CLI for ingesting an Obsidian vault and querying the RAG manager.

Usage examples:
    python -m tools.rag_cli --ingest "C:/Users/troyk/Documents/Personal"
    python -m tools.rag_cli --query "How do I reset my router?"
"""
import argparse
import os
import sys

from tools.rag import RagManager


DEFAULT_VAULT = os.path.expanduser(r"C:\Users\troyk\Documents\Personal")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ingest", help="Path to Obsidian vault to ingest", nargs="?", const=DEFAULT_VAULT)
    p.add_argument("--embed", help="Embed chunks during ingest (requires Ollama/OpenAI)", action="store_true")
    p.add_argument("--query", help="Run a query against the index", nargs="?")
    p.add_argument("--store", help="Path to persist vector store", default=None)
    p.add_argument("--topk", help="Top-k retrieval", type=int, default=5)
    args = p.parse_args()

    manager = RagManager(store_path=args.store)

    if args.ingest:
        vault = args.ingest or DEFAULT_VAULT
        print(f"Ingesting vault: {vault} (embed={args.embed})")
        docs = manager.ingest_vault(vault, embed=args.embed)
        print(f"Ingested {len(docs)} chunks. Store saved to {manager.store_path}")
        return

    if args.query:
        query = args.query
        print(f"Query: {query}")
        res = manager.answer_with_notes(query, top_k=args.topk)
        print("\n--- ANSWER ---\n")
        print(res.get("answer"))
        print("\n--- SOURCES ---\n")
        for i, s in enumerate(res.get("sources", [])):
            print(f"{i+1}. {s.get('path') or s.get('id')}")
        return

    p.print_help()


if __name__ == "__main__":
    main()
