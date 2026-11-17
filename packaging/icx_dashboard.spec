# Build only the application and explicitly synthetic demo data.
from pathlib import Path
ROOT = Path(SPECPATH).resolve().parent
datas = [(str(ROOT / "frontend" / "dist"), "frontend/dist"), (str(ROOT / "data" / "demo.csv"), "data"), (str(ROOT / "data" / "schema.csv"), "data")]
a = Analysis([str(ROOT / "launcher.py")], pathex=[str(ROOT)], datas=datas, binaries=[], hiddenimports=["uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto", "uvicorn.protocols.websockets.auto", "uvicorn.lifespan.on"], hookspath=[], runtime_hooks=[], excludes=[])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Internal CX Dashboard", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="Internal CX Dashboard")
app = BUNDLE(coll, name="Internal CX Dashboard.app", bundle_identifier="local.icx.dashboard")
