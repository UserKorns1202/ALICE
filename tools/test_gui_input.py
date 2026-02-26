import requests
import time

import os
port = os.environ.get('ALICE_HTTP_PORT', '8701')
ALICE_URL = f"http://127.0.0.1:{port}/gui_input"

payloads = [
    {
        "system": "You are a helpful assistant.",
        "messages": [
            {"role": "user", "content": "open calculator"}
        ]
    },
    {
        "system": "You are a helpful assistant.",
        "messages": [
            {"role": "user", "content": "what's the weather today"}
        ]
    }
]

for p in payloads:
    try:
        print("POSTing:", p['messages'][0]['content'])
        r = requests.post(ALICE_URL, json=p, timeout=10)
        try:
            print("Status:", r.status_code, "Response:", r.json())
        except Exception:
            print("Status:", r.status_code, "Text:", r.text)
    except Exception as e:
        print("Request failed:", e)
    time.sleep(1)
