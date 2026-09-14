from __future__ import annotations

import sys

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pandas as pd

from imh_oreka.odoo_common import DATA_PROCESSED_DIR, DATA_REPORTS_DIR, print_section


def read_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, sep=";", encoding="utf-8-sig")


def section(lines: list[str], title: str) -> None:
    lines.append("")
    lines.append("=" * 80)
    lines.append(title)
    lines.append("=" * 80)


def top_lines(df: pd.DataFrame, group: str, value: str, n: int = 20) -> str:
    if df.empty or group not in df.columns or value not in df.columns:
        return "(sin datos)"
    s = df.groupby(group)[value].sum().sort_values(ascending=False).head(n)
    return s.to_string()


def main() -> None:
    print_section("Informe de calidad PRC-01")

    plan = read_if_exists(DATA_PROCESSED_DIR / "12_prc01_v1_planifikazioa_forecast_detail.csv")
    real = read_if_exists(DATA_PROCESSED_DIR / "12_prc01_v1_errealak_detail.csv")
    all_monthly = read_if_exists(DATA_PROCESSED_DIR / "12_prc01_v1_all_monthly.csv")
    dep_monthly = read_if_exists(DATA_PROCESSED_DIR / "12_prc01_v1_department_scope_monthly.csv")
    emp_monthly = read_if_exists(DATA_PROCESSED_DIR / "12_prc01_v1_forecast_employee_scope_monthly.csv")
    proj_monthly = read_if_exists(DATA_PROCESSED_DIR / "12_prc01_v1_forecast_project_scope_monthly.csv")

    lines: list[str] = []

    section(lines, "Resumen general")
    if not plan.empty:
        lines.append(f"PlanificaciÃ³n: {len(plan)} lÃ­neas | {plan['ordu_planifikatuak'].sum():.2f} h | {plan['pertsona'].nunique()} personas | {plan['proiektua'].nunique()} proyectos")
        lines.append(f"FÃ³rmula detectada: {plan['formula_planifikazioa'].dropna().astype(str).iloc[0] if 'formula_planifikazioa' in plan.columns and len(plan) else 'N/D'}")
    else:
        lines.append("PlanificaciÃ³n: sin datos")

    if not real.empty:
        lines.append(f"Reales: {len(real)} lÃ­neas | {real['ordu_errealak'].sum():.2f} h | {real['pertsona'].nunique()} personas | {real['proiektua'].nunique()} proyectos")
    else:
        lines.append("Reales: sin datos")

    section(lines, "Top planificaciÃ³n por persona")
    lines.append(top_lines(plan, "pertsona", "ordu_planifikatuak"))

    section(lines, "Top real por persona")
    lines.append(top_lines(real, "pertsona", "ordu_errealak"))

    section(lines, "Top planificaciÃ³n por proyecto")
    lines.append(top_lines(plan, "proiektua", "ordu_planifikatuak"))

    section(lines, "Top real por proyecto")
    lines.append(top_lines(real, "proiektua", "ordu_errealak"))

    section(lines, "Top real por departamento")
    lines.append(top_lines(real, "saila", "ordu_errealak"))

    section(lines, "DiagnÃ³stico de alcances")
    for name, df in [
        ("all", all_monthly),
        ("department_scope", dep_monthly),
        ("forecast_employee_scope", emp_monthly),
        ("forecast_project_scope", proj_monthly),
    ]:
        if df.empty:
            lines.append(f"{name}: sin datos")
        else:
            lines.append(
                f"{name}: filas={len(df)} | plan={df['ordu_planifikatuak'].sum():.2f} h | "
                f"real={df['ordu_errealak'].sum():.2f} h | balance={df['balantzea'].sum():.2f} h | "
                f"personas={df['pertsona'].nunique()} | proyectos={df['proiektua'].nunique()}"
            )

    section(lines, "Avisos")
    if not plan.empty and not real.empty:
        plan_people = set(plan["pertsona"].dropna().astype(str))
        real_people = set(real["pertsona"].dropna().astype(str))
        only_real = sorted(real_people - plan_people)
        only_plan = sorted(plan_people - real_people)
        lines.append(f"Personas con horas reales pero sin forecast: {len(only_real)}")
        lines.append(", ".join(only_real[:50]) if only_real else "(ninguna)")
        lines.append("")
        lines.append(f"Personas con forecast pero sin horas reales: {len(only_plan)}")
        lines.append(", ".join(only_plan[:50]) if only_plan else "(ninguna)")

    output = "\n".join(lines)
    path = DATA_REPORTS_DIR / "14_prc01_quality_report.txt"
    path.write_text(output, encoding="utf-8")

    print(output)
    print()
    print(f"Guardado: {path}")


if __name__ == "__main__":
    main()

