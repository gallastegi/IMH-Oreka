from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from imh_oreka.odoo_common import OdooClient, OUTPUT_DIR, save_json, save_csv, valid_fields, print_section


TASK_FIELDS = [
    "id",
    "name",
    "project_id",
    "parent_id",
    "child_ids",
    "user_id",
    "stage_id",
    "priority",
    "date_start",
    "date_deadline",
    "date_end",
    "planned_hours",
    "effective_hours",
    "remaining_hours",
    "total_hours_spent",
    "subtask_planned_hours",
    "subtask_effective_hours",
    "progress",
    "sale_line_id",
    "crm_lead_id",
    "tag_ids",
    "allow_timesheets",
    "active",
]


def main() -> None:
    client = OdooClient()
    client.authenticate()

    print_section("ExportaciÃ³n completa de planificaciÃ³n en project.task")

    fields = valid_fields(client, "project.task", TASK_FIELDS)

    records = client.search_read(
        "project.task",
        domain=[],
        fields=fields,
        limit=100000,
        order="id asc",
    )

    save_json(OUTPUT_DIR / "10_project_task_planning.json", records)
    save_csv(OUTPUT_DIR / "10_project_task_planning.csv", records)

    print(f"Tareas exportadas: {len(records)}")
    print(OUTPUT_DIR / "10_project_task_planning.csv")


if __name__ == "__main__":
    main()

