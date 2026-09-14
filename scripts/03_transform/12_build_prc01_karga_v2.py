from __future__ import annotations

import sys

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pandas as pd

from imh_oreka.odoo_common import DATA_PROCESSED_DIR, DATA_RAW_DIR, print_section


FORECAST_CANDIDATES = [
    DATA_RAW_DIR / "09_project_forecast_v3_SAFE.csv",
    DATA_RAW_DIR / "09_project_forecast_v2.csv",
    DATA_RAW_DIR / "09_project_forecast.csv",
]
FORECAST_FILE = next((p for p in FORECAST_CANDIDATES if p.exists()), None)

ANALYTIC_CANDIDATES = sorted(DATA_RAW_DIR.glob("11_analytic_lines_*_to_*.csv"))
ANALYTIC_FILE = ANALYTIC_CANDIDATES[-1] if ANALYTIC_CANDIDATES else None

DEPARTMENT_CONTAINS = os.getenv("PRC01_DEPARTMENT_CONTAINS", "").strip()
TEAM_PEOPLE = os.getenv("PRC01_TEAM_PEOPLE", "").strip()
EXCLUDE_PEOPLE = os.getenv("PRC01_EXCLUDE_PEOPLE", "").strip()


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep=";", encoding="utf-8-sig")


def norm_text(value):
    if pd.isna(value):
        return ""
    text = str(value)
    if text == "False":
        return ""
    return text


def contains_any(series: pd.Series, patterns: str) -> pd.Series:
    if not patterns:
        return pd.Series([True] * len(series), index=series.index)

    parts = [p.strip() for p in patterns.split("|") if p.strip()]
    if not parts:
        return pd.Series([True] * len(series), index=series.index)

    text = series.fillna("").astype(str)
    mask = pd.Series([False] * len(series), index=series.index)

    for p in parts:
        mask = mask | text.str.contains(p, case=False, regex=False, na=False)

    return mask


def exclude_any(series: pd.Series, patterns: str) -> pd.Series:
    if not patterns:
        return pd.Series([True] * len(series), index=series.index)
    return ~contains_any(series, patterns)


def build_forecast_detail() -> pd.DataFrame:
    if FORECAST_FILE is None:
        raise RuntimeError("No encuentro archivo project.forecast. Ejecuta 09_export_project_forecast_v3_SAFE.py")

    df = read_csv(FORECAST_FILE)
    df["date_start"] = pd.to_datetime(df["date_start"], errors="coerce")
    df["urtea"] = df["date_start"].dt.year
    df["hilabete_zk"] = df["date_start"].dt.month

    if "quantity" in df.columns:
        df["ordu_planifikatuak"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
        formula = "quantity"
    else:
        df["ordu_planifikatuak"] = (
            pd.to_numeric(df.get("effective_hours", 0), errors="coerce").fillna(0)
            + pd.to_numeric(df.get("remaining_hours", 0), errors="coerce").fillna(0)
        )
        formula = "effective_hours + remaining_hours"

    out = pd.DataFrame({
        "iturria": "Odoo/project.forecast",
        "formula_planifikazioa": formula,
        "forecast_id": df.get("id"),
        "data": df["date_start"].dt.date.astype(str),
        "urtea": df["urtea"],
        "hilabete_zk": df["hilabete_zk"],
        "pertsona": df.get("employee_id", "").map(norm_text),
        "erabiltzailea": df.get("user_id", "").map(norm_text),
        "proiektua": df.get("project_id", "").map(norm_text),
        "ataza": df.get("task_id", "").map(norm_text),
        "ordu_planifikatuak": df["ordu_planifikatuak"],
        "quantity": pd.to_numeric(df.get("quantity", 0), errors="coerce").fillna(0) if "quantity" in df.columns else 0,
        "effective_hours": pd.to_numeric(df.get("effective_hours", 0), errors="coerce").fillna(0),
        "remaining_hours": pd.to_numeric(df.get("remaining_hours", 0), errors="coerce").fillna(0),
        "oharra": df.get("name", ""),
    })

    out = out[exclude_any(out["pertsona"], EXCLUDE_PEOPLE)].copy()
    return out


def build_real_detail() -> pd.DataFrame:
    if ANALYTIC_FILE is None or not ANALYTIC_FILE.exists():
        raise RuntimeError("No encuentro data/raw/11_analytic_lines_*_to_*.csv. Ejecuta 11_export_analytic_lines_range.py")

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
        "pertsona": df.get("employee_id", "").map(norm_text),
        "erabiltzailea": df.get("user_id", "").map(norm_text),
        "saila": df.get("department_id", "").map(norm_text),
        "proiektua": df.get("project_id", "").map(norm_text),
        "ataza": df.get("task_id", "").map(norm_text),
        "kontu_analitikoa": df.get("account_id", "").map(norm_text),
        "holiday_id": df.get("holiday_id", "").map(norm_text),
        "ordu_errealak": pd.to_numeric(df.get("unit_amount", 0), errors="coerce").fillna(0),
        "amount": pd.to_numeric(df.get("amount", 0), errors="coerce").fillna(0),
        "sell_amount": pd.to_numeric(df.get("sell_amount", 0), errors="coerce").fillna(0),
        "oharra": df.get("name", ""),
    })

    out = out[exclude_any(out["pertsona"], EXCLUDE_PEOPLE)].copy()
    return out


def monthly_merge(plan_detail: pd.DataFrame, real_detail: pd.DataFrame) -> pd.DataFrame:
    keys = ["urtea", "hilabete_zk", "pertsona", "proiektua", "ataza"]

    plan_month = (
        plan_detail
        .groupby(keys, dropna=False, as_index=False)
        .agg(
            ordu_planifikatuak=("ordu_planifikatuak", "sum"),
            forecast_lerroak=("forecast_id", "size"),
        )
    )

    real_month = (
        real_detail
        .groupby(keys, dropna=False, as_index=False)
        .agg(
            ordu_errealak=("ordu_errealak", "sum"),
            analytic_lerroak=("analytic_line_id", "size"),
        )
    )

    monthly = plan_month.merge(real_month, how="outer", on=keys)
    monthly["ordu_planifikatuak"] = monthly["ordu_planifikatuak"].fillna(0)
    monthly["ordu_errealak"] = monthly["ordu_errealak"].fillna(0)
    monthly["balantzea"] = monthly["ordu_planifikatuak"] - monthly["ordu_errealak"]
    monthly["forecast_lerroak"] = monthly["forecast_lerroak"].fillna(0).astype(int)
    monthly["analytic_lerroak"] = monthly["analytic_lerroak"].fillna(0).astype(int)

    return monthly.sort_values(keys)


def save_scope(name: str, plan_detail: pd.DataFrame, real_detail: pd.DataFrame) -> None:
    monthly = monthly_merge(plan_detail, real_detail)
    path = DATA_PROCESSED_DIR / f"12_prc01_v2_{name}_monthly.csv"
    monthly.to_csv(path, sep=";", encoding="utf-8-sig", index=False)

    print(
        f"{name}: plan_rows={len(plan_detail)} | real_rows={len(real_detail)} | "
        f"monthly_rows={len(monthly)} | plan={plan_detail['ordu_planifikatuak'].sum() if len(plan_detail) else 0:.2f} h | "
        f"real={real_detail['ordu_errealak'].sum() if len(real_detail) else 0:.2f} h | "
        f"people_plan={plan_detail['pertsona'].nunique() if len(plan_detail) else 0} | "
        f"people_real={real_detail['pertsona'].nunique() if len(real_detail) else 0}"
    )
    print(path)


def main() -> None:
    print_section("ConstrucciÃ³n PRC-01 karga v2")

    plan = build_forecast_detail()
    real = build_real_detail()

    plan_path = DATA_PROCESSED_DIR / "12_prc01_v2_planifikazioa_forecast_detail.csv"
    real_path = DATA_PROCESSED_DIR / "12_prc01_v2_errealak_detail.csv"
    plan.to_csv(plan_path, sep=";", encoding="utf-8-sig", index=False)
    real.to_csv(real_path, sep=";", encoding="utf-8-sig", index=False)

    print(f"Forecast usado: {FORECAST_FILE}")
    print(f"Analytic usado: {ANALYTIC_FILE}")
    print(f"Exclusiones: {EXCLUDE_PEOPLE or '(ninguna)'}")
    print()
    print(f"PlanificaciÃ³n detalle: {len(plan)} filas | {plan['ordu_planifikatuak'].sum():.2f} h | {plan['pertsona'].nunique()} personas")
    print(f"Reales detalle: {len(real)} filas | {real['ordu_errealak'].sum():.2f} h | {real['pertsona'].nunique()} personas")
    print(plan_path)
    print(real_path)

    print_section("ResÃºmenes por alcance")

    save_scope("all", plan, real)

    if DEPARTMENT_CONTAINS:
        real_dep = real[contains_any(real["saila"], DEPARTMENT_CONTAINS)].copy()
        dep_people = set(real_dep["pertsona"].dropna().astype(str))
        plan_dep = plan[plan["pertsona"].isin(dep_people)].copy()
        save_scope("department_scope", plan_dep, real_dep)

    if TEAM_PEOPLE:
        plan_team = plan[contains_any(plan["pertsona"], TEAM_PEOPLE)].copy()
        real_team = real[contains_any(real["pertsona"], TEAM_PEOPLE)].copy()
        save_scope("team_scope", plan_team, real_team)

    forecast_people = set(plan["pertsona"].dropna().astype(str))
    real_forecast_people = real[real["pertsona"].isin(forecast_people)].copy()
    save_scope("forecast_employee_scope", plan, real_forecast_people)


if __name__ == "__main__":
    main()

