"""Quick demo for the new inline edit flow using agents directly.

This doesn't start ALICE; it shows how an instruction like
  edit thing.txt to say "VRGL"
is parsed, resolved, and applied.
"""
import os
from agents import parse_inline_edit, FileEditor

instr = 'edit thing.txt to say "VRGL"'
print('Instruction:', instr)
parsed = parse_inline_edit(instr)
print('Parsed:', parsed)
if not parsed:
    print('No inline edit detected')
else:
    path = parsed['path']
    # Resolve in workspace (script dir)
    base = os.path.dirname(__file__)
    cand = os.path.join(base, path)
    if not os.path.exists(cand):
        print('File not found, creating at:', cand)
    fe = FileEditor()
    result = fe.apply_edit(cand, parsed['content'], dry_run=False, make_backup=True)
    print('Result:', result)
    if result.get('ok'):
        with open(cand,'r',encoding='utf-8') as f:
            print('File contents now:\n', f.read())
