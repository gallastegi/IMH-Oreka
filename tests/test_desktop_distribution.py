from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER_PATH = ROOT / "packaging" / "imh_oreka_launcher.py"


def load_launcher():
    spec = importlib.util.spec_from_file_location("imh_oreka_launcher", LAUNCHER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_launcher_has_approved_odoo_defaults() -> None:
    launcher = load_launcher()
    assert launcher.DEFAULT_ODOO_URL == "https://odoo.imh.eus"
    assert launcher.DEFAULT_ODOO_DB == "imh"


def test_launcher_selects_an_available_local_port() -> None:
    launcher = load_launcher()
    port = launcher.choose_port(18501, 18510)
    assert 18501 <= port <= 18510


def test_windows_build_definition_is_versioned() -> None:
    assert (ROOT / "packaging" / "IMH-Oreka.spec").exists()
    assert (ROOT / "build_windows.ps1").exists()
