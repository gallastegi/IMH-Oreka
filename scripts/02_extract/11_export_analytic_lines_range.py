from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import os

from imh_oreka.odoo_common import (
    OdooClient,
    OUTPUT_DIR,
    save_json,
    save_csv,
    valid_fields,
    print_section,
)


DATE_FROM = os.getenv("ODOO_DATE_FROM", f"{os.getenv('ODOO_YEAR', '2026')}-01-01")
DATE_TO = os.getenv("ODOO_DATE_TO", f"{int(os.getenv('ODOO_YEAR', '2026')) + 1}-01-01")

FIELDS = [
    "id",
    "date",
    "name",
    "employee_id",
    "user_id",
    "department_id",
    "project_id",
    "task_id",
    "account_id",
    "holiday_id",
    "unit_amount",
    "amount",
    "sell_amount",
    "total_hour_price",
    "grant_hour_amount",
    "grant_hour_price",
    "is_granted",
    "so_line",
    "tag_ids",
    "create_date",
    "write_date",
]


def main() -> None:
    client = OdooClient()
    client.authenticate()

    print_section("ExportaciÃ³n ampliada de account.analytic.line")

    fields = valid_fields(client, "account.analytic.line", FIELDS)

    domain = [
        ["date", ">=", DATE_FROM],
        ["date", "<", DATE_TO],
    ]

    records = client.search_read(
        "account.analytic.line",
        domain=domain,
        fields=fields,
        limit=200000,
        order="date asc, id asc",
    )

    stem = f"11_analytic_lines_{DATE_FROM}_to_{DATE_TO}".replace(":", "-")
    save_json(OUTPUT_DIR / f"{stem}.json", records)
    save_csv(OUTPUT_DIR / f"{stem}.csv", records)

    print(f"Periodo: {DATE_FROM} <= date < {DATE_TO}")
    print(f"LÃ­neas exportadas: {len(records)}")
    print(OUTPUT_DIR / f"{stem}.csv")


if __name__ == "__main__":
    main()

