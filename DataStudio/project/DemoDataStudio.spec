# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

template_root = Path(SPECPATH).resolve().parents[1] / 'Templates'
template_files = [
    (str(path), str(Path('Templates') / path.relative_to(template_root).parent))
    for path in template_root.rglob('*') if path.is_file()
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=template_files,
    hiddenimports=['semopy', 'numdifftools', 'pyreadstat', 'PIL.Image', 'PIL.ImageFont',
                   'matplotlib.backends.backend_agg', 'scipy.optimize', 'scipy.linalg'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='DataStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
