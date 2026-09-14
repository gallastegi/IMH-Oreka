from __future__ import annotations

import sys

import json
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pandas as pd

from imh_oreka.odoo_common import DATA_PROCESSED_DIR, DATA_RAW_DIR, print_section


YEAR = int(os.getenv("ODOO_YEAR", "2026"))
MONTH = int(os.getenv("ODOO_MONTH", "7"))


def many2one_name(value):
    if isinstance(value, list) and len(value) == 2:
        return value[1]
    return ""


def many2one_id(value):
    if isinstance(value, list) and len(value) == 2:
        return value[0]
    return None


def main() -> None:
    input_file = DATA_RAW_DIR / f"timesheets_{YEAR}_{MONTH:02d}.json"

    print_section("Vista previa de carga mensual desde partes")
    print(f"Entrada: {input_file}")

    if not input_file.exists():
        raise RuntimeError(
            f"No existe {input_file}. Ejecuta antes: python 05_export_timesheets_month.py"
        )

    with input_file.open("r", encoding="utf-8") as f:
        records = json.load(f)

    if not records:
        print("No hay registros para el periodo indicado.")
        return

    rows = []
    for r in records:
        rows.append(
            {
                "urtea": YEAR,
                "hilabete_zk": MONTH,
                "data": r.get("date"),
                "pertsona_id": many2one_id(r.get("employee_id")),
                "pertsona_izena": many2one_name(r.get("employee_id")) or many2one_name(r.get("user_id")),
                "erabiltzailea": many2one_name(r.get("user_id")),
                "proiektua_id": many2one_id(r.get("project_id")),
                "proiektua": many2one_name(r.get("project_id")),
                "ataza_id": many2one_id(r.get("task_id")),
                "ataza": many2one_name(r.get("task_id")),
                "kontu_analitikoa": many2one_name(r.get("account_id")),
                "ordu_errealak": float(r.get("unit_amount") or 0),
                "azalpena": r.get("name", ""),
                "iturria": "Odoo/account.analytic.line",
            }
        )

    df = pd.DataFrame(rows)

    detail_path = DATA_PROCESSED_DIR / f"karga_detail_preview_{YEAR}_{MONTH:02d}.csv"
    df.to_csv(detail_path, sep=";", index=False, encoding="utf-8-sig")

    grouped = (
        df.groupby(
            [
                "urtea",
                "hilabete_zk",
                "pertsona_id",
                "pertsona_izena",
                "proiektua_id",
                "proiektua",
                "ataza_id",
                "ataza",
            ],
            dropna=False,
            as_index=False,
        )
        .agg(
            ordu_errealak=("ordu_errealak", "sum"),
            lerro_kopurua=("ordu_errealak", "size"),
        )
        .sort_values(["pertsona_izena", "proiektua", "ataza"])
    )

    summary_path = DATA_PROCESSED_DIR / f"karga_month_preview_{YEAR}_{MONTH:02d}.csv"
    grouped.to_csv(summary_path, sep=";", index=False, encoding="utf-8-sig")

    print_section("Archivos generados")
    print(detail_path)
    print(summary_path)

    print_section("Resumen rÃ¡pido")
    print(grouped.head(30).to_string(index=False))


if __name__ == "__main__":
    main()

