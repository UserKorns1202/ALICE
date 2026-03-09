"""
Example VRGL setup config. Copy this into the VRGL project as `vrgl_setup.py`
and edit values to match the local layout. The VRGL code should import
this module (or read environment variables) instead of hardcoding paths.

Only put non-sensitive example values here; use a separate secrets file
for real API keys and credentials.
"""

import os

# Piper TTS
# Either set `PIPER_URL` (e.g. "http://127.0.0.1:5001") or set `PIPER_DIR`
# to the folder containing Piper's `server.js` so helper code can start it.
PIPER_URL = os.getenv('PIPER_URL', '')
PIPER_DIR = os.getenv('PIPER_DIR', '')

# Path to ALICE resources if you want to reference shared assets
# e.g. audio, models, or utility modules. Leave empty to use local VRGL copies.
ALICE_SHARED_PATH = os.getenv('ALICE_SHARED_PATH', '')

# Remote access helper module (if reusing ALICE's remote_access)
REMOTE_ACCESS_MODULE_PATH = os.getenv('REMOTE_ACCESS_MODULE_PATH', '')

# Secrets file path (should be excluded from VCS)
SECRETS_FILE = os.getenv('VRGL_SECRETS_FILE', 'vrgl_secrets.py')

# Optional: default wake word mapping and model name
WAKE_WORD = os.getenv('VRGL_WAKE_WORD', 'virgil')
AI_MODEL = os.getenv('VRGL_AI_MODEL', 'vrgl')

# Example helper for loading secrets safely
def load_secrets(path=None):
    path = path or SECRETS_FILE
    if not path:
        return {}
    try:
        ns = {}
        with open(path, 'r', encoding='utf-8') as f:
            code = f.read()
        exec(code, ns)
        return ns
    except Exception:
        return {}
