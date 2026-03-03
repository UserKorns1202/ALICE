"""Capture publisher using `mss` to take local screenshots and publish
capture events with a `screenshot_path` for downstream OCR processing.

This publisher writes screenshots to `modules/ocr_service/tmp/` and emits a
JSON payload with the path so the OCR worker can read the image locally.
"""
import time
import os
import pathlib
import uuid
import tempfile
from typing import Optional

try:
    import mss
    import mss.tools
    from PIL import Image
    mss_available = True
except Exception:
    mss_available = False

from .bus import publish

TMP_DIR = pathlib.Path(__file__).parent / 'tmp'
TMP_DIR.mkdir(parents=True, exist_ok=True)


def capture_and_publish(host: str = '127.0.0.1', port: int = 8765, region: Optional[list] = None) -> dict:
    """Capture a region and publish a `capture` event referencing the image.

    `region` is [left, top, width, height]. If omitted, capture a small
    centered region of the primary monitor.
    """
    ts = time.time()
    if not mss_available:
        raise RuntimeError('mss or Pillow not available; install mss Pillow')

    with mss.mss() as sct:
        # `sct.monitors[0]` is the virtual full-screen that spans all monitors.
        # Use that by default so we capture the entire desktop across multiple
        # displays unless the caller provides an explicit region.
        monitors = sct.monitors
        mon = monitors[0]
        mon_left = int(mon.get('left', 0))
        mon_top = int(mon.get('top', 0))
        mon_w = int(mon.get('width'))
        mon_h = int(mon.get('height'))

        if region and len(region) == 4:
            left, top, w, h = region
        else:
            # Default: capture the entire virtual desktop (all monitors)
            left, top, w, h = mon_left, mon_top, mon_w, mon_h

        bbox = {'left': left, 'top': top, 'width': w, 'height': h}
        sct_img = sct.grab(bbox)

        # Use a safe unique temp filename (ensures new file each capture and
        # avoids any collision with OneDrive sync/locking). Write via
        # mss.tools.to_png to the generated path and close it immediately.
        tf = tempfile.NamedTemporaryFile(suffix='.png', dir=str(TMP_DIR), delete=False)
        out_path = pathlib.Path(tf.name)
        try:
            tf.close()
            mss.tools.to_png(sct_img.rgb, sct_img.size, output=str(out_path))
        except Exception:
            # If writing via NamedTemporaryFile path fails, fall back to
            # deterministic fallback name.
            try:
                fname = f"screenshot_{int(ts)}_{uuid.uuid4().hex[:6]}.png"
                out_path = TMP_DIR / fname
                mss.tools.to_png(sct_img.rgb, sct_img.size, output=str(out_path))
            except Exception:
                raise

    payload = {
        'ts': ts,
        'app': 'screen',
        'roi': [left, top, w, h],
        'hash': uuid.uuid4().hex,
        'tags': [],
        'screenshot_path': str(out_path)
    }

    # Cleanup old screenshots: keep only the N most recent files to limit disk use
    try:
        max_keep = 3
        files = list(TMP_DIR.glob('screenshot_*.png')) + list(TMP_DIR.glob('*.png'))
        # Deduplicate and only consider actual files
        files = [p for p in set(files) if p.exists()]
        if len(files) > max_keep:
            # sort by modification time ascending (oldest first)
            files_sorted = sorted(files, key=lambda p: p.stat().st_mtime)
            to_delete = files_sorted[0: max(0, len(files_sorted) - max_keep)]
            for p in to_delete:
                try:
                    p.unlink()
                    print(f"[ocr_capture] removed old screenshot: {p}")
                except Exception:
                    pass
    except Exception:
        pass
    # Debug: log the path of the newly created screenshot so we can observe
    # when captures occur and if the file changes between captures.
    try:
        print(f"[ocr_capture] saved screenshot: {out_path}")
    except Exception:
        pass
    try:
        publish(host, port, 'capture', payload)
    except Exception:
        try:
            print(f"[ocr_capture] publish to {host}:{port} failed, continuing")
        except Exception:
            pass
    return payload


if __name__ == '__main__':
    print('Capturing a region and publishing capture event...')
    p = capture_and_publish()
    print('Published:', p)
