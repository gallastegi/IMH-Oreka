from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import os

from imh_oreka.odoo_common import OdooClient, OUTPUT_DIR, save_json, save_csv, valid_fields, print_section


DATE_FROM = os.getenv("ODOO_DATE_FROM", "")
DATE_TO = os.getenv("ODOO_DATE_TO", "")

FIELDS = [
    "id",
    "name",
    "display_name",
    "employee_id",
    "user_id",
    "project_id",
    "task_id",
    "date_start",
    "date_end",
    "quantity",
    "effective_hours",
    "remaining_hours",
    "unit_cost",
    "unit_price",
    "cost_subtotal",
    "price_subtotal",
    "grant_invoicing_hours",
    "grant_hour_price",
    "line_no",
    "line_type",
    "type_l",
    "task_type",
    "project_id_is_granted",
    "hours_warning",
    "create_date",
    "write_date",
]


def main() -> None:
    client = OdooClient()
    client.authenticate()

    model = "project.forecast"

    print_section("ExportaciÃ³n project.forecast v2")

    if not client.model_exists(model):
        print("El modelo project.forecast no es accesible o no existe.")
        return

    fields = valid_fields(client, model, FIELDS)

    domain = []
    if DATE_FROM:
        domain.append(["date_start", ">=", DATE_FROM])
    if DATE_TO:
        domain.append(["date_start", "<", DATE_TO])

    records = client.search_read(
        model=model,
        domain=domain,
        fields=fields,
        limit=200000,
        order="date_start asc, id asc",
    )

    save_json(OUTPUT_DIR / "09_project_forecast_v2.json", records)
    save_csv(OUTPUT_DIR / "09_project_forecast_v2.csv", records)

    print(f"Filtro: {DATE_FROM or '-inf'} <= date_start < {DATE_TO or '+inf'}")
    print(f"Registros exportados: {len(records)}")
    print(f"Campos exportados: {fields}")
    print(OUTPUT_DIR / "09_project_forecast_v2.csv")


if __name__ == "__main__":
    main()

