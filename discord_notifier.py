"""Discord notifier helper.

Two configuration methods:
1. Environment variables:
   DISCORD_BOT_TOKEN, DISCORD_DEFAULT_CHANNEL_ID
2. Local JSON file discord_config.json containing:
   {"bot_token":"...","default_channel_id":"123456789012345678"}

Uses HTTP POST to Discord create message endpoint (no gateway) to keep dependency light.
Note: Bot must have permission to read/send messages in target channel.
"""
from __future__ import annotations
import os
import json
import urllib.request
import urllib.error

_CFG_CACHE = None
CFG_FILE = os.path.join(os.path.dirname(__file__), "discord_config.json")
API_BASE = "https://discord.com/api/v10"


def _load_cfg():
    global _CFG_CACHE
    if _CFG_CACHE is not None:
        return _CFG_CACHE
    token = os.getenv("DISCORD_BOT_TOKEN")
    chan = os.getenv("DISCORD_DEFAULT_CHANNEL_ID")
    if token and chan:
        _CFG_CACHE = {"bot_token": token, "default_channel_id": chan}
        return _CFG_CACHE
    if os.path.exists(CFG_FILE):
        try:
            with open(CFG_FILE, "r") as f:
                data = json.load(f)
            if all(k in data for k in ("bot_token", "default_channel_id")):
                _CFG_CACHE = data
                return data
        except Exception:
            pass
    _CFG_CACHE = {}
    return _CFG_CACHE


def can_send() -> bool:
    cfg = _load_cfg()
    return bool(cfg.get("bot_token") and cfg.get("default_channel_id"))


def send_discord_message(channel_id: str | None, content: str):
    cfg = _load_cfg()
    token = cfg.get("bot_token")
    default_channel = cfg.get("default_channel_id")
    if not token:
        return False, "No bot token configured"
    cid = channel_id or default_channel
    if not cid:
        return False, "No channel id provided or configured"
    url = f"{API_BASE}/channels/{cid}/messages"
    payload = json.dumps({"content": content[:1900]}).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", f"Bot {token}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if 200 <= resp.status < 300:
                return True, "sent"
            return False, f"discord http {resp.status}"
    except urllib.error.HTTPError as e:
        return False, f"discord error {e.code}: {e.read().decode(errors='ignore')[:200]}"
    except Exception as e:
        return False, f"discord send failed: {e}"

if __name__ == "__main__":
    ok, info = send_discord_message(None, "Test message from ALICE")
    print(ok, info)
