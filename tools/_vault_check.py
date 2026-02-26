import os
vault = r"C:\Users\troyk\Documents\Personal"
mds = []
for root, _, files in os.walk(vault):
    for f in files:
        if f.lower().endswith('.md'):
            mds.append(os.path.join(root, f))
print('count', len(mds))
for p in mds[:20]:
    print(p)
