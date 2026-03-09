# VRGL Migration Notes

Overview
- This file documents minimal steps to bring a trimmed VRGL copy up-to-date with ALICE features
  without hardcoding resource paths or secrets.

Quick steps
1. Copy `vrgl_setup.example.py` into the VRGL repo as `vrgl_setup.py` and edit values.
2. Put secrets (API keys, tokens) into a file excluded from VCS (e.g. `vrgl_secrets.py`) and set
   `VRGL_SECRETS_FILE` in `vrgl_setup.py` or the environment.
3. Where VRGL currently hardcodes paths to Piper, remote access, or shared assets, import the
   setup module and use its values. Example:

```py
# old: piper_tts.PIPER_URL = 'http://127.0.0.1:5001'
from vrgl_setup import PIPER_URL, PIPER_DIR
if PIPER_URL:
    piper_tts.PIPER_URL = PIPER_URL
elif PIPER_DIR:
    # code that starts or points to Piper using PIPER_DIR
    pass
```

4. To reuse ALICE's `remote_access` helper, set `REMOTE_ACCESS_MODULE_PATH` to the folder
   containing ALICE's `remote_access.py`, then adjust `sys.path` or import dynamically:

```py
import sys
from vrgl_setup import REMOTE_ACCESS_MODULE_PATH
if REMOTE_ACCESS_MODULE_PATH:
    if REMOTE_ACCESS_MODULE_PATH not in sys.path:
        sys.path.insert(0, REMOTE_ACCESS_MODULE_PATH)
    import remote_access
```

5. Replace any hardcoded `config.txt` reads/writes with either environment variables or
   values from `vrgl_setup.py` so VRGL remains portable.

Notes and recommendations
- Keep `vrgl_setup.py` under the VRGL repo root and exclude secrets from version control.
- For large subsystems (speech, Piper), prefer pointing to ALICE's shared paths rather than
  copying binaries; use `ALICE_SHARED_PATH` to reference shared assets.
- Run a smoke test after migration: start VRGL with `python main.py` (or your entrypoint) and
  verify TTS and remote access behave.
