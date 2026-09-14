from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from imh_oreka.odoo_common import OdooClient, OUTPUT_DIR, save_json, save_csv, print_section


KEYWORDS = [
    "project",
    "task",
    "forecast",
    "planning",
    "plan",
    "analytic",
    "timesheet",
    "sheet",
    "employee",
    "department",
    "leave",
    "holiday",
    "calendar",
    "resource",
    "sale",
    "crm",
    "expense",
    "academic",
    "course",
    "faculty",
    "student",
    "contract",
    "booking",
    "reservation",
    "formakuntza",
    "prestaketa",
    "karga",
]


def contains_keyword(text: str) -> bool:
    t = (text or "").lower()
    return any(k.lower() in t for k in KEYWORDS)


def main() -> None:
    client = OdooClient()
    client.authenticate()

    print_section("Descubrimiento de modelos instalados")

    model_fields = ["id", "model", "name", "state", "transient"]
    models = client.search_read(
        "ir.model",
        domain=[],
        fields=model_fields,
        limit=100000,
        order="model asc",
    )

    filtered_models = [
        m for m in models
        if contains_keyword(m.get("model", "")) or contains_keyword(m.get("name", ""))
    ]

    save_json(OUTPUT_DIR / "07_all_ir_models.json", models)
    save_csv(OUTPUT_DIR / "07_all_ir_models.csv", models)
    save_json(OUTPUT_DIR / "07_candidate_ir_models.json", filtered_models)
    save_csv(OUTPUT_DIR / "07_candidate_ir_models.csv", filtered_models)

    print(f"Modelos totales: {len(models)}")
    print(f"Modelos candidatos: {len(filtered_models)}")

    print_section("Descubrimiento de mÃ³dulos instalados")

    module_fields = ["id", "name", "shortdesc", "state", "latest_version", "installed_version"]
    modules = client.search_read(
        "ir.module.module",
        domain=[["state", "=", "installed"]],
        fields=module_fields,
        limit=100000,
        order="name asc",
    )

    filtered_modules = [
        m for m in modules
        if contains_keyword(m.get("name", "")) or contains_keyword(m.get("shortdesc", ""))
    ]

    save_json(OUTPUT_DIR / "07_installed_modules.json", modules)
    save_csv(OUTPUT_DIR / "07_installed_modules.csv", modules)
    save_json(OUTPUT_DIR / "07_candidate_installed_modules.json", filtered_modules)
    save_csv(OUTPUT_DIR / "07_candidate_installed_modules.csv", filtered_modules)

    print(f"MÃ³dulos instalados: {len(modules)}")
    print(f"MÃ³dulos candidatos: {len(filtered_modules)}")

    print_section("Descubrimiento de campos candidatos")

    field_fields = [
        "id",
        "model",
        "name",
        "field_description",
        "ttype",
        "relation",
        "state",
        "store",
        "readonly",
        "required",
    ]

    domain = [
        "|", "|", "|", "|", "|",
        ["model", "ilike", "project"],
        ["model", "ilike", "analytic"],
        ["model", "ilike", "forecast"],
        ["model", "ilike", "planning"],
        ["model", "ilike", "employee"],
        ["model", "ilike", "leave"],
    ]

    fields = client.search_read(
        "ir.model.fields",
        domain=domain,
        fields=field_fields,
        limit=100000,
        order="model asc, name asc",
    )

    filtered_fields = [
        f for f in fields
        if (
            contains_keyword(f.get("model", ""))
            or contains_keyword(f.get("name", ""))
            or contains_keyword(f.get("field_description", ""))
            or contains_keyword(f.get("relation", ""))
        )
    ]

    save_json(OUTPUT_DIR / "07_candidate_ir_model_fields.json", filtered_fields)
    save_csv(OUTPUT_DIR / "07_candidate_ir_model_fields.csv", filtered_fields)

    print(f"Campos candidatos: {len(filtered_fields)}")

    print_section("Archivos generados")
    for name in [
        "07_candidate_ir_models.csv",
        "07_candidate_installed_modules.csv",
        "07_candidate_ir_model_fields.csv",
    ]:
        print(OUTPUT_DIR / name)


if __name__ == "__main__":
    main()

