from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from imh_oreka.odoo_common import DATA_REPORTS_DIR, ODOO_DB, ODOO_URL, ODOO_USER, OdooClient, print_section, save_json


def main() -> None:
    client = OdooClient()

    print_section("ConexiÃ³n Odoo")
    print(f"URL: {ODOO_URL}")
    print(f"DB: {ODOO_DB}")
    print(f"Usuario: {ODOO_USER}")

    version = client.version()
    uid = client.authenticate()

    print_section("Resultado")
    print(f"AutenticaciÃ³n correcta. UID: {uid}")
    print("VersiÃ³n:")
    print(version)

    save_json(
        DATA_REPORTS_DIR / "01_connection_test.json",
        {
            "url": ODOO_URL,
            "db": ODOO_DB,
            "user": ODOO_USER,
            "uid": uid,
            "version": version,
        },
    )

    print(f"\nGuardado: {DATA_REPORTS_DIR / '01_connection_test.json'}")


if __name__ == "__main__":
    main()

