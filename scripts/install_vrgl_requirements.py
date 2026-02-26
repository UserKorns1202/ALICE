#!/usr/bin/env python3
"""
Install missing pip packages needed by the `VRGL` clone.
This script is conservative: it attempts to import common modules and pip-installs
well-known package names when imports fail. For large packages (torch), failures
are reported and the user may need to install manually for their platform.

Usage: python scripts/install_vrgl_requirements.py
"""
import subprocess
import sys
import importlib

MODULE_MAP = {
    'speech_recognition': 'SpeechRecognition',
    'sympy': 'sympy',
    'pygame': 'pygame',
    'psutil': 'psutil',
    'keyboard': 'keyboard',
    'pytesseract': 'pytesseract',
    'PIL': 'pillow',
    'requests': 'requests',
    'torch': 'torch',
    'torchvision': 'torchvision',
    'onnxruntime': 'onnxruntime',
    'numpy': 'numpy'
}

def pip_install(pkg):
    print(f"Installing {pkg}...")
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg])
        return True
    except subprocess.CalledProcessError as e:
        print(f"pip install failed for {pkg}: {e}")
        return False

def ensure():
    failed = []
    for mod, pkg in MODULE_MAP.items():
        try:
            importlib.import_module(mod)
            print(f"OK: {mod}")
            continue
        except Exception:
            print(f"Missing: {mod} (will try to install {pkg})")
        ok = pip_install(pkg)
        if not ok:
            failed.append((mod, pkg))
    if failed:
        print('\nSome packages failed to install:')
        for m,p in failed:
            print(f" - {m} -> {p}")
        print('You may need to install these manually or consult platform-specific docs (especially for torch).')
        return 2
    print('\nAll required packages installed (or already present).')
    return 0

if __name__ == '__main__':
    sys.exit(ensure())
