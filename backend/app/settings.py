from __future__ import annotations
import os
import sys
from pathlib import Path

APP_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
SOURCE_ROOT = APP_ROOT
DEFAULT_MASTER_CSV = APP_ROOT / "data" / "demo.csv"
MASTER_FILENAME = Path("imported.csv")
APP_DATA_DIRECTORY_NAME = "InternalCXDashboardDemo"
_runtime_master_csv: Path | None = None

def load_env_file(path: Path | None = None) -> None:
    env_path = path or APP_ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

def master_csv_path() -> Path:
    if _runtime_master_csv is not None:
        return _runtime_master_csv
    load_env_file()
    persisted = persisted_master_csv_path()
    if persisted.exists():
        return persisted
    configured = os.environ.get("ICX_MASTER_CSV")
    return Path(configured).expanduser() if configured else DEFAULT_MASTER_CSV

def default_master_csv_path() -> Path:
    return DEFAULT_MASTER_CSV

def app_data_directory() -> Path:
    configured = os.environ.get("ICX_APP_DATA_DIR")
    if configured:
        return Path(configured).expanduser()
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / APP_DATA_DIRECTORY_NAME

def persisted_master_csv_path() -> Path:
    return app_data_directory() / MASTER_FILENAME.name

def clear_persisted_master_csv() -> None:
    persisted = persisted_master_csv_path()
    if persisted.exists():
        persisted.unlink()

def set_runtime_master_csv(path: str | Path | None) -> Path | None:
    global _runtime_master_csv
    _runtime_master_csv = None if path is None or not str(path).strip() else Path(path).expanduser()
    return _runtime_master_csv

def runtime_master_csv_path() -> Path | None:
    return _runtime_master_csv
