# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: Python JSON-RPC sidecar for Electron."""
from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

SPECDIR = Path(SPECPATH).resolve()
ROOT = SPECDIR.parent if SPECDIR.name == "desktop" else SPECDIR

datas = [
    (str(ROOT / "version.txt"), "."),
    (str(ROOT / "KSGoperacii.csv"), "."),
]
datas += collect_data_files("certifi")

hiddenimports = [
    "bridge",
    "bridge.handlers",
    "config_store",
    "report_profiles",
    "excel_io",
    "export_reports",
    "lor_analysis",
    "ksg_analysis",
    "ops_analysis",
    "paths",
    "updater",
    "changelog",
    "gui.ui_theme",
    "gui.helpers",
    "openpyxl",
    "certifi",
    "pandas",
    "numpy",
]
# pandas / openpyxl internals often need a few extras on Windows
hiddenimports += collect_submodules("openpyxl")

a = Analysis(
    [str(ROOT / "bridge" / "cli.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(SPECDIR / "pyi_rth_utf8.py")],
    excludes=[
        "matplotlib",
        "ttkbootstrap",
        "tkinterdnd2",
        "PIL",
        "pytest",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AnalizIstoriiBackend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # no console flash; stderr still piped by Electron
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AnalizIstoriiBackend",
)
