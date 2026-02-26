"""Safe process termination helpers.

Provide guarded APIs for closing/killing processes with checks and a confirm-first flow.

API:
- find_procs(identifier) -> list[psutil.Process]
- is_critical_process(proc) -> bool
- safe_terminate(identifier, confirm=False, force=False, dry_run=True, timeout=5) -> dict

The function returns a dict with keys: ok (bool), requires_confirmation (bool), message (str), details (list).
"""
from __future__ import annotations

import time
import typing

try:
    import psutil
except Exception:  # pragma: no cover - informative fallback
    psutil = None

CRITICAL_NAMES = {
    "winlogon.exe",
    "csrss.exe",
    "lsass.exe",
    "explorer.exe",
    "svchost.exe",
    "system",
    "system idle process",
}


def _ensure_psutil():
    if psutil is None:
        return False, "psutil is required: pip install psutil"
    return True, None


def find_procs(identifier: typing.Union[int, str]) -> list:
    ok, msg = _ensure_psutil()
    if not ok:
        raise RuntimeError(msg)

    matches = []
    if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
        pid = int(identifier)
        try:
            p = psutil.Process(pid)
            matches.append(p)
        except Exception:
            return []
        return matches

    name = str(identifier).lower()
    for p in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
        try:
            pname = (p.info.get('name') or '').lower()
            if pname == name or pname.startswith(name) or name in (p.info.get('exe') or '').lower() or any(name in (c or '').lower() for c in p.info.get('cmdline') or []):
                matches.append(p)
        except Exception:
            continue
    return matches


def is_critical_process(proc: 'psutil.Process') -> bool:
    try:
        name = (proc.name() or '').lower()
        if name in CRITICAL_NAMES:
            return True
        # very low pids are usually critical on Windows
        if proc.pid <= 4:
            return True
        return False
    except Exception:
        return True


def safe_terminate(identifier: typing.Union[int, str], *, confirm: bool = False, force: bool = False, dry_run: bool = True, timeout: float = 5.0) -> dict:
    """Attempt to terminate processes matched by `identifier`.

    Args:
      identifier: PID (int/str) or process name substring.
      confirm: if False and action is potentially dangerous return requires_confirmation.
      force: when True allow kill() if terminate() hangs.
      dry_run: if True, only report what would be done.
      timeout: seconds to wait for graceful termination before forcing.

    Returns:
      dict: {ok, requires_confirmation, message, details:[{pid,name,action}]}
    """
    ok, msg = _ensure_psutil()
    if not ok:
        return {"ok": False, "requires_confirmation": False, "message": msg, "details": []}

    procs = find_procs(identifier)
    if not procs:
        return {"ok": False, "requires_confirmation": False, "message": f"No process found for '{identifier}'", "details": []}

    details = []
    dangerous = False
    for p in procs:
        try:
            pname = p.name()
        except Exception:
            pname = '<unknown>'
        info = {"pid": getattr(p, 'pid', None), "name": pname}
        if is_critical_process(p):
            info['risk'] = 'critical'
            dangerous = True
        else:
            info['risk'] = 'normal'
        details.append(info)

    if dangerous and not confirm:
        return {"ok": False, "requires_confirmation": True, "message": "One or more matching processes are critical - confirmation required.", "details": details}

    if dry_run:
        return {"ok": True, "requires_confirmation": False, "message": "Dry-run: termination planned.", "details": details}

    results = []
    for p in procs:
        try:
            p_name = p.name()
            p_pid = p.pid
            p.terminate()
            gone = False
            try:
                p.wait(timeout=timeout)
                gone = True
            except Exception:
                gone = False
            if not gone and force:
                p.kill()
                try:
                    p.wait(timeout=2)
                    gone = True
                except Exception:
                    gone = False
            results.append({"pid": p_pid, "name": p_name, "terminated": gone})
        except Exception as e:
            results.append({"pid": getattr(p, 'pid', None), "name": getattr(p, 'name', lambda: '<unknown>')(), "terminated": False, "error": str(e)})

    overall_ok = any(r.get('terminated') for r in results)
    message = "One or more processes terminated." if overall_ok else "No processes were terminated."
    return {"ok": overall_ok, "requires_confirmation": False, "message": message, "details": results}


if __name__ == '__main__':
    # quick CLI for local testing
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument('target')
    p.add_argument('--confirm', action='store_true')
    p.add_argument('--force', action='store_true')
    p.add_argument('--no-dry-run', dest='dry', action='store_false')
    p.add_argument('--timeout', type=float, default=5.0)
    args = p.parse_args()
    res = safe_terminate(args.target, confirm=args.confirm, force=args.force, dry_run=args.dry, timeout=args.timeout)
    import json

    print(json.dumps(res, indent=2))
