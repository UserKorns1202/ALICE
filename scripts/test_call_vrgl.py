import importlib.util, traceback, sys
from pathlib import Path
repo = Path(__file__).resolve().parent.parent
import sys
# ensure repo root is on sys.path so local imports inside VRGL.py resolve
if str(repo) not in sys.path:
    sys.path.insert(0, str(repo))

spec = importlib.util.spec_from_file_location('_local_vrgl', repo / 'VRGL' / 'VRGL.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)  # type: ignore
print('Loaded:', getattr(mod, '__file__', None))
print('Has query_vrgl:', hasattr(mod, 'query_vrgl'))
try:
    print('Calling query_vrgl with timeout=5...')
    out = mod.query_vrgl('Say VRGL test.', timeout=5)
    print('Result preview:', repr(str(out)[:400]))
except Exception:
    print('Call raised:')
    traceback.print_exc()
