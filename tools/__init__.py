"""Tools package initializer for ALICE.
Expose the registry module for simpler imports.
"""
try:
    from . import registry  # type: ignore
except Exception:
    # best-effort: leave package importable even if registry fails to load
    registry = None
