from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def repository_text() -> str:
    excluded = {Path(__file__).resolve()}
    roots = [ROOT / "apps", ROOT / "config", ROOT / "data" / "planning", ROOT / "docs", ROOT / "scripts", ROOT / "src"]
    files = [ROOT / ".env.example", ROOT / "README.md", ROOT / "SECURITY.md"]
    for base in roots:
        if base.exists():
            files.extend(path for path in base.rglob("*") if path.is_file())
    chunks = []
    for path in files:
        if path.resolve() in excluded:
            continue
        try:
            chunks.append(path.read_text(encoding="utf-8-sig"))
        except UnicodeDecodeError:
            continue
    return "\n".join(chunks).lower()


def test_repository_has_no_known_private_environment_or_person_values() -> None:
    text = repository_text()
    forbidden = [
        "imh" + "_pro_020724",
        "beñat " + "gallastegi",
        "benat " + "gallastegi",
        "ander " + "elejaga",
        "iker " + "altuna",
    ]
    assert not [value for value in forbidden if value in text]


def test_approved_production_endpoint_is_the_builtin_default() -> None:
    common = (ROOT / "src" / "imh_oreka" / "odoo_common.py").read_text(encoding="utf-8-sig")
    assert 'DEFAULT_ODOO_URL = "https://odoo.imh.eus"' in common
    assert 'DEFAULT_ODOO_DB = "imh"' in common
    assert 'DEFAULT_ODOO_URL = "http://' not in common


def test_private_outputs_are_ignored_and_legacy_evidence_is_absent() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8-sig")
    for rule in [".env", "logs/", "docs/90_archive/", "data/raw/*", "data/processed/*", "data/reports/*", "config/*.local.csv"]:
        assert rule in gitignore
    assert not (ROOT / "docs" / "90_archive").exists()
