#!/usr/bin/env python3
"""
image_sorter.py

Standalone script (not attached to ALICE) to sort images found in a given directory
into the existing subfolders of that directory based on visual similarity.

Key features:
- Scans a root directory for image files and subfolders.
- Uses perceptual hashing (pHash via imagehash) to compute similarity.
- Builds a prototype hash for each existing subfolder (from images currently inside it)
  and assigns images from the root into the nearest prototype when distance <= threshold.
- Optionally (best-effort) queries a local Ollama installation to extract labels for
  improved matching (if --use-ollama is passed and Ollama is reachable). Ollama integration
  is conservative and will not break the process if Ollama is missing.
- By default runs in --dry-run mode to show proposed moves without performing them.

Notes / constraints:
- The script will ONLY move images into subfolders that already exist in the given root.
  It will not create new category folders unless --create-unknown is provided.
- This is a pragmatic, easy-to-run tool that you can extend later with CLIP embeddings
  or face-rec pipelines from your ALICE repo.

Requirements (install into your environment):
  pip install pillow imagehash numpy scikit-learn requests

Usage examples:
  python image_sorter.py "C:/path/to/photo_root" --dry-run
  python image_sorter.py "C:/path/to/photo_root" --threshold 14 --use-ollama

"""
from __future__ import annotations

import argparse
import base64
import io
import json
import logging
import math
import os
import shutil
import sys
from typing import Dict, List, Optional, Tuple

try:
    from PIL import Image
except Exception:
    print("Missing dependency: pillow. Install with `pip install pillow`.")
    raise

try:
    import imagehash
except Exception:
    print("Missing dependency: imagehash. Install with `pip install imagehash`.")
    raise

import numpy as np
import requests
import difflib
from typing import Set
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
    _HAS_SENTE = True
except Exception:
    _HAS_SENTE = False

try:
    # tkinter is available in standard Python on Windows; used to pop up a folder picker
    import tkinter as tk
    from tkinter import filedialog
    _HAS_TK = True
except Exception:
    _HAS_TK = False

ImageExtensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"}

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("image_sorter")


def find_images(root: str) -> List[str]:
    """Return list of image file paths directly under root (non-recursive)."""
    files = []
    for entry in os.listdir(root):
        path = os.path.join(root, entry)
        if os.path.isfile(path):
            ext = os.path.splitext(entry)[1].lower()
            if ext in ImageExtensions:
                files.append(path)
    return sorted(files)


def find_subfolders(root: str) -> List[str]:
    return [os.path.join(root, d) for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))]


def compute_phash(path: str, hash_size: int = 8, resize: Optional[int] = 256) -> imagehash.ImageHash:
    """Compute perceptual hash for an image after optional resizing.

    Resizing dramatically speeds up hashing for large images and reduces memory.
    """
    with Image.open(path) as im:
        try:
            im = im.convert("RGB")
            if resize:
                im = im.resize((resize, resize), Image.LANCZOS)
            return imagehash.phash(im, hash_size=hash_size)
        except Exception:
            # fall back to direct phash
            return imagehash.phash(im, hash_size=hash_size)


def hash_to_bits(h: imagehash.ImageHash) -> np.ndarray:
    # Convert ImageHash to boolean bit vector
    arr = np.asarray(h.hash, dtype=np.uint8)  # shape depends on hash_size
    return arr.reshape(-1)


def build_prototype_for_folder(folder: str, hash_size: int = 16) -> Optional[np.ndarray]:
    """Compute mean bit vector for images inside folder. Returns None if folder has no images."""
    images = []
    for fn in os.listdir(folder):
        p = os.path.join(folder, fn)
        if os.path.isfile(p) and os.path.splitext(fn)[1].lower() in ImageExtensions:
            try:
                h = compute_phash(p, hash_size=hash_size)
                images.append(hash_to_bits(h))
            except Exception as e:
                logger.debug("Skipping image %s: %s", p, e)
    if not images:
        return None
    stacked = np.stack(images, axis=0).astype(np.float32)
    mean = stacked.mean(axis=0)
    # prototype bit vector is the majority vote
    proto = (mean >= 0.5).astype(np.uint8)
    return proto


def hamming_bits(a: np.ndarray, b: np.ndarray) -> int:
    return int((a != b).sum())


def attempt_ollama_label(image_path: str) -> Optional[str]:
    """Best-effort attempt to query a local Ollama server for a textual label of the image.

    This function is intentionally conservative - Ollama setups and models vary. If the
    local Ollama HTTP API is present and a model that looks suitable for image captioning
    is found, we try to call it. If anything fails, we return None.
    """
    try:
        base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        # Check models
        models_url = f"{base}/api/models"
        r = requests.get(models_url, timeout=2.0)
        if r.status_code != 200:
            logger.debug("Ollama models endpoint returned %s", r.status_code)
            return None
        models = r.json()
        # Heuristic: find model whose name contains 'image' or 'vision' or 'clip' or 'caption'
        chosen = None
        for m in models:
            name = m.get("name", "").lower()
            if any(k in name for k in ("image", "vision", "clip", "caption", "openimage")):
                chosen = m.get("name")
                break
        if not chosen and models:
            # Fallback to first model
            chosen = models[0].get("name")
        if not chosen:
            return None

        # Read and base64 the image - some packs understand inline base64 in the prompt.
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

        # Try a safe generate call that asks the model to describe the image.
        # Many local packs accept simple text prompts; some accept a data URL. We try a few forms.
        prompt_candidates = [
            f"Describe the content of the image (concise keywords): data:image;base64,{b64}",
            "Describe the image in a few keywords.",
            "Keywords:",
        ]

        gen_url = f"{base}/api/generate"
        for prompt in prompt_candidates:
            payload = {"model": chosen, "prompt": prompt, "max_tokens": 100}
            try:
                gr = requests.post(gen_url, json=payload, timeout=10)
                if gr.status_code == 200:
                    text = gr.text
                    # try to sanitize JSON if returned
                    try:
                        decoded = gr.json()
                        # find text in response
                        if isinstance(decoded, dict):
                            # this is a best effort - different Ollama versions differ
                            txt = decoded.get("text") or decoded.get("output") or json.dumps(decoded)
                        else:
                            txt = str(decoded)
                    except Exception:
                        txt = text
                    txt = str(txt).strip()
                    if txt:
                        logger.debug("Ollama label for %s: %s", image_path, txt)
                        return txt
            except Exception:
                continue
        return None
    except Exception as e:
        logger.debug("Ollama lookup failed: %s", e)
        return None


def tokenize_text(s: str) -> Set[str]:
    toks = [t.strip(".,;:!?()[]\"'\n\r").lower() for t in s.split()]
    return set(t for t in toks if t)


def simple_text_score(a: str, b: str) -> float:
    """Return a simple similarity score between 0..1 using token Jaccard and difflib ratio."""
    if not a or not b:
        return 0.0
    a, b = a.lower(), b.lower()
    ja = tokenize_text(a)
    jb = tokenize_text(b)
    jaccard = 0.0
    if ja or jb:
        jaccard = len(ja & jb) / max(1, len(ja | jb))
    seq = difflib.SequenceMatcher(a=a, b=b).ratio()
    return max(jaccard, seq)


class EmbeddingMatcher:
    def __init__(self, folder_names: List[str]):
        if not _HAS_SENTE:
            raise RuntimeError("sentence-transformers not available")
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.folder_names = folder_names
        self.folder_embs = self.model.encode(folder_names, convert_to_numpy=True)

    def best_match(self, text: str) -> Tuple[int, float]:
        emb = self.model.encode([text], convert_to_numpy=True)
        sims = cosine_similarity(emb, self.folder_embs)[0]
        idx = int(np.argmax(sims))
        return idx, float(sims[idx])


def compute_planned_moves(root: str, threshold: int = 12, use_ollama: bool = False, hash_size: int = 8, resize: Optional[int] = 256, workers: int = 4, semantic: bool = False, semantic_method: str = "ollama", semantic_threshold: float = 0.35) -> List[Tuple[str, str, float, Optional[str]]]:
    """Compute planned moves without performing any file operations.

    Returns list of tuples: (src_path, dst_folder, score_or_distance, label_or_none)
    For semantic mode score is float in 0..1; for visual mode distance is int.
    """
    logger.info("Scanning root directory: %s", root)
    images = find_images(root)
    if not images:
        logger.info("No images found in %s", root)
        return []

    subfolders = find_subfolders(root)
    if not subfolders:
        logger.info("No subfolders found in %s - nothing to assign into.", root)
        return []

    logger.info("Found %d images and %d subfolders", len(images), len(subfolders))

    # Semantic mode
    if semantic:
        logger.info("Running semantic assignment (method=%s, threshold=%s).", semantic_method, semantic_threshold)
        folder_names = [os.path.basename(s) for s in subfolders]
        matcher = None
        if semantic_method == "embeddings":
            if not _HAS_SENTE:
                logger.warning("sentence-transformers not installed; embeddings method unavailable. Falling back to simple matching.")
                semantic_method = "simple"
            else:
                matcher = EmbeddingMatcher(folder_names)

        planned_moves: List[Tuple[str, str, float, Optional[str]]] = []

        # Limit Ollama calls by optionally running them in parallel threads
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures_by_img = {img: ex.submit(attempt_ollama_label, img) for img in images} if semantic_method == "ollama" else {}

            for img in images:
                # obtain label according to chosen method
                if semantic_method == "ollama":
                    fut = futures_by_img.get(img)
                    try:
                        label = fut.result(timeout=10) if fut is not None else None
                    except Exception:
                        label = None
                elif semantic_method == "embeddings":
                    label = attempt_ollama_label(img)
                    if not label:
                        label = os.path.splitext(os.path.basename(img))[0]
                else:
                    label = attempt_ollama_label(img) or os.path.splitext(os.path.basename(img))[0]

                best_dst = None
                best_score = 0.0
                if matcher is not None:
                    idx, score = matcher.best_match(label)
                    best_score = score
                    best_dst = subfolders[idx]
                else:
                    for sf in subfolders:
                        score = simple_text_score(label or "", os.path.basename(sf))
                        if score > best_score:
                            best_score = score
                            best_dst = sf

                logger.debug("Image %s semantic best match %s score=%.3f label=%s", os.path.basename(img), best_dst and os.path.basename(best_dst), best_score, label)
                if best_dst is not None and best_score >= semantic_threshold:
                    planned_moves.append((img, best_dst, float(best_score), label))
                else:
                    logger.debug("Image %s did not semantically match any subfolder (best=%s score=%.3f)", os.path.basename(img), best_dst and os.path.basename(best_dst), best_score)

        return planned_moves

    # Visual mode
    # Build prototypes in parallel per-folder
    prototypes: Dict[str, np.ndarray] = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        future_map = {}
        for sf in subfolders:
            # gather images in subfolder
            imgs = [os.path.join(sf, fn) for fn in os.listdir(sf) if os.path.isfile(os.path.join(sf, fn)) and os.path.splitext(fn)[1].lower() in ImageExtensions]
            if not imgs:
                continue
            # submit per-folder worker to compute phashes and prototype
            future_map[ex.submit(_build_proto_from_list, imgs, hash_size, resize) ] = sf

        for fut in as_completed(future_map):
            sf = future_map[fut]
            try:
                proto = fut.result()
                if proto is not None:
                    prototypes[sf] = proto
                    logger.debug("Built prototype for %s", sf)
            except Exception as e:
                logger.debug("Failed to build prototype for %s: %s", sf, e)

    if not prototypes:
        logger.info("No prototypes (subfolders had no images). Nothing to compare against.")
        return []

    planned_moves: List[Tuple[str, str, float, Optional[str]]] = []
    for img in images:
        try:
            h = compute_phash(img, hash_size=hash_size)
            bits = hash_to_bits(h)
        except Exception as e:
            logger.warning("Failed to hash %s: %s", img, e)
            continue

        ollama_label = None
        if use_ollama:
            ollama_label = attempt_ollama_label(img)

        best_sf = None
        best_dist = math.inf
        for sf, proto in prototypes.items():
            d = hamming_bits(bits, proto)
            if d < best_dist:
                best_dist = d
                best_sf = sf

        logger.debug("Image %s best match %s with distance %d", os.path.basename(img), best_sf, best_dist)
        if best_sf is not None and best_dist <= threshold:
            planned_moves.append((img, best_sf, float(best_dist), ollama_label))

    return planned_moves


def apply_planned_moves(planned_moves: List[Tuple[str, str, float, Optional[str]]], dry_run: bool) -> int:
    moved = 0
    if not planned_moves:
        return 0
    logger.info("Planned moves: %d images (dry_run=%s)", len(planned_moves), dry_run)
    for src, dst, score, label in planned_moves:
        name = os.path.basename(src)
        dest_path = os.path.join(dst, name)
        if isinstance(score, float):
            score_display = f"{score:.3f}"
        else:
            score_display = str(score)
        logger.info("%s -> %s  (score=%s) %s", name, os.path.basename(dst), score_display, f"[label:{label}]" if label else "")
        if not dry_run:
            final_dest = dest_path
            base, ext = os.path.splitext(name)
            i = 1
            while os.path.exists(final_dest):
                final_dest = os.path.join(dst, f"{base}_{i}{ext}")
                i += 1
            try:
                shutil.move(src, final_dest)
                moved += 1
            except Exception as e:
                logger.error("Failed to move %s -> %s: %s", src, final_dest, e)
    return moved


def _build_proto_from_list(paths: List[str], hash_size: int, resize: Optional[int]) -> Optional[np.ndarray]:
    """Compute prototype bit vector from a list of image paths (helper for parallel use)."""
    bits_list = []
    for p in paths:
        try:
            h = compute_phash(p, hash_size=hash_size, resize=resize)
            bits_list.append(hash_to_bits(h))
        except Exception:
            continue
    if not bits_list:
        return None
    stacked = np.stack(bits_list, axis=0).astype(np.float32)
    mean = stacked.mean(axis=0)
    proto = (mean >= 0.5).astype(np.uint8)
    return proto


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="image_sorter.py", description="Sort images into existing subfolders using visual similarity.")
    p.add_argument("root", nargs="?", help="Root folder containing images and subfolders (images must be directly in root). If omitted, a folder picker will open.")
    p.add_argument("--threshold", type=int, default=12, help="Hamming distance threshold for assignment (lower=more strict)")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--dry-run", dest="dry_run", action="store_true", help="Show planned moves without performing them")
    group.add_argument("--apply", dest="apply", action="store_true", help="Actually perform the moves (dangerous!)")
    p.add_argument("--use-ollama", action="store_true", help="Attempt to use a local Ollama server for supplemental image labels (best-effort)")
    p.add_argument("--create-unknown", action="store_true", help="Allow creating an 'unknown' subfolder for unmatched images (not used by default)")
    p.add_argument("--hash-size", type=int, default=8, help="Hash size passed to phash (8 -> faster, less sensitive; 16 -> slower, more sensitive)")
    p.add_argument("--resize", type=int, default=256, help="Resize images to square size (pixels) before hashing to speed up processing. Set 0 to disable resizing.")
    p.add_argument("--workers", type=int, default=max(2, (os.cpu_count() or 2)), help="Number of worker threads for hashing and prototype building")
    p.add_argument("--semantic", action="store_true", help="Use semantic grouping (match image labels to existing folder names)")
    p.add_argument("--semantic-method", choices=["ollama", "embeddings", "simple"], default="ollama", help="Method to obtain/compare semantic labels. 'ollama' will try local Ollama; 'embeddings' uses sentence-transformers (if installed); 'simple' uses token overlap/difflib.")
    p.add_argument("--semantic-threshold", type=float, default=0.35, help="Threshold (0..1) for semantic match confidence (higher = stricter)")
    p.add_argument("--verbose", action="store_true", help="Enable verbose (debug) logging")
    args = p.parse_args(argv)

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # If root not provided, open a folder picker dialog (or fall back to console input)
    root_arg = args.root
    if not root_arg:
        root_arg = None
        if _HAS_TK:
            try:
                tk_root = tk.Tk()
                tk_root.withdraw()
                tk_root.attributes("-topmost", True)
                chosen = filedialog.askdirectory(title="Select root folder containing images and subfolders")
                tk_root.destroy()
                if chosen:
                    root_arg = chosen
            except Exception:
                root_arg = None
        if not root_arg:
            # Fallback: ask in console
            try:
                root_arg = input("Enter path to root folder: ").strip()
            except Exception:
                root_arg = None

    if not root_arg:
        logger.error("No root folder specified. Exiting.")
        return 2

    root = os.path.abspath(root_arg)
    if not os.path.isdir(root):
        logger.error("Root path is not a directory: %s", root)
        return 2

    # Decide apply vs dry-run: flags or interactive prompt
    if getattr(args, "apply", False):
        do_apply = True
    elif getattr(args, "dry_run", False):
        do_apply = False
    else:
        try:
            resp = input("Run in dry-run (show planned moves) or apply moves? [dry/apply]: ").strip().lower()
            do_apply = resp.startswith("a")
        except Exception:
            do_apply = False

    logger.info("Mode: %s", "APPLY" if do_apply else "DRY-RUN")

    # Orchestration loop: compute moves, apply, repeat until all images sorted or no progress.
    current_threshold = args.threshold
    reductions = 0
    max_reductions = 10
    max_iterations = 100
    iteration = 0

    while iteration < max_iterations:
        planned = compute_planned_moves(root, threshold=current_threshold, use_ollama=args.use_ollama, hash_size=args.hash_size, resize=args.resize, workers=args.workers, semantic=args.semantic, semantic_method=args.semantic_method, semantic_threshold=args.semantic_threshold)

        if not planned:
            # write diagnostic info to file to help debugging
            dbg = {"root": root, "threshold": current_threshold, "semantic": args.semantic, "method": args.semantic_method, "images": []}
            imgs = find_images(root)
            subfolders = find_subfolders(root)
            for img in imgs:
                rec = {"image": img, "label": None, "scores": []}
                if args.semantic:
                    lbl = attempt_ollama_label(img)
                    rec["label"] = lbl
                    for sf in subfolders:
                        sc = simple_text_score(lbl or os.path.splitext(os.path.basename(img))[0], os.path.basename(sf))
                        rec["scores"].append({"folder": os.path.basename(sf), "score": sc})
                else:
                    try:
                        h = compute_phash(img, hash_size=args.hash_size)
                        bits = hash_to_bits(h)
                        for sf in subfolders:
                            proto = build_prototype_for_folder(sf, hash_size=args.hash_size)
                            if proto is None:
                                d = None
                            else:
                                d = int(hamming_bits(bits, proto))
                            rec["scores"].append({"folder": os.path.basename(sf), "distance": d})
                    except Exception as e:
                        rec["error"] = str(e)
                dbg["images"].append(rec)
            dbg_path = os.path.join(root, "image_sorter_debug.json")
            try:
                with open(dbg_path, "w", encoding="utf-8") as f:
                    json.dump(dbg, f, indent=2)
                logger.info("No matches found; wrote diagnostics to %s", dbg_path)
            except Exception as e:
                logger.info("No matches found; failed to write diagnostics: %s", e)

            if reductions < max_reductions and current_threshold > 0:
                current_threshold = max(0, current_threshold - 5)
                reductions += 1
                logger.info("No matches found; lowering threshold to %d and retrying (reduction #%d)", current_threshold, reductions)
                iteration += 1
                continue
            else:
                logger.info("No matches found and cannot lower threshold further. Exiting.")
                break

        if not do_apply:
            apply_planned_moves(planned, dry_run=True)
            logger.info("Dry-run complete. %d planned moves shown.", len(planned))
            break

        moved = apply_planned_moves(planned, dry_run=False)
        if moved == 0:
            if reductions < max_reductions and current_threshold > 0:
                current_threshold = max(0, current_threshold - 5)
                reductions += 1
                logger.info("No files moved; lowering threshold to %d and retrying (reduction #%d)", current_threshold, reductions)
                iteration += 1
                continue
            else:
                logger.info("No files moved and cannot reduce threshold further. Exiting.")
                break

        reductions = 0
        remaining = find_images(root)
        if not remaining:
            logger.info("All images sorted. Done.")
            break
        else:
            logger.info("%d images remain; continuing iteration.", len(remaining))
            iteration += 1
            continue

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
