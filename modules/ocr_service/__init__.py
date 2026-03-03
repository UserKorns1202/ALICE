"""OCR service package (lightweight pub/sub test stubs).

This package provides a minimal bus, a capture publisher stub, and a simple
OCR worker stub for local testing. These are scaffolds intended to be
non-intrusive and to validate the IPC/message flow before deeper integration
with `ALICE`.
"""

__all__ = [
    'bus',
    'capture',
    'ocr_worker',
]
