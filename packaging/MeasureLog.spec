# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller recipe for a single-file MeasureLog.exe.

Build from the project root:
    pyinstaller packaging/MeasureLog.spec --noconfirm

The result is dist/MeasureLog.exe - one file, no installer, no Python needed on
the machine that runs it.
"""

import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent
ICON = ROOT / "packaging" / "icon.ico"
ICON_PNG = ROOT / "packaging" / "icon.png"

block_cipher = None

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(path), ".") for path in (ICON, ICON_PNG) if path.exists()],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Nothing here is used by the app; excluding them keeps the .exe small.
    excludes=[
        "numpy", "pandas", "matplotlib", "scipy", "PIL", "IPython", "jupyter",
        "pytest", "setuptools", "pip", "wheel", "lib2to3", "pydoc_data",
        "test", "unittest", "distutils", "email.test", "tkinter.test",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="MeasureLog",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX compression is left off on purpose: it saves a few MB but is a common
    # trigger for antivirus false positives on freshly built executables.
    upx=False,
    runtime_tmpdir=None,
    console=False,          # a GUI app - no console window behind it
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON) if ICON.exists() else None,
    version=str(ROOT / "packaging" / "version_info.txt")
    if (ROOT / "packaging" / "version_info.txt").exists() and sys.platform == "win32"
    else None,
)
