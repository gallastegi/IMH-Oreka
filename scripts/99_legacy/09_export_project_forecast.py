from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import os

from imh_oreka.odoo_common import OdooClient, OUTPUT_DIR, save_json, save_csv, valid_fields, print_section


YEAR = int(os.getenv("ODOO_YEAR", "2026"))
MONTH = int(os.getenv("ODOO_MONTH", "7"))

CANDIDATE_FIELDS = [
    "id",
    "name",
    "display_name",
    "project_id",
    "task_id",
    "employee_id",
    "user_id",
    "resource_id",
    "date_start",
    "date_stop",
    "start_datetime",
    "end_datetime",
    "allocated_hours",
    "planned_hours",
    "effective_hours",
    "remaining_hours",
    "unit_amount",
    "state",
    "company_id",
    "create_date",
    "write_date",
]


def main() -> None:
    client = OdooClient()
    client.authenticate()

    model = "project.forecast"

    print_section("ExportaciÃ³n project.forecast")

    if not client.model_exists(model):
        print("El modelo project.forecast no es accesible o no existe.")
        return

    fields = valid_fields(client, model, CANDIDATE_FIELDS)
    all_fields = client.fields_get(model)
    count = client.search_count(model, [])

    records = client.search_read(
        model=model,
        domain=[],
        fields=fields,
        limit=100000,
        order="id desc",
    )

    save_json(OUTPUT_DIR / "09_project_forecast_fields.json", all_fields)
    save_csv(OUTPUT_DIR / "09_project_forecast.csv", records)
    save_json(OUTPUT_DIR / "09_project_forecast.json", records)

    print(f"Registros project.forecast: {count}")
    print(f"Campos exportados: {fields}")
    print(OUTPUT_DIR / "09_project_forecast.csv")


if __name__ == "__main__":
    main()

