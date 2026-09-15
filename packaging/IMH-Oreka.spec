from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules


ROOT = Path(SPECPATH).resolve().parent

datas = [
    (str(ROOT / "apps"), "apps"),
    (str(ROOT / "config"), "config"),
    (str(ROOT / "scripts"), "scripts"),
    (str(ROOT / "data" / "planning"), "data/planning"),
]
binaries = []
hiddenimports = []
for package in ("streamlit", "plotly"):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

# The Streamlit entrypoint is shipped as data and imported at runtime, so
# PyInstaller cannot discover the application package through static analysis.
hiddenimports += collect_submodules("imh_oreka")

a = Analysis(
    [str(ROOT / "packaging" / "imh_oreka_launcher.py")],
    pathex=[str(ROOT), str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="IMH-Oreka",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory=".",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="IMH-Oreka",
)
