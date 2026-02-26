Amica TTS microservice (pyttsx3)
=================================

What this is
------------
A small, local FastAPI microservice that exposes a simple OpenAI-style TTS endpoint compatible with Amica's TTS integration points:

- POST /v1/audio/speech — accepts JSON {"input": "text to speak", "voice": optional, "rate": optional} and returns WAV bytes (audio/wav).
- GET /health — quick status check.

Why use it
---------
- Offline/local TTS using pyttsx3 (Windows SAPI voice support).
- Simple to run alongside Amica and point Amica's `openai_tts_url` (or equivalent) to it.

Quick start (Windows PowerShell)
-------------------------------
1. Create and activate a venv (recommended):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Run the server (development):

```powershell
python app.py
# or, run with uvicorn directly for production-ish serving:
uvicorn app:app --host 0.0.0.0 --port 5002 --workers 1
```

Try it (example):
------------------
Use the included `test_request.py` or curl to POST text and save the resulting WAV.

Example curl:

```powershell
curl -X POST http://localhost:5002/v1/audio/speech -H "Content-Type: application/json" -d '{"input":"Hello from Amica!"}' --output amica.wav
```

Configuring Amica
-----------------
Set Amica's OpenAI-style TTS URL to the new service, for example (where Amica expects `openai_tts_url`):

```
http://localhost:5002
```

Then Amica's TTS code (which posts to `\v1\audio\speech`) will receive WAV bytes and can play them.

Notes & caveats
---------------
- `pyttsx3` uses platform TTS engines (SAPI on Windows). The voice names (for `voice` param) are platform-specific; you can omit `voice` to use default.
- Concurrency: this service uses a simple threading lock to avoid pyttsx3 cross-thread issues; it serializes synthesis calls. For higher throughput use a different backend (Coqui, ElevenLabs, Piper) or pre-generate audio.
- If you need MP3 or other formats, add conversion (ffmpeg) or a different TTS engine.

If you want, I can:
- Add an optional file-caching layer to avoid re-synthesizing identical texts.
- Add an authentication header to restrict access.
- Wire this service into the Amica repo (add a small config file) and a systemd/Windows service wrapper.
