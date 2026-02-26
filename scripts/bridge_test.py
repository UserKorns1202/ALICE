#!/usr/bin/env python3
"""
Small diagnostic script to test KEVIN and ALICE bridge endpoints locally.

Usage examples:
  python scripts/bridge_test.py --bridge http://127.0.0.1:8700 --key THE_BRIDGE_KEY
  python scripts/bridge_test.py --kevin http://127.0.0.1:5000

This will POST a simple prompt and print status codes and response bodies
so you can see Pydantic/validation errors (422) and any error details.
"""
import argparse
import json
import sys
from typing import Any, Dict

try:
    import requests
except Exception:
    print("Please install requests: pip install requests")
    raise


def pretty_print_resp(resp: requests.Response):
    print(f"URL: {resp.request.url}")
    print(f"Status: {resp.status_code}")
    print("--- Response headers ---")
    for k, v in resp.headers.items():
        print(f"{k}: {v}")
    print("--- Response body ---")
    text = resp.text
    # try to pretty-json
    try:
        j = resp.json()
        print(json.dumps(j, indent=2, ensure_ascii=False))
    except Exception:
        print(text)


def post_json(url: str, payload: Dict[str, Any], headers: Dict[str, str] = None, timeout=10):
    headers = headers or {}
    headers.setdefault("Content-Type", "application/json")
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=timeout)
        return r
    except requests.RequestException as e:
        print(f"Request to {url} failed: {e}")
        return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--bridge', default='http://127.0.0.1:8700', help='Bridge base URL')
    p.add_argument('--kevin', default='http://127.0.0.1:5000', help='KEVIN base URL')
    p.add_argument('--key', default=None, help='Bridge API key (x-bridge-api-key header)')
    args = p.parse_args()

    kevin_url = args.kevin.rstrip('/')
    bridge_url = args.bridge.rstrip('/')

    # payload the bridge normally uses
    payload = {"text": "[neutral] hello", "use_history": False, "speak": False}

    print("\n== Testing KEVIN directly ==")
    kevin_post = kevin_url + '/query'
    r = post_json(kevin_post, payload)
    if r is None:
        print("No response from KEVIN")
    else:
        pretty_print_resp(r)

    print("\n== Testing Bridge /query (with API key header if provided) ==")
    bridge_post = bridge_url + '/query'
    headers = {}
    if args.key:
        headers['x-bridge-api-key'] = args.key
    r2 = post_json(bridge_post, payload, headers=headers)
    if r2 is None:
        print("No response from Bridge /query")
    else:
        pretty_print_resp(r2)

    print("\n== Testing Bridge /bridge/alice (alias) ==")
    bridge_alias = bridge_url + '/bridge/alice'
    r3 = post_json(bridge_alias, {"text": "[neutral] hello"}, headers=headers)
    if r3 is None:
        print("No response from Bridge /bridge/alice")
    else:
        pretty_print_resp(r3)

    print('\nDone.')


if __name__ == '__main__':
    main()
