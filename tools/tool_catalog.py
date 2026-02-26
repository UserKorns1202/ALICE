"""Central catalog of tools and voice pattern metadata.

This file lists available tool ids, descriptions and common voice patterns.
It is intentionally minimal and safe: patterns are suggestions and the
actual voice->call wiring is done by `patterns.py` which reads this catalog.
"""
from __future__ import annotations
from typing import List, Dict

TOOL_CATALOG: List[Dict] = [
    {
        "id": "system.list_processes",
        "title": "List running processes",
        "description": "List currently running programs (pid and name).",
        "patterns": [
            r".*\b(what|which) (programs|processes) (are )?running\b.*",
            r".*\blist (running )?(programs|processes)\b.*",
        ],
    },
    {
        "id": "system.bluetooth_status",
        "title": "Bluetooth status",
        "description": "Report Bluetooth adapter status.",
        "patterns": [r".*\bbluetooth status\b.*", r".*\bis bluetooth (on|off)\b.*"],
    },
    {
        "id": "system.toggle_bluetooth",
        "title": "Toggle Bluetooth",
        "description": "Enable or disable Bluetooth adapters.",
        "patterns": [r".*\bturn bluetooth (on|off)\b.*"],
    },
    {
        "id": "system.open_app",
        "title": "Open application",
        "description": "Open an application by name or path.",
        "patterns": [r".*\b(open|launch) (.+)\b.*"],
    },
    {
        "id": "system.close_app",
        "title": "Close application",
        "description": "Close an application by name or PID.",
        "patterns": [r".*\b(close|kill|terminate) (.+)\b.*"],
    },
    # Extra tools implemented in tools.extra_tools
    {
        "id": "extra.screenshot",
        "title": "Screenshot",
        "description": "Capture screenshot to a file.",
        "patterns": [r".*\btake a screenshot\b.*", r".*\bscreenshot\b.*"],
    },
    {
        "id": "extra.battery_status",
        "title": "Battery status",
        "description": "Return battery percentage and plugged state.",
        "patterns": [r".*\bbattery status\b.*", r".*\bwhat'?s my battery\b.*"],
    },
    {
        "id": "extra.network_status",
        "title": "Network interfaces",
        "description": "Report network interfaces and state.",
        "patterns": [r".*\bnetwork status\b.*", r".*\bwhat networks are (connected|up)\b.*"],
    },
    {
        "id": "extra.find_files",
        "title": "Find files",
        "description": "Search for files by name under a folder.",
        "patterns": [r".*\bfind (?:file|files) (.+)\b.*", r".*\bsearch (?:for )?file (.+)\b.*"],
    },
]
