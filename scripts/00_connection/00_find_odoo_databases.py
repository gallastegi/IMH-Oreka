from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
import xmlrpc.client
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

OUTPUT_DIR = ROOT_DIR / "data" / "reports"
OUTPUT_DIR.mkdir(exist_ok=True)

ODOO_URL = os.getenv("ODOO_URL", "").rstrip("/")


def print_section(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def save_json(path: Path, data) -> None:
    path.parent.mkdir(exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def try_xmlrpc_db_list(url: str):
    endpoint = f"{url}/xmlrpc/2/db"
    result = {
        "method": "xmlrpc",
        "endpoint": endpoint,
        "ok": False,
        "databases": [],
        "error": "",
    }

    try:
        proxy = xmlrpc.client.ServerProxy(endpoint, allow_none=True)
        dbs = proxy.list()
        result["ok"] = True
        result["databases"] = dbs
    except Exception as exc:
        result["error"] = str(exc)

    return result


def try_json_db_list(url: str):
    endpoint = f"{url}/web/database/list"
    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": "call",
        "params": {},
        "id": 1,
    }).encode("utf-8")

    result = {
        "method": "jsonrpc",
        "endpoint": endpoint,
        "ok": False,
        "databases": [],
        "raw": "",
        "error": "",
    }

    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            result["raw"] = raw[:2000]
            data = json.loads(raw)

            if "result" in data:
                result["ok"] = True
                result["databases"] = data["result"]
            elif "error" in data:
                result["error"] = str(data["error"])
            else:
                result["error"] = "Respuesta JSON inesperada"

    except Exception as exc:
        result["error"] = str(exc)

    return result


def main() -> None:
    print_section("BÃºsqueda de bases de datos Odoo")
    print(f"URL base: {ODOO_URL}")

    results = []

    for url in [ODOO_URL]:
        print_section(f"Probando XML-RPC database list: {url}")
        xml_result = try_xmlrpc_db_list(url)
        results.append(xml_result)

        if xml_result["ok"]:
            print("OK")
            print(xml_result["databases"])
        else:
            print("No disponible")
            print(xml_result["error"])

        print_section(f"Probando JSON /web/database/list: {url}")
        json_result = try_json_db_list(url)
        results.append(json_result)

        if json_result["ok"]:
            print("OK")
            print(json_result["databases"])
        else:
            print("No disponible")
            print(json_result["error"])

    save_json(OUTPUT_DIR / "00_find_odoo_databases.json", results)

    print_section("Resultado")
    found = []
    for r in results:
        if r.get("ok") and r.get("databases"):
            found.extend(r["databases"])

    found = sorted(set(found))

    if found:
        print("Bases encontradas:")
        for db in found:
            print(f"- {db}")
    else:
        print("No se han podido listar bases de datos.")
        print("Esto suele pasar si Odoo tiene list_db desactivado o si la ruta estÃ¡ protegida.")
        print("Siguiente paso: probar candidatos con 00_try_database_candidates.py o pedir el nombre a IT/Digital5.")

    print()
    print(f"Guardado: {OUTPUT_DIR / '00_find_odoo_databases.json'}")


if __name__ == "__main__":
    main()

