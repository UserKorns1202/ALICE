"""
Analyze local Python module dependencies starting from ALICE.py.
Outputs a JSON list of required .py files (workspace relative).
"""
import ast, os, json, sys

start = 'ALICE.py'
root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
visited_modules = set()
visited_files = set()
local_files = {os.path.splitext(f)[0]: f for f in os.listdir(root) if f.endswith('.py')}
# include package dirs with __init__.py
for d in os.listdir(root):
    dp = os.path.join(root, d)
    if os.path.isdir(dp) and os.path.exists(os.path.join(dp, '__init__.py')):
        local_files[d] = os.path.join(d, '__init__.py')

sys.setrecursionlimit(10000)

def resolve_module_to_file(mod):
    # mod can be like pkg.module or module
    parts = mod.split('.')
    # try progressively
    for i in range(len(parts),0,-1):
        prefix = '.'.join(parts[:i])
        if prefix in local_files:
            rel = local_files[prefix]
            return os.path.normpath(os.path.join(root, rel))
    return None


def analyze_file(path):
    path = os.path.normpath(path)
    if path in visited_files:
        return
    visited_files.add(path)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            src = f.read()
    except Exception:
        return
    try:
        tree = ast.parse(src)
    except Exception:
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                mod = n.name
                fpath = resolve_module_to_file(mod)
                if fpath:
                    analyze_file(fpath)
        elif isinstance(node, ast.ImportFrom):
            if node.level != 0:
                # relative import; skip resolving
                continue
            if not node.module:
                continue
            mod = node.module
            fpath = resolve_module_to_file(mod)
            if fpath:
                analyze_file(fpath)

if __name__ == '__main__':
    start_path = os.path.join(root, start)
    if not os.path.exists(start_path):
        print('Start file not found:', start_path)
        sys.exit(2)
    analyze_file(start_path)
    # include the start file
    visited_files.add(os.path.normpath(start_path))
    rels = [os.path.relpath(p, root).replace('\\','/') for p in sorted(visited_files)]
    out = os.path.join(root, 'scripts', 'vrgl_dependency_list.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(rels, f, indent=2)
    print('Wrote', out)
