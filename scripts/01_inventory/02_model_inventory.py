from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from imh_oreka.odoo_common import DATA_REPORTS_DIR, OdooClient, OUTPUT_DIR, print_section, save_csv, save_json


MODELS_TO_CHECK = [
    # Base
    "res.users",
    "res.partner",
    "hr.employee",
    "hr.department",

    # Calendars / resources
    "resource.calendar",
    "resource.calendar.attendance",
    "resource.calendar.leaves",
    "calendar.event",

    # Projects / tasks
    "project.project",
    "project.task",
    "project.task.type",
    "project.tags",

    # Timesheets / analytic
    "account.analytic.line",
    "account.analytic.account",
    "account.analytic.plan",

    # Leaves
    "hr.leave",
    "hr.leave.type",
    "hr.leave.allocation",

    # Expenses
    "hr.expense",
    "hr.expense.sheet",

    # Planning / allocation candidates
    "planning.slot",
    "planning.role",

    # Sales / CRM candidates
    "crm.lead",
    "sale.order",
    "sale.order.line",

    # Reservations candidates. These may not exist depending on custom modules.
    "resource.booking",
    "resource.booking.type",
    "appointment.type",
]


def summarize_fields(model_name: str, fields: dict) -> list[dict]:
    rows = []
    for field_name, meta in sorted(fields.items()):
        rows.append(
            {
                "model": model_name,
                "field": field_name,
                "label": meta.get("string", ""),
                "type": meta.get("type", ""),
                "relation": meta.get("relation", ""),
                "required": meta.get("required", ""),
                "readonly": meta.get("readonly", ""),
                "store": meta.get("store", ""),
            }
        )
    return rows


def main() -> None:
    client = OdooClient()
    version = client.version()
    uid = client.authenticate()

    print_section("Inventario de modelos Odoo")
    print(f"UID: {uid}")
    print(f"VersiÃ³n: {version}")

    inventory = {
        "version": version,
        "models": {},
    }
    summary_rows: list[dict] = []

    for model_name in MODELS_TO_CHECK:
        print(f"Revisando: {model_name}")

        try:
            count = client.search_count(model_name, [])
            fields = client.fields_get(model_name)

            inventory["models"][model_name] = {
                "accessible": True,
                "count": count,
                "fields": fields,
            }

            summary_rows.append(
                {
                    "model": model_name,
                    "accessible": True,
                    "count": count,
                    "field": "",
                    "label": "",
                    "type": "",
                    "relation": "",
                    "required": "",
                    "readonly": "",
                    "store": "",
                    "error": "",
                }
            )
            summary_rows.extend(
                {
                    **row,
                    "accessible": True,
                    "count": count,
                    "error": "",
                }
                for row in summarize_fields(model_name, fields)
            )

        except Exception as exc:
            inventory["models"][model_name] = {
                "accessible": False,
                "error": str(exc),
            }
            summary_rows.append(
                {
                    "model": model_name,
                    "accessible": False,
                    "count": "",
                    "field": "",
                    "label": "",
                    "type": "",
                    "relation": "",
                    "required": "",
                    "readonly": "",
                    "store": "",
                    "error": str(exc),
                }
            )

    save_json(OUTPUT_DIR / "odoo_model_inventory.json", inventory)
    save_csv(DATA_REPORTS_DIR / "odoo_model_inventory_summary.csv", summary_rows)

    print_section("Archivos generados")
    print(OUTPUT_DIR / "odoo_model_inventory.json")
    print(DATA_REPORTS_DIR / "odoo_model_inventory_summary.csv")


if __name__ == "__main__":
    main()

