import os, sys
# Ensure workspace root is on sys.path so imports find top-level modules
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from discord_integration import _apply_strict_source_guard

# Case: response repeats source (should pass)
resp, fb = _apply_strict_source_guard('This is a test summary.', 'This is a test summary.')
print('case1 ->', resp, fb)
# Case: response contains an uppercase token not in source (single token) - should not trigger fallback
resp, fb = _apply_strict_source_guard('Report: STRANGE_EVENT occurred', 'strange_event occurred')
print('case2 ->', resp, fb)
# Case: response contains many uppercase tokens not in source - should trigger fallback
resp, fb = _apply_strict_source_guard('ALPHA BETA GAMMA unexpected', 'only alpha present')
print('case3 ->', resp, fb)
