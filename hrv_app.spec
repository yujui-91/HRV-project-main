# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the HRV GUI app (方案A: `hrv_app` imported as a package).
#
# ONE-FILE build: everything (python DLL, _internal contents, mne/neo/bioread
# data) is packed into a single self-contained HRV_Analysis.exe — nothing
# separate to copy. At launch the bootloader unpacks to a temp dir, so the
# first start is slower than the one-dir build.
#
# Build:   pyinstaller hrv_app.spec --noconfirm
# Output:  dist/HRV_Analysis.exe   (single file)
#
# CONSOLE=False -> windowed release (no console window).

from PyInstaller.utils.hooks import collect_all, collect_submodules

CONSOLE = False

datas, binaries, hiddenimports = [], [], []

# Signal-file reader backends carry data files + lazily-imported submodules that
# PyInstaller's static analysis would otherwise miss.
for pkg in ('mne', 'neo', 'bioread'):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# The app package, plus modules imported inside functions (conditional/lazy).
hiddenimports += collect_submodules('hrv_app')
hiddenimports += [
    'hrv_app.core.report_generator',
    'hrv_app.core.report_generator_Eng',
    'hrv_app.core.rri_rpeak',
    'hrv_app.core.tff_reader',
    'hrv_app.core.edf_reader',
    'hrv_app.core.acq_reader',
    'hrv_app.core.abf_reader',
]

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Not used by the GUI (legacy/ only) or conflicting GUI toolkits.
    excludes=['tkinter', 'PyQt5', 'PySide2', 'PySide6', 'neurokit2', 'wfdb'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# One-file: bundle scripts + binaries + datas all into the EXE (no COLLECT).
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='HRV_Analysis',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=CONSOLE,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
