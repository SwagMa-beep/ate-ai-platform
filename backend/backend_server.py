"""Packaged FastAPI backend entry point for the desktop app."""
from __future__ import annotations

import argparse
import multiprocessing
import os
import sys
from pathlib import Path

import uvicorn


def _backend_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _load_dotenv_if_present(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def main() -> None:
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser(description="ATE AI Platform backend server")
    parser.add_argument("--host", default=os.environ.get("ATE_BACKEND_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("ATE_BACKEND_PORT", "18080")))
    parser.add_argument("--data-dir", default=os.environ.get("ATE_DATA_DIR", ""))
    args = parser.parse_args()

    backend_dir = _backend_dir()
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    _load_dotenv_if_present(backend_dir / ".env")
    if getattr(sys, "frozen", False):
        _load_dotenv_if_present(Path(getattr(sys, "_MEIPASS", backend_dir)) / ".env")

    if args.data_dir:
        data_dir = Path(args.data_dir).resolve()
        os.environ.setdefault("ATE_BASE_DIR", str(data_dir.parent))
        os.environ.setdefault("DATA_DIR", str(data_dir))
        os.environ.setdefault("UPLOAD_DIR", str(data_dir / "uploads"))
        os.environ.setdefault("PROCESSED_DIR", str(data_dir / "processed"))
        os.environ.setdefault("RAW_DIR", str(data_dir / "raw"))
        os.environ.setdefault("LOG_DIR", str(data_dir / "logs"))

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
