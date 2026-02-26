# Piper wrapper (local neural TTS)

This folder contains a small Node/Express wrapper around the Piper TTS binary and ONNX voice models.

What is here
- `server.js` - Express server exposing `/tts` and `/voices` endpoints.
- `piper.exe` - pre-bundled Windows binary (if included).
- `models/` - where ONNX voice models must be placed.
- `piper-installer.bat` and `voice-installer.bat` - helper scripts that attempt to download Piper and a default voice (Windows, may require Chocolatey and admin rights).
- `start-piper.ps1` - convenience PowerShell script to install npm deps, run the voice installer if needed, and launch the server in a new terminal.

Quick start (Windows)
1. Open PowerShell in this folder (`c:\Users\troyk\OneDrive\Documents\Amica\piper`).
2. Run the helper (it requires Node.js installed):

```powershell
# Run once
.\start-piper.ps1
```

The script will:
- run `npm ci` (or `npm install`)
- if `models/` contains no .onnx files, attempt to run `voice-installer.bat` to fetch a sample voice (this may require Chocolatey and admin privileges)
- open a new cmd window and run `npm start` which runs `node server.js` (server listens on port 5001 by default)

Manual start (if you don't want the helper script)
1. Ensure you have at least one ONNX voice in `models/` (e.g. `en-us-amy-low.onnx`). If not, run `voice-installer.bat` from a cmd prompt.
2. Install Node deps:

```powershell
npm ci
```

3. Start the server:

```powershell
npm start
```

Test the server
- List voices:
  - `GET http://127.0.0.1:5001/voices`
- Generate speech (GET):
  - `GET http://127.0.0.1:5001/tts?text=hello%20world` -> returns WAV
- Generate speech (POST):
  - `POST http://127.0.0.1:5001/tts` with JSON `{ "text": "hello world", "voice": "en-us-amy-low.onnx" }`

Wiring to Amica
- In Amica Settings → TTS → choose `piper` as the backend.
- Set `Piper URL` to `http://127.0.0.1:5001`.

Notes
- Models can be large (hundreds of MB). If `voice-installer.bat` fails you can manually download a model release from the Piper project and place the ONNX file into `models/`.
- Running Piper on CPU can be slow for large models; GPU or optimized ONNX runtimes help.
- If you want, I can add a fallback in `amica-tts` to call Piper when available and otherwise use pyttsx3.