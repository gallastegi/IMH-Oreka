from __future__ import annotations

import json
import os
import xmlrpc.client
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

OUTPUT_DIR = ROOT_DIR / "data" / "reports"
OUTPUT_DIR.mkdir(exist_ok=True)

ODOO_URL = os.getenv("ODOO_URL", "").rstrip("/")
ODOO_DB = os.getenv("ODOO_DB", "")
ODOO_USER = os.getenv("ODOO_USER", "")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "")

MODELS = [
    "project.forecast",
    "project.task",
    "project.project",
    "account.analytic.line",
    "hr.employee",
    "hr.department",
    "hr.leave",
    "resource.calendar",
    "resource.calendar.attendance",
    "resource.calendar.leaves",
]


def print_section(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def save_json(path: Path, data) -> None:
    path.parent.mkdir(exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def main() -> None:
    if not ODOO_DB:
        raise RuntimeError("Falta ODOO_DB en .env")
    if not ODOO_USER or not ODOO_PASSWORD:
        raise RuntimeError("Faltan ODOO_USER u ODOO_PASSWORD en .env")

    print_section("Smoke test producciÃ³n Odoo")
    print(f"URL: {ODOO_URL}")
    print(f"DB: {ODOO_DB}")
    print(f"Usuario: {ODOO_USER}")

    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common", allow_none=True)
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object", allow_none=True)

    version = common.version()
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})

    if not uid:
        raise RuntimeError("No autentica. Revisa ODOO_DB, ODOO_USER y ODOO_PASSWORD.")

    print(f"AutenticaciÃ³n OK. UID={uid}")
    print(f"VersiÃ³n: {version}")

    summary = []

    for model in MODELS:
        print(f"Revisando {model}")
        item = {
            "model": model,
            "accessible": False,
            "count": None,
            "fields": None,
            "error": "",
        }

        try:
            count = models.execute_kw(
                ODOO_DB,
                uid,
                ODOO_PASSWORD,
                model,
                "search_count",
                [[]],
            )

            fields = models.execute_kw(
                ODOO_DB,
                uid,
                ODOO_PASSWORD,
                model,
                "fields_get",
                [],
                {"attributes": ["string", "type", "relation"]},
            )

            item["accessible"] = True
            item["count"] = count
            item["fields"] = len(fields)

            print(f"  OK registros={count}, campos={len(fields)}")

        except Exception as exc:
            item["error"] = str(exc)
            print(f"  ERROR {exc}")

        summary.append(item)

    save_json(
        OUTPUT_DIR / "13_prod_smoke_test.json",
        {
            "url": ODOO_URL,
            "db": ODOO_DB,
            "user": ODOO_USER,
            "uid": uid,
            "version": version,
            "models": summary,
        },
    )

    print_section("Guardado")
    print(OUTPUT_DIR / "13_prod_smoke_test.json")


if __name__ == "__main__":
    main()

