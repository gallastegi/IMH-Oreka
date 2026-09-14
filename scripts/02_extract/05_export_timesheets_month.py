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
    month_date_range,
    print_section,
)


YEAR = int(os.getenv("ODOO_YEAR", "2026"))
MONTH = int(os.getenv("ODOO_MONTH", "7"))


TIMESHEET_FIELDS = [
    "id",
    "date",
    "name",
    "employee_id",
    "user_id",
    "project_id",
    "task_id",
    "account_id",
    "unit_amount",
    "amount",
    "create_uid",
    "create_date",
    "write_uid",
    "write_date",
]


def main() -> None:
    client = OdooClient()
    client.authenticate()

    start, end = month_date_range(YEAR, MONTH)

    print_section("ExportaciÃ³n mensual de partes de horas")
    print(f"Periodo: {start} <= date < {end}")

    fields = valid_fields(client, "account.analytic.line", TIMESHEET_FIELDS)

    domain = [
        ["date", ">=", start],
        ["date", "<", end],
    ]

    # En algunas instalaciones account.analytic.line tambiÃ©n contiene lÃ­neas no-timesheet.
    # Si existen campos project_id/task_id/employee_id, esta exportaciÃ³n ayuda a filtrar despuÃ©s.
    records = client.search_read(
        model="account.analytic.line",
        domain=domain,
        fields=fields,
        limit=100000,
        order="date asc, id asc",
    )

    stem = f"timesheets_{YEAR}_{MONTH:02d}"
    save_json(OUTPUT_DIR / f"{stem}.json", records)
    save_csv(OUTPUT_DIR / f"{stem}.csv", records)

    print_section("Resultado")
    print(f"Registros exportados: {len(records)}")
    print(OUTPUT_DIR / f"{stem}.json")
    print(OUTPUT_DIR / f"{stem}.csv")


if __name__ == "__main__":
    main()

