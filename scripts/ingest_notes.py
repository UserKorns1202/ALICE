"""
ingest_notes.py

Standalone document ingestion → markdown-notes tool with Ollama integration.

Features:
- GUI file picker (Tkinter) or `--file` CLI argument
- Parsers for PDF, DOCX, Markdown, plain text
- Chunking with overlap and configurable size
- Sends chunks to Ollama (HTTP -> http://localhost:11434 or `ollama query` fallback)
- Accumulates and writes a single coherent Markdown notes file

Usage:
    python scripts/ingest_notes.py         # GUI prompt
    python scripts/ingest_notes.py --file path/to/doc.pdf

Make sure Ollama is running locally or in PATH.
Add this script as a sub-component to ALICE by calling `ingest_document(path)`.
"""

import argparse
import os
import sys
import subprocess
import json
from pathlib import Path
from typing import Generator, Optional

try:
    import tkinter as tk
    from tkinter import filedialog
except Exception:
    tk = None

try:
    import requests
except Exception:
    requests = None

try:
    from PyPDF2 import PdfReader
except Exception:
    PdfReader = None

try:
    import docx
except Exception:
    docx = None


def select_file_via_dialog() -> Optional[str]:
    if tk is None:
        print("Tkinter not available; pass --file instead.")
        return None
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(title="Select document to ingest")
    return file_path or None


def read_text_from_pdf(path: str) -> str:
    if PdfReader is None:
        raise RuntimeError("PyPDF2 not installed (pip install PyPDF2)")
    reader = PdfReader(path)
    pages = []
    for p in reader.pages:
        try:
            pages.append(p.extract_text() or "")
        except Exception:
            pages.append("")
    return "\n\n".join(pages)


def read_text_from_docx(path: str) -> str:
    if docx is None:
        raise RuntimeError("python-docx not installed (pip install python-docx)")
    doc = docx.Document(path)
    paragraphs = [p.text for p in doc.paragraphs if p.text]
    return "\n\n".join(paragraphs)


def read_text(path: str) -> str:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        return read_text_from_pdf(path)
    if suffix == ".docx":
        return read_text_from_docx(path)
    # treat markdown, text, and others as plain text
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def chunk_text(text: str, max_chars: int = 3000, overlap: int = 300) -> Generator[str, None, None]:
    start = 0
    n = len(text)
    while start < n:
        end = min(start + max_chars, n)
        chunk = text[start:end]
        yield chunk
        if end == n:
            break
        start = max(0, end - overlap)


def try_ollama_http(prompt: str, model: str, max_tokens: int, temperature: float) -> Optional[str]:
    if requests is None:
        return None
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    try:
        # Use streaming to handle Ollama's chunked JSON responses
        r = requests.post(url, json=payload, timeout=120, stream=True)
        r.raise_for_status()
        # Try to parse as a single JSON object first
        try:
            data = r.json()
            if isinstance(data, dict):
                for k in ("text", "content", "result", "response"):
                    if k in data and isinstance(data[k], str):
                        return data[k]
                for v in data.values():
                    if isinstance(v, str):
                        return v
            return r.text
        except Exception:
            # Fallback: parse newline-delimited JSON streaming chunks
            assembled = []
            try:
                for line in r.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    line = line.strip()
                    try:
                        obj = json.loads(line)
                        if isinstance(obj, dict):
                            if "response" in obj and isinstance(obj["response"], str):
                                assembled.append(obj["response"])
                            elif "text" in obj and isinstance(obj["text"], str):
                                assembled.append(obj["text"])
                            elif "content" in obj and isinstance(obj["content"], str):
                                assembled.append(obj["content"])
                            elif "result" in obj and isinstance(obj["result"], str):
                                assembled.append(obj["result"])
                    except Exception:
                        # Not JSON — append raw chunk
                        assembled.append(line)
            except Exception:
                pass
            if assembled:
                return "".join(assembled)
            return None
    except Exception:
        return None


def try_ollama_cli(prompt: str, model: str) -> Optional[str]:
    # Try common Ollama CLI invocation patterns as a fallback
    attempts = [
        ["ollama", "query", model, prompt],
        ["ollama", "generate", model, "--prompt", prompt],
        ["ollama", "run", model, "--prompt", prompt],
        ["ollama", "generate", model, prompt],
    ]
    for cmd in attempts:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            out = proc.stdout.strip()
            if out:
                return out
        except Exception:
            continue
    return None


def send_to_ollama(prompt: str, model: str = "llama3.2", max_tokens: int = 2048, temperature: float = 0.3) -> str:
    # Try HTTP first, then CLI fallback
    out = try_ollama_http(prompt, model, max_tokens, temperature)
    if out:
        return out
    out = try_ollama_cli(prompt, model)
    if out:
        return out
    raise RuntimeError("Could not contact Ollama (HTTP or CLI). Ensure it's running and accessible.")


def post_process_notes(notes: str, original_text: str, model: str, max_tokens: int, temperature: float) -> str:
    # For long texts, summarize original for context
    if len(original_text) > 10000:
        # Chunk and summarize key parts, but for simplicity, use first and last parts
        summary = original_text[:5000] + "\n...\n" + original_text[-5000:]
    else:
        summary = original_text
    prompt = (
        "You are refining reading annotations for an entire book. Below are the accumulated annotations and a summary of the original text.\n"
        "Tasks:\n"
        "- Ensure coherence and flow across sections.\n"
        "- Check for completeness: Add missing key ideas, themes, examples, arguments, or connections. Expand on each major point with more details, quotes, and insights.\n"
        "- Fix inconsistencies or repetitions.\n"
        "- Add cross-references, an index of key terms, and a final summary like a student's study guide.\n"
        "- Maintain the annotation style: informal, insightful, with bullets, quotes, questions.\n"
        "- Significantly expand the notes to cover the full depth of the book, ensuring no major content is missed.\n"
        "Output only the refined markdown annotations.\n"
        f"Original text summary:\n---\n{summary}\n---\nAccumulated annotations:\n---\n{notes}\n---\nRefined annotations:"
    )
    return send_to_ollama(prompt, model=model, max_tokens=max_tokens, temperature=temperature)


def build_prompt(chunk: str, previous_notes: Optional[str]) -> str:
    system = (
        "You are an avid reader taking detailed, copious annotations while reading this book. Produce extensive, insightful notes in markdown format, mimicking the style of personal reading annotations.\n"
        "Style guidelines:\n"
        "- Use informal, flowing language as if jotting down thoughts on the side.\n"
        "- Organize by major sections with ## headings, but keep subsections minimal.\n"
        "- Use bullet points (-) for key ideas, quotes, questions, connections, and personal reflections.\n"
        "- Highlight important quotes with > or **.\n"
        "- Include questions you might ask, connections to real life or other concepts, and 'aha' moments.\n"
        "- Avoid formal definitions unless naturally arising; focus on understanding and implications.\n"
        "- Make it cohesive and narrative-like, like a stream of consciousness while reading.\n"
        "- Be thorough: Cover all main ideas, themes, examples, and arguments in the chunk. Do not summarize lightly; extract and annotate extensively.\n"
        "- End with a brief transition note if continuing to next section.\n"
        "Do not include any metadata like author, ISBN, publisher, or generation info — just the notes.\n"
        "Output only the markdown notes content.\n"
    )
    prev = "" if not previous_notes else f"Previous annotations for continuity:\n{previous_notes}\n---\n"
    prompt = f"{system}{prev}Current section to annotate:\n---\n{chunk}\n---\nProduce the extensive annotations now."
    return prompt


def ingest_document(path: str, *, out_dir: Optional[str] = None, model: str = "llama3.2", max_chars: int = 5000, overlap: int = 500, max_tokens: int = 4096, temperature: float = 0.3) -> str:
    text = read_text(path)
    base = Path(path).stem
    out_dir = out_dir or str(Path(path).parent)
    output_path = Path(out_dir) / f"{base}_notes.md"

    accumulated = []
    previous_notes = ""
    chunk_index = 0
    for chunk in chunk_text(text, max_chars=max_chars, overlap=overlap):
        chunk_index += 1
        prompt = build_prompt(chunk, previous_notes)
        print(f"Processing chunk {chunk_index}...")
        reply = send_to_ollama(prompt, model=model, max_tokens=max_tokens, temperature=temperature)
        # normalize reply
        reply = reply.strip()
        # ensure it starts with markdown header — if not, wrap
        accumulated.append(reply)
        # keep recent notes for continuity (trim to last ~4000 chars)
        concat = "\n\n".join(accumulated[-4:])
        previous_notes = concat[-4000:]

    final = "\n\n".join(accumulated)
    # Post-process for coherence and completeness
    print("Post-processing notes for coherence...")
    refined_notes = post_process_notes(final, text, model=model, max_tokens=max_tokens, temperature=temperature)
    header = f"# Reading Annotations for {base}\n\n"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header + refined_notes)

    print(f"Notes written to: {output_path}")
    return str(output_path)


def main():
    parser = argparse.ArgumentParser(description="Ingest a document and produce markdown notes using Ollama.")
    parser.add_argument("--file", "-f", help="Path to file to ingest")
    parser.add_argument("--out", help="Output directory for notes")
    parser.add_argument("--model", default="llama3.2", help="Ollama model to use (default: llama3.2)")
    parser.add_argument("--max-chars", type=int, default=5000, help="Max characters per chunk")
    parser.add_argument("--overlap", type=int, default=500, help="Overlap characters between chunks")
    parser.add_argument("--max-tokens", type=int, default=4096, help="Max tokens for Ollama response")
    args = parser.parse_args()

    file_path = args.file
    if not file_path:
        file_path = select_file_via_dialog()
        if not file_path:
            print("No file selected.")
            sys.exit(1)

    if not os.path.exists(file_path):
        print("File not found:", file_path)
        sys.exit(1)

    try:
        out = ingest_document(file_path, out_dir=args.out, model=args.model, max_chars=args.max_chars, overlap=args.overlap, max_tokens=args.max_tokens)
        print("Done — output:", out)
    except Exception as e:
        print("Error during ingestion:", e)
        sys.exit(2)


if __name__ == "__main__":
    main()
