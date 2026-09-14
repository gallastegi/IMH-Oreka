from __future__ import annotations

import sys

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pandas as pd

from imh_oreka.odoo_common import OUTPUT_DIR, print_section


FORECAST_FILE = OUTPUT_DIR / "09_project_forecast.csv"

# Busca automÃ¡ticamente el Ãºltimo CSV ampliado de analytic lines.
ANALYTIC_CANDIDATES = sorted(OUTPUT_DIR.glob("11_analytic_lines_*_to_*.csv"))
ANALYTIC_FILE = ANALYTIC_CANDIDATES[-1] if ANALYTIC_CANDIDATES else None


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep=";", encoding="utf-8-sig")


def normalize_false(value):
    if pd.isna(value):
        return ""
    text = str(value)
    if text == "False":
        return ""
    return text


def build_forecast_detail() -> pd.DataFrame:
    if not FORECAST_FILE.exists():
        raise RuntimeError(f"No existe {FORECAST_FILE}. Ejecuta antes 09_export_project_forecast.py")

    df = read_csv(FORECAST_FILE)
    df["date_start"] = pd.to_datetime(df["date_start"], errors="coerce")
    df["urtea"] = df["date_start"].dt.year
    df["hilabete_zk"] = df["date_start"].dt.month

    # En los datos de test, effective_hours + remaining_hours cuadra con project.task.planned_hours.
    df["ordu_planifikatuak"] = df["effective_hours"].fillna(0) + df["remaining_hours"].fillna(0)
    df["ordu_forecast_effective"] = df["effective_hours"].fillna(0)
    df["ordu_forecast_remaining"] = df["remaining_hours"].fillna(0)

    out = pd.DataFrame({
        "iturria": "Odoo/project.forecast",
        "forecast_id": df.get("id"),
        "data": df["date_start"].dt.date.astype(str),
        "urtea": df["urtea"],
        "hilabete_zk": df["hilabete_zk"],
        "pertsona": df.get("employee_id", "").map(normalize_false),
        "erabiltzailea": df.get("user_id", "").map(normalize_false),
        "proiektua": df.get("project_id", "").map(normalize_false),
        "ataza": df.get("task_id", "").map(normalize_false),
        "ordu_planifikatuak": df["ordu_planifikatuak"],
        "ordu_forecast_effective": df["ordu_forecast_effective"],
        "ordu_forecast_remaining": df["ordu_forecast_remaining"],
        "oharra": df.get("name", ""),
    })

    return out


def build_real_detail() -> pd.DataFrame:
    if ANALYTIC_FILE is None or not ANALYTIC_FILE.exists():
        raise RuntimeError("No encuentro outputs/11_analytic_lines_*_to_*.csv. Ejecuta antes 11_export_analytic_lines_range.py")

    df = read_csv(ANALYTIC_FILE)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["urtea"] = df["date"].dt.year
    df["hilabete_zk"] = df["date"].dt.month

    out = pd.DataFrame({
        "iturria": "Odoo/account.analytic.line",
        "analytic_line_id": df.get("id"),
        "data": df["date"].dt.date.astype(str),
        "urtea": df["urtea"],
        "hilabete_zk": df["hilabete_zk"],
        "pertsona": df.get("employee_id", "").map(normalize_false),
        "erabiltzailea": df.get("user_id", "").map(normalize_false),
        "saila": df.get("department_id", "").map(normalize_false),
        "proiektua": df.get("project_id", "").map(normalize_false),
        "ataza": df.get("task_id", "").map(normalize_false),
        "kontu_analitikoa": df.get("account_id", "").map(normalize_false),
        "holiday_id": df.get("holiday_id", "").map(normalize_false),
        "ordu_errealak": df.get("unit_amount", 0).fillna(0),
        "amount": df.get("amount", 0).fillna(0),
        "sell_amount": df.get("sell_amount", 0).fillna(0),
        "oharra": df.get("name", ""),
    })

    return out


def main() -> None:
    print_section("ConstrucciÃ³n PRC-01 karga v0")

    forecast_detail = build_forecast_detail()
    real_detail = build_real_detail()

    forecast_path = OUTPUT_DIR / "12_prc01_planifikazioa_forecast_detail.csv"
    real_path = OUTPUT_DIR / "12_prc01_errealak_detail.csv"

    forecast_detail.to_csv(forecast_path, sep=";", encoding="utf-8-sig", index=False)
    real_detail.to_csv(real_path, sep=";", encoding="utf-8-sig", index=False)

    plan_month = (
        forecast_detail
        .groupby(["urtea", "hilabete_zk", "pertsona", "proiektua", "ataza"], dropna=False, as_index=False)
        .agg(
            ordu_planifikatuak=("ordu_planifikatuak", "sum"),
            forecast_lerroak=("forecast_id", "size"),
        )
    )

    real_month = (
        real_detail
        .groupby(["urtea", "hilabete_zk", "pertsona", "proiektua", "ataza"], dropna=False, as_index=False)
        .agg(
            ordu_errealak=("ordu_errealak", "sum"),
            analytic_lerroak=("analytic_line_id", "size"),
        )
    )

    monthly = plan_month.merge(
        real_month,
        how="outer",
        on=["urtea", "hilabete_zk", "pertsona", "proiektua", "ataza"],
    )

    monthly["ordu_planifikatuak"] = monthly["ordu_planifikatuak"].fillna(0)
    monthly["ordu_errealak"] = monthly["ordu_errealak"].fillna(0)
    monthly["balantzea"] = monthly["ordu_planifikatuak"] - monthly["ordu_errealak"]
    monthly["forecast_lerroak"] = monthly["forecast_lerroak"].fillna(0).astype(int)
    monthly["analytic_lerroak"] = monthly["analytic_lerroak"].fillna(0).astype(int)

    monthly = monthly.sort_values(["urtea", "hilabete_zk", "pertsona", "proiektua", "ataza"])

    monthly_path = OUTPUT_DIR / "12_prc01_karga_hilekoa_v0.csv"
    monthly.to_csv(monthly_path, sep=";", encoding="utf-8-sig", index=False)

    print(f"Forecast detalle: {len(forecast_detail)} filas")
    print(f"Reales detalle: {len(real_detail)} filas")
    print(f"Resumen mensual: {len(monthly)} filas")
    print()
    print(forecast_path)
    print(real_path)
    print(monthly_path)

    print_section("Primeras filas resumen")
    print(monthly.head(30).to_string(index=False))


if __name__ == "__main__":
    main()

