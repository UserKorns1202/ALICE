import py_compile,glob
files=glob.glob('VRGL/*.py')
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print('OK',f)
    except Exception as e:
        print('ERR',f,e)
