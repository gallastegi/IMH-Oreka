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


def top(df: pd.DataFrame, group: str, value: str, n: int = 30) -> str:
    if df.empty or group not in df.columns or value not in df.columns:
        return "(sin datos)"
    return df.groupby(group)[value].sum().sort_values(ascending=False).head(n).to_string()


def monthly_summary(path_name: str) -> str:
    df = read_if_exists(DATA_PROCESSED_DIR / path_name)
    if df.empty:
        return f"{path_name}: sin datos"
    return (
        f"{path_name}: filas={len(df)} | "
        f"plan={df['ordu_planifikatuak'].sum():.2f} h | "
        f"real={df['ordu_errealak'].sum():.2f} h | "
        f"balance={df['balantzea'].sum():.2f} h | "
        f"personas={df['pertsona'].nunique()} | "
        f"proyectos={df['proiektua'].nunique()}"
    )


def main() -> None:
    print_section("Informe de alcance PRC-01")

    plan = read_if_exists(DATA_PROCESSED_DIR / "12_prc01_v2_planifikazioa_forecast_detail.csv")
    real = read_if_exists(DATA_PROCESSED_DIR / "12_prc01_v2_errealak_detail.csv")

    lines: list[str] = []

    section(lines, "Resumen de ficheros")
    lines.append(f"PlanificaciÃ³n forecast: {len(plan)} filas | {plan['ordu_planifikatuak'].sum() if not plan.empty else 0:.2f} h | {plan['pertsona'].nunique() if not plan.empty else 0} personas")
    lines.append(f"Horas reales: {len(real)} filas | {real['ordu_errealak'].sum() if not real.empty else 0:.2f} h | {real['pertsona'].nunique() if not real.empty else 0} personas")

    section(lines, "ResÃºmenes mensuales")
    for filename in [
        "12_prc01_v2_all_monthly.csv",
        "12_prc01_v2_department_scope_monthly.csv",
        "12_prc01_v2_team_scope_monthly.csv",
        "12_prc01_v2_forecast_employee_scope_monthly.csv",
    ]:
        lines.append(monthly_summary(filename))

    section(lines, "Top planificaciÃ³n por persona")
    lines.append(top(plan, "pertsona", "ordu_planifikatuak"))

    section(lines, "Top real por persona")
    lines.append(top(real, "pertsona", "ordu_errealak"))

    section(lines, "Top real por departamento")
    lines.append(top(real, "saila", "ordu_errealak"))

    section(lines, "Personas con reales pero sin forecast")
    if not plan.empty and not real.empty:
        plan_people = set(plan["pertsona"].dropna().astype(str))
        real_people = set(real["pertsona"].dropna().astype(str))
        only_real = sorted(real_people - plan_people)
        lines.append(f"Total: {len(only_real)}")
        lines.extend(only_real[:100])
    else:
        lines.append("(sin datos)")

    section(lines, "Personas con forecast pero sin reales")
    if not plan.empty and not real.empty:
        plan_people = set(plan["pertsona"].dropna().astype(str))
        real_people = set(real["pertsona"].dropna().astype(str))
        only_plan = sorted(plan_people - real_people)
        lines.append(f"Total: {len(only_plan)}")
        lines.extend(only_plan[:100])
    else:
        lines.append("(sin datos)")

    output = "\n".join(lines)
    path = DATA_REPORTS_DIR / "15_prc01_scope_report.txt"
    path.write_text(output, encoding="utf-8")
    print(output)
    print()
    print(f"Guardado: {path}")


if __name__ == "__main__":
    main()

