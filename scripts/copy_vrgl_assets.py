import os
import shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent
vrgl = root / 'VRGL'
assets_src = root / 'assets'

copies = []

# Ensure VRGL assets dir
vrgl_assets = vrgl / 'assets'
if not vrgl_assets.exists():
    vrgl_assets.mkdir(parents=True)

# Copy faces folder if present
faces_src = assets_src / 'faces'
if faces_src.exists():
    dst = vrgl_assets / 'faces'
    if dst.exists():
        print(f"Destination {dst} already exists; skipping copy of faces")
    else:
        shutil.copytree(faces_src, dst)
        copies.append(str(dst))
        print(f"Copied faces to {dst}")
else:
    print("No assets/faces folder found to copy")

# Copy documents used by VRGL
docs = ["documents/declaration_of_independence.txt"]
for d in docs:
    src = root / d
    if src.exists():
        dest_dir = vrgl / 'documents'
        dest_dir.mkdir(parents=True, exist_ok=True)
        dst = dest_dir / src.name
        if not dst.exists():
            shutil.copy2(src, dst)
            copies.append(str(dst))
            print(f"Copied document {src} -> {dst}")
        else:
            print(f"Document {dst} already exists; skipping")
    else:
        print(f"Document {src} not found; skipping")

# Ensure models already present (yolov3, yolov5). If models exist in root, copy them.
models_src = root
model_files = ['yolov3.weights','yolov3.cfg','yolov5s.pt']
vrgl_models = vrgl / 'models'
vrgl_models.mkdir(parents=True, exist_ok=True)
for m in model_files:
    s = models_src / m
    if s.exists():
        d = vrgl_models / m
        if not d.exists():
            shutil.copy2(s, d)
            copies.append(str(d))
            print(f"Copied model {s} -> {d}")
        else:
            print(f"Model {d} already exists; skipping")
    else:
        print(f"Model {s} not found in repo root; skipping")

print('Done. Copied:', copies)
