# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

root = Path(SPECPATH).resolve()
datas = []
for path in (root / 'VBAFUZZY_ONL').rglob('*.bas'):
    datas.append((str(path), str(path.relative_to(root).parent)))
for path in (root / 'VBA Library').rglob('*.bas'):
    datas.append((str(path), str(path.relative_to(root).parent)))
for path in (root / 'VBA Library').glob('*.txt'):
    datas.append((str(path), str(path.relative_to(root).parent)))
for rel in ('tools_spherical/main.py', 'tools_quantum/main.py', 'tools_neutrosophic/main.py'):
    path = root / rel
    datas.append((str(path), str(path.relative_to(root).parent)))

a = Analysis(
    ['main.py'], pathex=[str(root)], binaries=[], datas=datas,
    hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=[], noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='FuzzyStudio', debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False, disable_windowed_traceback=False,
)
