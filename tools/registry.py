"""Simple tool registry for ALICE.

Registers Python callables as named tools and provides a safe call wrapper.
This is intentionally minimal and sync; adapt to async or RPC later.
"""
from __future__ import annotations
from typing import Callable, Any, Dict
import inspect

_TOOLS: Dict[str, Callable[..., Any]] = {}


def register(name: str, fn: Callable[..., Any]):
    """Register a tool by name. Overwrites existing entry if present."""
    if not callable(fn):
        raise TypeError("fn must be callable")
    _TOOLS[name] = fn


def unregister(name: str):
    _TOOLS.pop(name, None)


def list_tools() -> list:
    return list(_TOOLS.keys())


def call_tool(name: str, *args, **kwargs) -> dict:
    """Call a registered tool and return a standardized result dict.

    Returns: {"ok": bool, "result": Any, "error": str|None}
    """
    if name not in _TOOLS:
        return {"ok": False, "result": None, "error": f"Tool '{name}' not found"}
    fn = _TOOLS[name]
    try:
        sig = inspect.signature(fn)
        # Basic sanity: do not pass unexpected kwargs
        bound = sig.bind_partial(*args, **kwargs)
        res = fn(*bound.args, **bound.kwargs)
        return {"ok": True, "result": res, "error": None}
    except Exception as e:
        return {"ok": False, "result": None, "error": str(e)}


def _register_examples():
    # Keep a couple of tiny example tools for quick testing
    def echo(text: str):
        return text

    register("echo", echo)


_register_examples()
