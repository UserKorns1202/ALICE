"""SMS notification helper for ALICE/VRGL.

Configuration sources (checked in order):
1. Environment variables:
   TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER, TWILIO_TO_NUMBER
2. Local JSON file sms_config.json with keys:
   {"account_sid":"...","auth_token":"...","from":"+1...","to":"+1..."}

Provide a safe no-op fallback if credentials absent.
"""
from __future__ import annotations
import os
import json
from typing import Optional, Tuple

try:
    from twilio.rest import Client  # type: ignore
except Exception:  # Twilio not installed yet
    Client = None  # type: ignore

_CONFIG_CACHE: Optional[dict] = None

_DEF_CFG_FILE = os.path.join(os.path.dirname(__file__), "sms_config.json")


def _load_config() -> dict:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    cfg = {}
    # Env first
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    frm = os.getenv("TWILIO_FROM_NUMBER")
    to = os.getenv("TWILIO_TO_NUMBER")
    if all([sid, token, frm, to]):
        cfg = {"account_sid": sid, "auth_token": token, "from": frm, "to": to}
    else:
        # Try file
        if os.path.exists(_DEF_CFG_FILE):
            try:
                with open(_DEF_CFG_FILE, "r") as f:
                    file_cfg = json.load(f)
                if all(k in file_cfg for k in ("account_sid", "auth_token", "from", "to")):
                    cfg = file_cfg
            except Exception:
                pass
    _CONFIG_CACHE = cfg
    return cfg


def can_send() -> bool:
    if Client is None:
        return False
    cfg = _load_config()
    return bool(cfg)


def send_sms(message: str) -> Tuple[bool, str]:
    if not can_send():
        return False, "SMS not configured"
    cfg = _load_config()
    try:
        client = Client(cfg["account_sid"], cfg["auth_token"])
        resp = client.messages.create(body=message[:1600], from_=cfg["from"], to=cfg["to"])
        return True, f"SMS queued id={resp.sid}"
    except Exception as e:
        return False, f"SMS failed: {e}"

if __name__ == "__main__":
    ok, info = send_sms("Test notification from ALICE")
    print(ok, info)
