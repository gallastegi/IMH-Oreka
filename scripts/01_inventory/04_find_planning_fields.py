from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import re

from imh_oreka.odoo_common import OdooClient, OUTPUT_DIR, save_json, save_csv, print_section


MODELS_TO_SCAN = [
    "project.project",
    "project.task",
    "account.analytic.line",
    "hr.employee",
    "hr.leave",
    "resource.calendar",
    "resource.calendar.attendance",
    "resource.calendar.leaves",
    "planning.slot",
    "calendar.event",
]

KEYWORDS = [
    "plan",
    "planned",
    "planning",
    "hour",
    "hours",
    "allocated",
    "allocation",
    "effective",
    "remaining",
    "spent",
    "time",
    "date",
    "deadline",
    "start",
    "end",
    "employee",
    "user",
    "project",
    "task",
    "parent",
    "child",
    "subtask",
    "analytic",
    "x_",
    "custom",
    "docencia",
    "formacion",
    "formakuntza",
    "orokor",
    "general",
    "karga",
    "carga",
]


def field_matches(field_name: str, meta: dict) -> bool:
    haystack = " ".join(
        str(x or "")
        for x in [
            field_name,
            meta.get("string"),
            meta.get("help"),
            meta.get("relation"),
            meta.get("type"),
        ]
    ).lower()

    return any(keyword.lower() in haystack for keyword in KEYWORDS)


def main() -> None:
    client = OdooClient()
    client.authenticate()

    print_section("BÃºsqueda de campos candidatos para planificaciÃ³n/carga")

    rows: list[dict] = []
    full: dict[str, dict] = {}

    for model_name in MODELS_TO_SCAN:
        print(f"Escaneando: {model_name}")

        try:
            fields = client.fields_get(model_name)
            full[model_name] = {}

            for field_name, meta in sorted(fields.items()):
                if field_matches(field_name, meta):
                    row = {
                        "model": model_name,
                        "field": field_name,
                        "label": meta.get("string", ""),
                        "type": meta.get("type", ""),
                        "relation": meta.get("relation", ""),
                        "required": meta.get("required", ""),
                        "readonly": meta.get("readonly", ""),
                        "store": meta.get("store", ""),
                        "help": meta.get("help", ""),
                    }
                    rows.append(row)
                    full[model_name][field_name] = meta

        except Exception as exc:
            rows.append(
                {
                    "model": model_name,
                    "field": "",
                    "label": "",
                    "type": "",
                    "relation": "",
                    "required": "",
                    "readonly": "",
                    "store": "",
                    "help": "",
                    "error": str(exc),
                }
            )

    save_json(OUTPUT_DIR / "planning_field_candidates.json", full)
    save_csv(OUTPUT_DIR / "planning_field_candidates.csv", rows)

    print_section("Archivos generados")
    print(OUTPUT_DIR / "planning_field_candidates.json")
    print(OUTPUT_DIR / "planning_field_candidates.csv")
    print(f"Campos candidatos encontrados: {len(rows)}")


if __name__ == "__main__":
    main()

