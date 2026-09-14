from __future__ import annotations

import os
import socket
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path


DEFAULT_ODOO_URL = "https://odoo.imh.eus"
DEFAULT_ODOO_DB = "imh"


def application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def choose_port(first: int = 8501, last: int = 8510) -> int:
    for port in range(first, last + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"No hay un puerto libre entre {first} y {last}.")


def open_browser_when_ready(port: int) -> None:
    url = f"http://localhost:{port}"
    for _ in range(120):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                webbrowser.open(url)
                return
        except OSError:
            time.sleep(0.25)


def show_startup_error(root: Path, error: BaseException) -> None:
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "launcher_error.log"
    log_path.write_text(traceback.format_exc(), encoding="utf-8")
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            0,
            f"No se ha podido iniciar IMH Oreka.\n\nDetalle: {error}\n\nLog: {log_path}",
            "IMH Oreka",
            0x10,
        )
    except Exception:
        pass


def main() -> int:
    root = application_root()
    app_script = root / "apps" / "streamlit" / "prc01_horas_imputadas.py"
    if not app_script.exists():
        raise FileNotFoundError(f"No se encuentra la aplicación: {app_script}")

    os.chdir(root)
    os.environ.setdefault("ODOO_URL", DEFAULT_ODOO_URL)
    os.environ.setdefault("ODOO_DB", DEFAULT_ODOO_DB)
    for relative in ("data/raw", "data/processed", "data/reports", "logs"):
        (root / relative).mkdir(parents=True, exist_ok=True)

    port = choose_port()
    threading.Thread(target=open_browser_when_ready, args=(port,), daemon=True).start()

    from streamlit.web import cli as streamlit_cli

    sys.argv = [
        "streamlit",
        "run",
        str(app_script),
        "--global.developmentMode=false",
        "--server.headless=true",
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--browser.gatherUsageStats=false",
    ]
    return int(streamlit_cli.main() or 0)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as exc:
        show_startup_error(application_root(), exc)
        raise
