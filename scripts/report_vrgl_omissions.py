import os,json
root='.'
with open('scripts/vrgl_dependency_list.json') as f:
    deps=json.load(f)
pyfiles=[f for f in os.listdir(root) if f.endswith('.py')]
not_copied=[f for f in pyfiles if f not in deps]
print('Top-level .py files not copied:')
for f in sorted(not_copied): print(' -',f)
# list some large known files
for name in ['yolov3.weights','yolov3.cfg','yolov5s.pt','Amica','archived']:
    print(name, 'exists?', os.path.exists(name))
