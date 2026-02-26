#!/usr/bin/env python3
"""
Try importing `VRGL` (the cloned package). If import fails because of missing
dependencies, run the installer script and retry. Optionally actually launch
`VRGL/VRGL.py` when `--run` is passed.

Usage:
  python scripts/ensure_and_run_vrgl.py       # just verify imports
  python scripts/ensure_and_run_vrgl.py --run # install if needed and run VRGL
"""
import sys
import subprocess
import time
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VRGL_DIR = ROOT / 'VRGL'
INSTALLER = ROOT / 'scripts' / 'install_vrgl_requirements.py'

def try_import_vrgl():
    sys.path.insert(0, str(VRGL_DIR))
    try:
        import VRGL as vr
        return True, None
    except Exception as e:
        return False, e

def run_installer():
    print('Running installer to add missing Python packages...')
    rc = subprocess.call([sys.executable, str(INSTALLER)])
    return rc == 0

def run_vrgl_process():
    p = subprocess.Popen([sys.executable, str(VRGL_DIR / 'VRGL.py')])
    print(f'VRGL started (PID {p.pid}).')
    return p

def main():
    run_flag = '--run' in sys.argv

    ok, err = try_import_vrgl()
    if ok:
        print('VRGL import succeeded.')
        if run_flag:
            run_vrgl_process()
        return 0

    print('VRGL import failed:', err)
    installed = run_installer()
    if not installed:
        print('Installer failed; please inspect output and install dependencies manually.')
        return 2

    # small delay to allow pip hooks to settle
    time.sleep(1)
    ok2, err2 = try_import_vrgl()
    if ok2:
        print('VRGL import succeeded after installing requirements.')
        if run_flag:
            run_vrgl_process()
        return 0
    else:
        print('Still failed to import VRGL after installing dependencies:', err2)
        return 3

if __name__ == '__main__':
    sys.exit(main())
