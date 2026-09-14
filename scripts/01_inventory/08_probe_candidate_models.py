from __future__ import annotations

import sys

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
import pandas as pd

from imh_oreka.odoo_common import DATA_REPORTS_DIR, OdooClient, OUTPUT_DIR, print_section, safe_filename, save_csv, save_json


FALLBACK_MODELS = [
    "project.forecast",
    "project.sale.line.employee.map",
    "account.analytic.tag",
    "hr.contract",
    "contract.date",
    "academic.course",
    "academic.faculty",
    "calendar.event",
    "resource.calendar",
    "resource.calendar.attendance",
    "resource.calendar.leaves",
    "project.project",
    "project.task",
    "account.analytic.line",
]


def main() -> None:
    client = OdooClient()
    client.authenticate()

    print_section("Sondeo de modelos candidatos")

    candidate_file = OUTPUT_DIR / "07_candidate_ir_models.csv"
    candidate_models = []

    if candidate_file.exists():
        df = pd.read_csv(candidate_file, sep=";", encoding="utf-8-sig")
        if "model" in df.columns:
            candidate_models.extend(df["model"].dropna().astype(str).tolist())

    candidate_models.extend(FALLBACK_MODELS)
    candidate_models = sorted(set(candidate_models))

    summary = []

    for model_name in candidate_models:
        print(f"Sondeando: {model_name}")
        try:
            count = client.search_count(model_name, [])
            fields = client.fields_get(model_name)

            field_rows = []
            for field_name, meta in sorted(fields.items()):
                field_rows.append({
                    "model": model_name,
                    "field": field_name,
                    "label": meta.get("string", ""),
                    "type": meta.get("type", ""),
                    "relation": meta.get("relation", ""),
                    "store": meta.get("store", ""),
                    "readonly": meta.get("readonly", ""),
                    "required": meta.get("required", ""),
                    "help": meta.get("help", ""),
                })

            save_csv(OUTPUT_DIR / "08_model_fields" / f"{safe_filename(model_name)}.csv", field_rows)

            sample_fields = [r["field"] for r in field_rows[:]]
            preferred = [
                "id", "name", "display_name", "date", "date_start", "date_stop",
                "start_datetime", "end_datetime", "employee_id", "user_id",
                "project_id", "task_id", "parent_id", "child_ids",
                "planned_hours", "effective_hours", "remaining_hours",
                "allocated_hours", "unit_amount", "amount", "state", "stage_id",
            ]
            valid = [f for f in preferred if f in fields]
            if not valid:
                valid = ["id", "display_name"] if "display_name" in fields else ["id"]

            sample = client.search_read(
                model_name,
                domain=[],
                fields=valid,
                limit=20,
                order="id desc",
            )

            save_json(OUTPUT_DIR / "08_model_samples" / f"{safe_filename(model_name)}.json", sample)
            save_csv(OUTPUT_DIR / "08_model_samples" / f"{safe_filename(model_name)}.csv", sample)

            summary.append({
                "model": model_name,
                "accessible": True,
                "count": count,
                "fields": len(fields),
                "sample_fields": ", ".join(valid),
                "error": "",
            })

        except Exception as exc:
            summary.append({
                "model": model_name,
                "accessible": False,
                "count": "",
                "fields": "",
                "sample_fields": "",
                "error": str(exc),
            })

    save_csv(DATA_REPORTS_DIR / "08_candidate_models_probe_summary.csv", summary)

    print_section("Archivo generado")
    print(DATA_REPORTS_DIR / "08_candidate_models_probe_summary.csv")


if __name__ == "__main__":
    main()

