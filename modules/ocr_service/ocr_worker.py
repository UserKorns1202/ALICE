"""OCR worker: subscribes to 'capture' messages, runs local OCR (Tesseract via
`pytesseract`) on the referenced screenshot, and publishes structured OCR
results back to the bus.

If `pytesseract` or the Tesseract binary is not available the worker will
print an error and skip OCR. This keeps behavior local-only and non-cloud.
"""
import threading
import time
import os
from typing import Optional

from .bus import subscribe_forever, publish

try:
    from PIL import Image
    import pytesseract
    pytesseract_available = True
except Exception:
    pytesseract_available = False


def _locate_tesseract_binary() -> str | None:
    """Try to locate the tesseract executable in PATH or common Windows locations."""
    try:
        import shutil
        # shutil.which will check PATH
        p = shutil.which('tesseract')
        if p:
            return p
    except Exception:
        pass

    # Common install locations on Windows
    common = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files\Tesseract\tesseract.exe",
    ]
    for p in common:
        try:
            if os.path.exists(p):
                return p
        except Exception:
            continue
    return None

# If pytesseract is available, try to ensure the underlying tesseract binary
# is pointed to so OCR can run even if PATH wasn't updated for this session.
if pytesseract_available:
    try:
        bin_path = _locate_tesseract_binary()
        if bin_path:
            try:
                pytesseract.pytesseract.tesseract_cmd = bin_path
            except Exception:
                # older pytesseract may expect attribute at top-level
                try:
                    pytesseract.tesseract_cmd = bin_path
                except Exception:
                    pass
    except Exception:
        pass


def _ocr_image(path: str) -> tuple[str, float]:
    """Run Tesseract OCR on `path` and return (text, avg_confidence).

    Uses `pytesseract.image_to_data` to gather per-line confidences.
    """
    if not pytesseract_available:
        raise RuntimeError('pytesseract or PIL not available')

    img = Image.open(path)
    try:
        # Preprocessing: convert to grayscale, enhance contrast, and resize for better OCR
        from PIL import ImageOps, ImageFilter
        img = img.convert('L')
        img = ImageOps.autocontrast(img)
        img = img.filter(ImageFilter.SHARPEN)
        # Resize moderately to improve recognition of small UI text
        w, h = img.size
        target_w = min(1600, max(800, w))
        if w < target_w:
            ratio = target_w / float(w)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    except Exception:
        # If preprocessing fails, continue with original image
        pass
    # Use image_to_data for confidences
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    texts = []
    confs = []
    n = len(data.get('text', []))
    for i in range(n):
        txt = (data['text'][i] or '').strip()
        conf = data['conf'][i]
        try:
            c = float(conf)
        except Exception:
            c = -1.0
        if txt:
            texts.append(txt)
            if c >= 0:
                confs.append(c / 100.0)

    text = '\n'.join(texts)
    avg_conf = (sum(confs) / len(confs)) if confs else 0.0
    return text, float(avg_conf)


def _handle_message(msg: dict, host: str, port: int):
    try:
        topic = msg.get('topic')
        payload = msg.get('payload') or {}
    except Exception:
        return

    if topic != 'capture':
        return

    ts = time.time()
    app = payload.get('app', 'unknown')
    roi = payload.get('roi')
    screenshot = payload.get('screenshot_path')

    result = {'ts': ts, 'app': app, 'roi': roi, 'text': '', 'confidence': 0.0}

    if not screenshot:
        # No screenshot given; nothing to OCR
        publish(host, port, 'ocr', result)
        return

    if not pytesseract_available:
        # Publish a result indicating OCR unavailable
        result['text'] = ''
        result['confidence'] = 0.0
        result['meta'] = {'error': 'pytesseract or PIL not installed'}
        publish(host, port, 'ocr', result)
        return

    try:
        text, conf = _ocr_image(screenshot)
        result['text'] = text
        result['confidence'] = conf
        result['meta'] = {'screenshot_path': screenshot}
    except Exception as e:
        result['meta'] = {'error': str(e)}

    publish(host, port, 'ocr', result)


def run_worker(host: str = '127.0.0.1', port: int = 8765, stop_event: threading.Event = None):
    def cb(msg):
        _handle_message(msg, host, port)

    subscribe_forever(host, port, cb, stop_event=stop_event)


if __name__ == '__main__':
    print('Starting OCR worker and listening for capture messages...')
    try:
        run_worker()
    except KeyboardInterrupt:
        print('Worker stopped')
