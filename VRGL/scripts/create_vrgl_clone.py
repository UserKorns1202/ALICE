"""
Create a VRGL clone of the project using dependency list.
Copies required files into a new folder `VRGL/` next to ALICE, renames ALICE.py -> VRGL.py,
and applies simple edits to remove model swapping and keep VRGL TTS voice.
"""
import os, json, shutil, re

root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
with open(os.path.join(root, 'scripts', 'vrgl_dependency_list.json'), 'r', encoding='utf-8') as f:
    deps = json.load(f)

dest = os.path.join(root, 'VRGL')
if not os.path.exists(dest):
    os.makedirs(dest)

copied = []
skipped = []

for rel in deps:
    src = os.path.join(root, rel)
    if not os.path.exists(src):
        skipped.append((rel, 'missing'))
        continue
    # destination filename: ALICE.py -> VRGL.py
    if os.path.normpath(rel).lower() == 'alice.py':
        dstname = 'VRGL.py'
    else:
        dstname = os.path.basename(rel)
    dst = os.path.join(dest, dstname)
    # read and possibly modify
    try:
        text = open(src, 'r', encoding='utf-8').read()
    except Exception:
        # binary or unreadable, copy raw
        shutil.copy2(src, dst)
        copied.append(rel)
        continue
    if os.path.normpath(rel).lower() == 'alice.py':
        # Replace aiModel assignment to be fixed to 'vrgl'
        text = re.sub(r"aiModel\s*=\s*['\"][^'\"]+['\"]", "aiModel = \"vrgl\"", text)
        # Remove the voice-selection block marked by comment and replace with fixed voice
        text = re.sub(r"# Set a preferred Piper voice filename based on model[\s\S]*?\n\s*\n", "# Set a preferred Piper voice filename for VRGL\n    current_tts_voice = 'en_US-danny-low.onnx'\n\n", text, count=1)
        # Optionally, drop any AMICA references (already removed upstream), also change header mentions of ALICE -> VRGL
        text = text.replace('ALICE', 'VRGL')
    # write
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(text)
    copied.append(rel)

# Copy scripts folder and helper scripts into VRGL/scripts
scripts_src = os.path.join(root, 'scripts')
if os.path.exists(scripts_src):
    scripts_dst = os.path.join(dest, 'scripts')
    if not os.path.exists(scripts_dst):
        shutil.copytree(scripts_src, scripts_dst)

# Summarize
report = {
    'copied': copied,
    'skipped': skipped,
    'destination': os.path.relpath(dest, root)
}
out = os.path.join(root, 'scripts', 'vrgl_clone_report.json')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=2)
print('Clone complete. Report:', out)
