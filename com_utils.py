"""Small helpers for safe COM initialization on Windows.

Usage:
    from com_utils import com_init
    with com_init():
        shell = win32com.client.Dispatch("WScript.Shell")
        # use shell, then del shell

This ensures `pythoncom.CoInitialize()` is called on enter and
`pythoncom.CoUninitialize()` on exit, reducing destructor races.
"""
from contextlib import contextmanager
import sys

@contextmanager
def com_init():
    """Context manager to initialize/uninitialize COM on the current thread.

    Safe to call even if pythoncom isn't available; in that case it's a no-op.
    """
    if sys.platform != "win32":
        yield
        return

    try:
        import pythoncom
    except Exception:
        # If pythoncom isn't available, behave as no-op
        yield
        return

    try:
        pythoncom.CoInitialize()
    except Exception:
        # best-effort; continue
        pass
    try:
        yield
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass
