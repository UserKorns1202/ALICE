# Quick parse tests for agents.parse_inline_edit and ALICE instr normalization
from agents import parse_inline_edit
import re

cases = [
    'plan and execute: edit thing.txt to say "VRGL"',
    'plan: edit thing.txt to say VRGL',
    'execute: edit /tmp/thing.txt to say "hello world"',
    'please edit thing.txt to say "VRGL"',
    'edit thing.txt to say VRGL',
    'plan and run: do something else',
]
for c in cases:
    print('IN:', c)
    print('PARSE:', parse_inline_edit(c))
    print('---')

# Also test ALICE normalization regex
norm = re.compile(r'^(?:plan\s+and\s+execute|plan\s+and\s+run|plan\s+and\s+execute:|plan\s+and\s+run:|plan\s*:|execute\s*:|run\s*:|plan\s+execute\s*:)?\s*', flags=re.I)
for c in cases:
    instr = re.sub(norm, '', c)
    print('NORM IN:', c, '->', instr)
