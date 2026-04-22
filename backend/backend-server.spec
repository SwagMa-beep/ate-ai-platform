# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


datas = []
env_file = Path(".env")
if env_file.exists():
    datas.append((str(env_file), "."))

hiddenimports = [
    "app.main",
    "multipart",
    "python_multipart",
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.protocols.websockets.wsproto_impl",
]

excludes = [
    "Cython",
    "IPython",
    "PyQt5",
    "PyQt6",
    "PySide2",
    "PySide6",
    "altair",
    "awscrt",
    "boto3",
    "botocore",
    "bokeh",
    "cv2",
    "dask",
    "distributed",
    "datashader",
    "docutils",
    "fsspec",
    "h5py",
    "holoviews",
    "hvplot",
    "jupyter",
    "jupyter_client",
    "jupyter_core",
    "llvmlite",
    "matplotlib",
    "mypy",
    "numba",
    "notebook",
    "panel",
    "plotly",
    "pyarrow",
    "scipy",
    "seaborn",
    "sklearn",
    "sphinx",
    "streamlit",
    "tables",
    "torch",
    "tensorflow",
    "tkinter",
    "win32com",
    "zmq",
]


a = Analysis(
    ["backend_server.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="backend-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
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
    name="backend-server",
)
