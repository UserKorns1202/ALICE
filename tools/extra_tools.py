"""Extra system utilities: screenshots, battery, network status, file search."""
from __future__ import annotations
import os
import time
from typing import Dict, Any, List
try:
    import pyautogui
except Exception:
    pyautogui = None
import psutil


def screenshot_capture(save_path: str | None = None) -> Dict[str, Any]:
    if pyautogui is None:
        return {"ok": False, "message": "pyautogui not available"}
    try:
        # Treat empty string as no path provided
        if not save_path:
            save_path = os.path.join(os.path.expanduser('~'), f"screenshot_{int(time.time())}.png")
        # Ensure extension exists; default to .png if missing
        base, ext = os.path.splitext(save_path)
        if not ext:
            save_path = base + ".png"
        img = pyautogui.screenshot()
        img.save(save_path)
        return {"ok": True, "path": save_path}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def battery_status() -> Dict[str, Any]:
    try:
        b = psutil.sensors_battery()
        if b is None:
            return {"ok": False, "message": "No battery information available"}
        return {"ok": True, "percent": b.percent, "plugged": b.power_plugged}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def network_status() -> Dict[str, Any]:
    try:
        stats = psutil.net_if_stats()
        res = [{"iface": k, "is_up": v.isup, "speed": getattr(v, 'speed', None)} for k, v in stats.items()]
        return {"ok": True, "interfaces": res}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def find_files(name_query: str, root: str | None = None, limit: int = 20) -> Dict[str, Any]:
    root = root or os.path.expanduser('~')
    found: List[str] = []
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            for fn in filenames:
                if name_query.lower() in fn.lower():
                    found.append(os.path.join(dirpath, fn))
                    if len(found) >= limit:
                        return {"ok": True, "results": found}
        return {"ok": True, "results": found}
    except Exception as e:
        return {"ok": False, "message": str(e)}


# Register with registry if available
try:
    from tools import registry
    registry.register("extra.screenshot", screenshot_capture)
    registry.register("extra.battery_status", battery_status)
    registry.register("extra.network_status", network_status)
    registry.register("extra.find_files", find_files)
except Exception:
    pass
