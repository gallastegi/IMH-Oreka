from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from imh_oreka.odoo_common import OdooClient, OUTPUT_DIR, save_json, save_csv, valid_fields, print_section


FIELDS = [
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
    "create_date",
    "write_date",
]


def search_read_with_context(client: OdooClient, model: str, domain, fields, limit=200000, order="id asc", context=None):
    uid = client.ensure_auth()
    return client.models.execute_kw(
        client.db,
        uid,
        client.password,
        model,
        "search_read",
        [domain],
        {
            "fields": fields,
            "limit": limit,
            "order": order,
            "context": context or {},
        },
    )


def main() -> None:
    client = OdooClient()
    client.authenticate()

    print_section("ExportaciÃ³n project.task con active_test=False")

    fields = valid_fields(client, "project.task", FIELDS)

    active_records = client.search_read(
        "project.task",
        domain=[],
        fields=fields,
        limit=200000,
        order="id asc",
    )

    all_records = search_read_with_context(
        client,
        "project.task",
        domain=[],
        fields=fields,
        limit=200000,
        order="id asc",
        context={"active_test": False},
    )

    save_json(OUTPUT_DIR / "10_project_task_planning_active.json", active_records)
    save_csv(OUTPUT_DIR / "10_project_task_planning_active.csv", active_records)

    save_json(OUTPUT_DIR / "10_project_task_planning_all.json", all_records)
    save_csv(OUTPUT_DIR / "10_project_task_planning_all.csv", all_records)

    print(f"Tareas activas: {len(active_records)}")
    print(f"Tareas activas + inactivas: {len(all_records)}")
    print(OUTPUT_DIR / "10_project_task_planning_all.csv")


if __name__ == "__main__":
    main()

