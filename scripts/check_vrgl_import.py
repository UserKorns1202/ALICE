import sys
import traceback
from pathlib import Path

print('Python executable:', sys.executable)
print('sys.path:')
for p in sys.path:
    print('  ', p)

try:
    import VRGL.VRGL as vrgl
    print('\nImported VRGL.VRGL successfully')
    print('VRGL file:', getattr(vrgl, '__file__', None))
    # try calling query_vrgl if present
    q = getattr(vrgl, 'query_vrgl', None)
    print('query_vrgl callable:', callable(q))
except Exception:
    print('\nImport failed:')
    traceback.print_exc()
    # try alternative imports
    try:
        import VRGL as mod
        print('\nImported VRGL as module:', getattr(mod, '__file__', None))
    except Exception:
        print('\nFallback import VRGL failed:')
        traceback.print_exc()

# Print repo layout (top-level)
root = Path(__file__).resolve().parent.parent
print('\nRepository root:', root)
print('Top-level entries:')
for p in sorted(root.iterdir()):
    print('  ', p.name)
