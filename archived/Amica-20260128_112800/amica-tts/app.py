from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, JSONResponse
import tempfile
import os
import threading

app = FastAPI(title="Amica TTS (pyttsx3)\nSimple OpenAI-like TTS endpoint for local/offline use")

# Simple lock to avoid concurrent pyttsx3 engine conflicts on some platforms
_tts_lock = threading.Lock()


def synthesize_wav_bytes(text: str, voice: str | None = None, rate: int | None = None) -> bytes:
    """
    Synthesize `text` to WAV bytes using pyttsx3 via a temp file.
    Returns bytes of a WAV file.
    """
    try:
        import pyttsx3
    except Exception as e:
        raise RuntimeError(f"pyttsx3 not available: {e}")

    # Create a temp file path
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    tmp_path = tmp.name
    tmp.close()

    # Create and configure engine per-call to avoid cross-thread issues
    engine = pyttsx3.init()
    try:
        if voice:
            try:
                engine.setProperty("voice", voice)
            except Exception:
                pass
        if rate is not None:
            try:
                engine.setProperty("rate", int(rate))
            except Exception:
                pass

        engine.save_to_file(text, tmp_path)
        engine.runAndWait()

        with open(tmp_path, "rb") as f:
            data = f.read()
        return data
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


@app.post("/v1/audio/speech")
async def audio_speech(req: Request):
    """
    Expected JSON body (compatible with Amica/OpenAI-style):
    { "input": "Hello world", "voice": "optional-voice-id-or-name", "rate": 150 }

    Returns: audio/wav bytes
    """
    # If the client disconnected before sending the body, abort early
    if await req.is_disconnected():
        return JSONResponse({"error": "client disconnected before request body was read"}, status_code=499)
    body = await req.json()
    # Accept either 'text' or 'input'
    text = body.get("input") or body.get("text") or body.get("message")
    if not text or not isinstance(text, str):
        raise HTTPException(status_code=400, detail="Missing 'input' (text) in request body")

    voice = body.get("voice")
    rate = body.get("rate")

    # Serialize synth under the lock to avoid engine concurrency issues on some platforms
    try:
        # If the client disconnects while we synthesize, we will try to stop early
        if await req.is_disconnected():
            return JSONResponse({"error": "client disconnected before synthesis started"}, status_code=499)
        with _tts_lock:
            wav = synthesize_wav_bytes(text, voice=voice, rate=rate)
        if await req.is_disconnected():
            # Client went away while we were synthesizing
            return JSONResponse({"error": "client disconnected during synthesis"}, status_code=499)
    except (ConnectionResetError, BrokenPipeError, OSError) as e:
        # Common when client force-closes connection; handle gracefully
        print(f"[TTS] client connection error during synthesis: {e}")
        return JSONResponse({"error": f"client connection error: {e}"}, status_code=499)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS synthesis failed: {e}")

    headers = {
        "Content-Type": "audio/wav",
        # Add a minimal Content-Disposition so browsers can download when requested
        "Content-Disposition": "attachment; filename=amica_tts.wav"
    }
    return Response(content=wav, media_type="audio/wav", headers=headers)


@app.get("/health")
async def health():
    return JSONResponse({
        "status": "ok",
        "tts_engine": "pyttsx3",
        "pyttsx3_available": _check_pyttsx3(),
    })


@app.get("/")
async def root_get(request: Request, text: str | None = None):
    """
    Compatibility helper: accept GET /?text=hello and return audio/wav.
    Many tools issue quick GET requests; this keeps them working while we encourage POST /v1/audio/speech.
    """
    if not text:
        return JSONResponse({"error": "no text provided; please call /v1/audio/speech (POST) with JSON {\"input\": \"...\"}"}, status_code=400)
    # Early disconnect check
    if await request.is_disconnected():
        return JSONResponse({"error": "client disconnected before synthesis"}, status_code=499)
    try:
        with _tts_lock:
            wav = synthesize_wav_bytes(text)
        if await request.is_disconnected():
            return JSONResponse({"error": "client disconnected during synthesis"}, status_code=499)
    except (ConnectionResetError, BrokenPipeError, OSError) as e:
        print(f"[TTS] client connection error during GET synthesis: {e}")
        return JSONResponse({"error": f"client connection error: {e}"}, status_code=499)
    except Exception as e:
        return JSONResponse({"error": f"synthesis failed: {e}"}, status_code=500)
    headers = {"Content-Type": "audio/wav", "Content-Disposition": "attachment; filename=amica_tts.wav"}
    return Response(content=wav, media_type="audio/wav", headers=headers)


def _check_pyttsx3() -> bool:
    try:
        import pyttsx3
        return True
    except Exception:
        return False


if __name__ == '__main__':
    # Only for local dev quick-run
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=5002, log_level="info")
