from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from imh_oreka.odoo_common import OdooClient, OUTPUT_DIR, save_json, save_csv, safe_filename, valid_fields, ODOO_LIMIT, print_section


SAMPLES = {
    "hr.employee": [
        "id",
        "name",
        "active",
        "user_id",
        "department_id",
        "resource_calendar_id",
        "parent_id",
        "work_email",
    ],
    "res.users": [
        "id",
        "name",
        "login",
        "active",
        "partner_id",
        "company_id",
    ],
    "project.project": [
        "id",
        "name",
        "active",
        "user_id",
        "partner_id",
        "date_start",
        "date",
        "allow_timesheets",
        "allocated_hours",
        "effective_hours",
    ],
    "project.task": [
        "id",
        "name",
        "active",
        "project_id",
        "parent_id",
        "child_ids",
        "user_ids",
        "user_id",
        "stage_id",
        "priority",
        "date_deadline",
        "planned_hours",
        "allocated_hours",
        "effective_hours",
        "remaining_hours",
        "total_hours_spent",
        "subtask_effective_hours",
    ],
    "account.analytic.line": [
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
    ],
    "hr.leave": [
        "id",
        "employee_id",
        "holiday_status_id",
        "date_from",
        "date_to",
        "number_of_days",
        "number_of_hours_display",
        "state",
    ],
    "hr.expense": [
        "id",
        "name",
        "employee_id",
        "date",
        "product_id",
        "total_amount",
        "state",
        "analytic_distribution",
    ],
    "planning.slot": [
        "id",
        "name",
        "employee_id",
        "user_id",
        "project_id",
        "task_id",
        "start_datetime",
        "end_datetime",
        "allocated_hours",
        "state",
        "role_id",
    ],
    "calendar.event": [
        "id",
        "name",
        "start",
        "stop",
        "duration",
        "user_id",
        "partner_ids",
        "res_model",
        "res_id",
    ],
}


def main() -> None:
    client = OdooClient()
    client.authenticate()

    print_section("Muestras de datos core")

    for model_name, requested_fields in SAMPLES.items():
        print(f"Exportando muestra: {model_name}")

        try:
            fields = valid_fields(client, model_name, requested_fields)
            records = client.search_read(
                model=model_name,
                domain=[],
                fields=fields,
                limit=ODOO_LIMIT,
                order="id desc",
            )

            stem = safe_filename(model_name)
            save_json(OUTPUT_DIR / "samples" / f"{stem}.json", records)
            save_csv(OUTPUT_DIR / "samples" / f"{stem}.csv", records)

            print(f"  OK: {len(records)} registros, {len(fields)} campos")

        except Exception as exc:
            error_data = [{"model": model_name, "error": str(exc)}]
            stem = safe_filename(model_name)
            save_json(OUTPUT_DIR / "samples" / f"{stem}_ERROR.json", error_data)
            print(f"  ERROR: {exc}")

    print_section("Carpeta de salida")
    print(OUTPUT_DIR / "samples")


if __name__ == "__main__":
    main()

