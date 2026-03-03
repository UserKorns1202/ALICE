# OCR service (scaffold)

This folder contains a minimal scaffold for a local OCR/capture service used by
`ALICE` for screen analysis. The scaffolds are purposely lightweight and
local-only so they can be tested before adding a real OCR engine or game
integration.

Files:
- `bus.py` — minimal TCP pub/sub server and client helpers.
- `capture.py` — a publisher stub sending a test `capture` message.
- `ocr_worker.py` — a worker stub that listens for `capture` messages and
  publishes simulated `ocr` messages.
- `config.json` — sample configuration.

Quick test:

Run the included smoke test to verify the bus and worker exchange messages:

```bash
python -c "from modules.ocr_service.bus import BusServer; s=BusServer(); s.start(); import time; from modules.ocr_service.ocr_worker import run_worker; import threading; t=threading.Thread(target=run_worker,daemon=True); t.start(); from modules.ocr_service.capture import send_test_capture; time.sleep(0.2); send_test_capture(); time.sleep(1); s.stop()"
```

This will start the bus, start the worker stub, publish a capture event, and
the worker will return a simulated OCR result.

Dependencies for real OCR
-------------------------
- Python packages: `mss`, `Pillow`, `pytesseract` (install into your project's
  virtual environment). Example:

```bash
pip install mss Pillow pytesseract
```

- Tesseract binary (required by `pytesseract`) must be installed on the system
  and available on `PATH`.

Windows installation options:
- Install via Chocolatey (requires admin / Chocolatey installed):

```powershell
choco install tesseract -y
```

- Install via winget:

```powershell
winget install Tesseract.OCR.Tesseract
```

- Or download the official installer and run it: https://github.com/tesseract-ocr/tesseract

Verify Tesseract:

```bash
tesseract --version
```

After installing the Tesseract binary and Python packages, rerun the
test runner to perform real OCR captures:

```bash
python -u -c "import modules.ocr_service.test_runner as tr; tr.main()"
```
