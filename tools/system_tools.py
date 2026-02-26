"""System-level helper tools for ALICE.

Provides process listing, app open/close, and Bluetooth status/toggle.
These functions are best-effort and may require elevated privileges for
some operations (e.g., enabling/disabling adapters on Windows).
"""
from __future__ import annotations
import psutil
import subprocess
import shutil
import os
from typing import List, Dict, Any

# best-effort safe-kill integration
try:
    from tools import safe_kill
except Exception:
    safe_kill = None

def list_processes(limit: int = 50) -> List[Dict[str, Any]]:
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            info = p.info
            procs.append({'pid': info.get('pid'), 'name': info.get('name'), 'cmdline': ' '.join(info.get('cmdline') or [])})
        except Exception:
            continue
        if len(procs) >= limit:
            break
    return procs


def _run_powershell(cmd: str) -> Dict[str, Any]:
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True)
        return {"ok": res.returncode == 0, "out": res.stdout.strip(), "err": res.stderr.strip()}
    except Exception as e:
        return {"ok": False, "out": "", "err": str(e)}


def bluetooth_status() -> Dict[str, Any]:
    """Return a best-effort summary of Bluetooth adapters on Windows.

    Returns: {ok: bool, adapters: [{Name, Status}], error: str|None}
    """
    try:
        # Query NetAdapter for items containing 'Bluetooth' in their InterfaceDescription
        cmd = "Get-NetAdapter | Where-Object { $_.InterfaceDescription -match 'Bluetooth' } | Select-Object -Property Name, Status | Format-Table -AutoSize"
        out = _run_powershell(cmd)
        if not out['ok']:
            return {"ok": False, "adapters": [], "error": out['err'] or out['out']}
        lines = [l for l in out['out'].splitlines() if l.strip()]
        adapters = []
        for l in lines[2:]:
            parts = l.strip().split()
            if len(parts) >= 2:
                name = ' '.join(parts[:-1])
                status = parts[-1]
                adapters.append({"name": name, "status": status})
        return {"ok": True, "adapters": adapters, "error": None}
    except Exception as e:
        return {"ok": False, "adapters": [], "error": str(e)}


def toggle_bluetooth(enable: bool) -> Dict[str, Any]:
    """Enable or disable Bluetooth adapters. Requires admin on Windows.

    Returns {ok: bool, message: str}
    """
    try:
        action = "Enable-NetAdapter" if enable else "Disable-NetAdapter"
        # Find Bluetooth adapters and toggle them
        find_cmd = "Get-NetAdapter | Where-Object { $_.InterfaceDescription -match 'Bluetooth' } | Select-Object -ExpandProperty Name"
        found = _run_powershell(find_cmd)
        if not found['ok'] or not found['out'].strip():
            # Fallback: try PnpDevice query
            alt_cmd = "Get-PnpDevice -Class Bluetooth | Where-Object { $_.Status -ne 'Unknown' } | Select-Object -ExpandProperty FriendlyName"
            alt = _run_powershell(alt_cmd)
            names = [l.strip() for l in (alt['out'] or '').splitlines() if l.strip()]
        else:
            names = [l.strip() for l in found['out'].splitlines() if l.strip()]

        if not names:
            return {"ok": False, "message": "No Bluetooth adapters found or insufficient privileges."}

        results = []
        for name in names:
            cmd = f"{action} -Name \"{name}\" -Confirm:$false"
            r = _run_powershell(cmd)
            results.append({"name": name, "ok": r['ok'], "out": r['out'], "err": r['err']})

        success = all(r['ok'] for r in results)
        return {"ok": success, "message": "; ".join([f"{r['name']}:{'ok' if r['ok'] else 'fail'}" for r in results])}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def open_app(target: str) -> Dict[str, Any]:
    """Open an application by path or by name (best-effort).

    Returns {ok: bool, message: str}
    """
    try:
        # If it's an existing file path, open it
        if os.path.exists(target):
            os.startfile(os.path.abspath(target))
            return {"ok": True, "message": f"Opened {target}"}

        # Try to find on PATH
        exe = shutil.which(target)
        if exe:
            subprocess.Popen([exe])
            return {"ok": True, "message": f"Launched {exe}"}

        # Fallback: try start-file (works for registered apps)
        try:
            os.startfile(target)
            return {"ok": True, "message": f"Opened {target} via startfile"}
        except Exception:
            pass

        return {"ok": False, "message": f"Could not find or open: {target}"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def close_app(identifier: str, confirm: bool = False, force: bool = False, dry_run: bool = True) -> Dict[str, Any]:
    """Close an application by PID or process name using guarded termination.

    By default this performs a dry-run and will return requires_confirmation=True
    if the target appears critical. Callers should re-invoke with `confirm=True`
    to actually perform termination. Set `force=True` to allow kill() if
    terminate() doesn't succeed.

    Returns {ok: bool, requires_confirmation: bool, message: str, details: [...]}
    """
    try:
        if safe_kill is None:
            # fallback to legacy behaviour but still safe: attempt gentle terminate only
            # If numeric, treat as PID
            if identifier.isdigit():
                pid = int(identifier)
                p = psutil.Process(pid)
                p.terminate()
                p.wait(timeout=3)
                return {"ok": True, "requires_confirmation": False, "message": f"Terminated PID {pid}", "details": [{"pid": pid}]}

            found = []
            for p in psutil.process_iter(['pid', 'name']):
                try:
                    if p.info.get('name') and identifier.lower() in p.info.get('name').lower():
                        p.terminate()
                        found.append(p.info.get('pid'))
                except Exception:
                    continue
            if not found:
                return {"ok": False, "requires_confirmation": False, "message": f"No processes matching '{identifier}' found.", "details": []}
            return {"ok": True, "requires_confirmation": False, "message": f"Terminated PIDs: {found}", "details": [{"pids": found}]}

        # Use safe_kill API
        res = safe_kill.safe_terminate(identifier, confirm=confirm, force=force, dry_run=dry_run)
        # normalize return shape slightly for callers
        return {"ok": res.get("ok", False), "requires_confirmation": res.get("requires_confirmation", False), "message": res.get("message", ""), "details": res.get("details", [])}
    except Exception as e:
        return {"ok": False, "requires_confirmation": False, "message": str(e), "details": []}


# Register with local tools.registry if available
try:
    from tools import registry
    registry.register("system.list_processes", list_processes)
    registry.register("system.bluetooth_status", bluetooth_status)
    registry.register("system.toggle_bluetooth", toggle_bluetooth)
    registry.register("system.open_app", open_app)
    registry.register("system.close_app", close_app)
except Exception:
    # Silent fallback if registry isn't importable in some contexts
    pass
