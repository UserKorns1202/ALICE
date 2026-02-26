import importlib.util
import inspect
import sys
import asyncio
import traceback
from pathlib import Path


def load_module_from_path(path: str):
    p = Path(path)
    spec = importlib.util.spec_from_file_location(p.stem, str(p.resolve()))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_tests(module_path: str):
    # Ensure repo root is on sys.path so imports like `import tools` work
    repo_root = Path.cwd()
    sys.path.insert(0, str(repo_root))
    mod = load_module_from_path(module_path)
    funcs = [(name, fn) for name, fn in inspect.getmembers(mod, inspect.isfunction) if name.startswith('test_')]
    failed = 0
    total = 0
    for name, fn in funcs:
        total += 1
        try:
            if inspect.iscoroutinefunction(fn):
                asyncio.run(fn())
            else:
                fn()
            print(f"PASS {name}")
        except AssertionError as ae:
            failed += 1
            print(f"FAIL {name}: AssertionError: {ae}")
            traceback.print_exc()
        except Exception as e:
            failed += 1
            print(f"ERROR {name}: {e}")
            traceback.print_exc()

    print(f"\nRan {total} tests: {total-failed} passed, {failed} failed")
    return failed

if __name__ == '__main__':
    # module file path relative to repo
    mod_path = 'tests/test_tools.py'
    sys.exit(run_tests(mod_path))
