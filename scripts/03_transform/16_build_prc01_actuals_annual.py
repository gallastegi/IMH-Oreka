from __future__ import annotations

import argparse
import os
import re
import unicodedata
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

DATA_RAW_DIR = ROOT_DIR / "data" / "raw"
DATA_PROCESSED_DIR = ROOT_DIR / "data" / "processed"
DATA_REPORTS_DIR = ROOT_DIR / "data" / "reports"
CLASSIFICATION_FILE = ROOT_DIR / "config" / "prc01_project_task_classification.csv"

DEPARTMENT_CONTAINS = os.getenv("PRC01_DEPARTMENT_CONTAINS", "").strip()
TEAM_PEOPLE = os.getenv("PRC01_TEAM_PEOPLE", "").strip()
EXCLUDE_PEOPLE = os.getenv("PRC01_EXCLUDE_PEOPLE", "").strip()

ALLOWED_GROUPS = {
    "Orokorrak",
    "Formakuntza",
    "Proiektuak",
    "Pendiente de clasificar",
}

CLASSIFICATION_COLUMNS = [
    "project_id",
    "project_name",
    "task_id",
    "task_name",
    "grupo_actividad",
    "subgrupo",
    "active",
    "review_status",
    "comment",
    "reviewed_by",
    "reviewed_at",
]


MONTH_NAMES_EU = {
    1: "Urtarrila",
    2: "Otsaila",
    3: "Martxoa",
    4: "Apirila",
    5: "Maiatza",
    6: "Ekaina",
    7: "Uztaila",
    8: "Abuztua",
    9: "Iraila",
    10: "Urria",
    11: "Azaroa",
    12: "Abendua",
}


def analytic_file_for_range(date_from: str, date_to: str) -> Path:
    return DATA_RAW_DIR / f"11_analytic_lines_{date_from}_to_{date_to}.csv"


def parse_range_from_filename(path: Path) -> tuple[str, str]:
    match = re.match(r"11_analytic_lines_(\d{4}-\d{2}-\d{2})_to_(\d{4}-\d{2}-\d{2})\.csv$", path.name)
    if not match:
        return "", ""
    return match.group(1), match.group(2)


def select_analytic_file(date_from: str | None = None, date_to: str | None = None) -> tuple[Path, str, str, str]:
    date_from = date_from or os.getenv("ODOO_DATE_FROM", "").strip()
    date_to = date_to or os.getenv("ODOO_DATE_TO", "").strip()

    if date_from or date_to:
        if not date_from or not date_to:
            raise RuntimeError("Debes indicar ambos valores: ODOO_DATE_FROM y ODOO_DATE_TO.")
        expected = analytic_file_for_range(date_from, date_to)
        if not expected.exists():
            raise RuntimeError(
                "No existe el raw esperado para el rango indicado: "
                f"{expected}. Ejecuta antes la descarga de horas reales para ese rango."
            )
        return expected, date_from, date_to, "explicit"

    candidates = sorted(DATA_RAW_DIR.glob("11_analytic_lines_*_to_*.csv"))
    if not candidates:
        raise RuntimeError(
            "No encuentro data/raw/11_analytic_lines_*_to_*.csv. "
            "Ejecuta antes 11_export_analytic_lines_range.py"
        )
    selected = candidates[-1]
    detected_from, detected_to = parse_range_from_filename(selected)
    print(
        "Aviso: no se ha indicado rango explicito. "
        f"Seleccion automatica: {selected}"
    )
    return selected, detected_from, detected_to, "auto"


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep=";", encoding="utf-8-sig")


def norm(value) -> str:
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


def normalize_key(value) -> str:
    return " ".join(norm(value).strip().split())


def normalize_text(value) -> str:
    text = normalize_key(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.casefold().split())


def ensure_classification_file() -> None:
    if CLASSIFICATION_FILE.exists():
        return
    CLASSIFICATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(columns=CLASSIFICATION_COLUMNS).to_csv(
        CLASSIFICATION_FILE,
        sep=";",
        encoding="utf-8-sig",
        index=False,
    )


def load_classification() -> pd.DataFrame:
    ensure_classification_file()
    classification = pd.read_csv(CLASSIFICATION_FILE, sep=";", encoding="utf-8-sig", dtype=str).fillna("")

    for column in CLASSIFICATION_COLUMNS:
        if column not in classification.columns:
            classification[column] = ""

    classification = classification[CLASSIFICATION_COLUMNS].copy()
    classification["active"] = classification["active"].astype(str).str.upper().isin(["TRUE", "1", "YES", "SI"])
    classification = classification[classification["active"]].copy()
    classification["grupo_actividad"] = classification["grupo_actividad"].where(
        classification["grupo_actividad"].isin(ALLOWED_GROUPS),
        "Pendiente de clasificar",
    )

    for column in ["project_id", "project_name", "task_id", "task_name"]:
        classification[column] = classification[column].map(normalize_key)

    return classification


def classification_maps(classification: pd.DataFrame) -> dict[str, dict]:
    maps: dict[str, dict] = {
        "task_exact_id": {},
        "project_id": {},
        "task_exact_name": {},
        "project_name": {},
    }

    for _, row in classification.iterrows():
        project_id = normalize_key(row.get("project_id", ""))
        task_id = normalize_key(row.get("task_id", ""))
        project_name = normalize_text(row.get("project_name", ""))
        task_name = normalize_text(row.get("task_name", ""))
        group = normalize_key(row.get("grupo_actividad", "")) or "Pendiente de clasificar"
        subgrupo = normalize_key(row.get("subgrupo", ""))
        value = (group, subgrupo)

        if task_id:
            maps["task_exact_id"][(project_id, task_id)] = value
        elif project_id:
            maps["project_id"][project_id] = value
        if task_name:
            maps["task_exact_name"][(project_name, task_name)] = value
        elif project_name:
            maps["project_name"][project_name] = value

    return maps


def classify_row(row: pd.Series, maps: dict[str, dict]) -> tuple[str, str, str, str, str]:
    project_id = normalize_key(row.get("project_id", ""))
    task_id = normalize_key(row.get("task_id", ""))
    project_name = normalize_text(row.get("project_name", ""))
    task_name = normalize_text(row.get("task_name", ""))

    if (project_id, task_id) in maps["task_exact_id"]:
        group, subgrupo = maps["task_exact_id"][(project_id, task_id)]
        return group, subgrupo, "task_exact_id", project_id, task_id
    if project_id in maps["project_id"]:
        group, subgrupo = maps["project_id"][project_id]
        return group, subgrupo, "project_id", project_id, ""
    if (project_name, task_name) in maps["task_exact_name"]:
        group, subgrupo = maps["task_exact_name"][(project_name, task_name)]
        return group, subgrupo, "task_exact_name", project_name, task_name
    if project_name in maps["project_name"]:
        group, subgrupo = maps["project_name"][project_name]
        return group, subgrupo, "project_name", project_name, ""
    return "Pendiente de clasificar", "", "pending", "", ""


def build_detail(
    df: pd.DataFrame,
    classification: pd.DataFrame,
    source_file: Path,
    source_date_from: str,
    source_date_to: str,
) -> pd.DataFrame:
    df = df.copy()

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["urtea"] = df["date"].dt.year
    df["hilabete_zk"] = df["date"].dt.month
    df["hilabetea"] = df["hilabete_zk"].map(MONTH_NAMES_EU)
    df["hilabete_ordena"] = df["hilabete_zk"]

    project_raw = df.get("project_id", "").map(norm)
    task_raw = df.get("task_id", "").map(norm)

    detail = pd.DataFrame({
        "source_file": source_file.name,
        "source_date_from": source_date_from,
        "source_date_to": source_date_to,
        "data": df["date"].dt.date.astype(str),
        "urtea": df["urtea"],
        "hilabete_zk": df["hilabete_zk"],
        "hilabetea": df["hilabetea"],
        "hilabete_ordena": df["hilabete_ordena"],
        "pertsona": df.get("employee_id", "").map(norm),
        "erabiltzailea": df.get("user_id", "").map(norm),
        "saila": df.get("department_id", "").map(norm),
        "project_id": project_raw,
        "project_name": project_raw,
        "task_id": task_raw,
        "task_name": task_raw,
        "proiektua": project_raw,
        "ataza": task_raw,
        "kontu_analitikoa": df.get("account_id", "").map(norm),
        "holiday_id": df.get("holiday_id", "").map(norm),
        "azalpena": df.get("name", "").map(norm),
        "ordu_errealak": pd.to_numeric(df.get("unit_amount", 0), errors="coerce").fillna(0),
        "amount": pd.to_numeric(df.get("amount", 0), errors="coerce").fillna(0),
        "sell_amount": pd.to_numeric(df.get("sell_amount", 0), errors="coerce").fillna(0),
    })

    detail["all_text"] = (
        detail["saila"] + " | "
        + detail["proiektua"] + " | "
        + detail["ataza"] + " | "
        + detail["kontu_analitikoa"] + " | "
        + detail["holiday_id"] + " | "
        + detail["azalpena"]
    )

    maps = classification_maps(classification)
    classified = detail.apply(lambda r: classify_row(r, maps), axis=1)
    detail["grupo_actividad"] = classified.map(lambda item: item[0])
    detail["subgrupo"] = classified.map(lambda item: item[1])
    detail["classification_source"] = classified.map(lambda item: item[2])
    detail["matched_project_key"] = classified.map(lambda item: item[3])
    detail["matched_task_key"] = classified.map(lambda item: item[4])

    # Nivel de anÃ¡lisis legible. Para el dashboard, proyecto + tarea evita barras imposibles de leer.
    detail["proiektua_ataza"] = detail["proiektua"].fillna("") + " / " + detail["ataza"].fillna("")
    detail["proiektua_ataza"] = detail["proiektua_ataza"].str.strip(" /")

    return detail


def save_unclassified_report(detail: pd.DataFrame) -> Path:
    DATA_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    pending = detail[detail["grupo_actividad"] == "Pendiente de clasificar"].copy()
    report_path = DATA_REPORTS_DIR / "prc01_unclassified_project_tasks.csv"

    if pending.empty:
        report = pd.DataFrame(
            columns=[
                "project_id",
                "project_name",
                "task_id",
                "task_name",
                "hours",
                "people_count",
                "first_date",
                "last_date",
                "suggested_group",
            ]
        )
    else:
        report = (
            pending.groupby(["project_id", "project_name", "task_id", "task_name"], dropna=False, as_index=False)
            .agg(
                hours=("ordu_errealak", "sum"),
                people_count=("pertsona", "nunique"),
                first_date=("data", "min"),
                last_date=("data", "max"),
            )
            .sort_values("hours", ascending=False)
        )
        report["suggested_group"] = ""

    report.to_csv(report_path, sep=";", encoding="utf-8-sig", index=False)
    return report_path


def save_classification_diagnostics(detail: pd.DataFrame) -> Path:
    DATA_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_REPORTS_DIR / "prc01_classification_diagnostics.csv"
    diagnostics = (
        detail.groupby(
            [
                "project_id",
                "project_name",
                "task_id",
                "task_name",
                "classification_source",
                "grupo_actividad",
                "matched_project_key",
                "matched_task_key",
            ],
            dropna=False,
            as_index=False,
        )
        .agg(hours=("ordu_errealak", "sum"))
        .sort_values("hours", ascending=False)
    )
    diagnostics["pending"] = diagnostics["grupo_actividad"].eq("Pendiente de clasificar")
    diagnostics.to_csv(path, sep=";", encoding="utf-8-sig", index=False)
    return path


def apply_scope(detail: pd.DataFrame) -> pd.DataFrame:
    scoped = detail.copy()

    if DEPARTMENT_CONTAINS:
        scoped = scoped[contains_any(scoped["saila"], DEPARTMENT_CONTAINS)].copy()

    if TEAM_PEOPLE:
        scoped = scoped[contains_any(scoped["pertsona"], TEAM_PEOPLE)].copy()

    if EXCLUDE_PEOPLE:
        scoped = scoped[exclude_any(scoped["pertsona"], EXCLUDE_PEOPLE)].copy()

    return scoped


def save_outputs(detail: pd.DataFrame) -> dict[str, object]:
    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    detail_path = DATA_PROCESSED_DIR / "16_prc01_actuals_annual_detail.csv"
    detail.to_csv(detail_path, sep=";", encoding="utf-8-sig", index=False)

    keys_base = ["urtea", "hilabete_zk", "hilabetea", "hilabete_ordena"]

    month_group = (
        detail.groupby(keys_base + ["grupo_actividad"], as_index=False)
        .agg(ordu_errealak=("ordu_errealak", "sum"), lerroak=("ordu_errealak", "size"))
        .sort_values(["urtea", "hilabete_ordena", "grupo_actividad"])
    )
    month_group.to_csv(DATA_PROCESSED_DIR / "16_prc01_actuals_annual_month_group.csv", sep=";", encoding="utf-8-sig", index=False)

    month_project = (
        detail.groupby(keys_base + ["grupo_actividad", "project_id", "project_name", "proiektua"], as_index=False)
        .agg(ordu_errealak=("ordu_errealak", "sum"), lerroak=("ordu_errealak", "size"))
        .sort_values(["urtea", "hilabete_ordena", "grupo_actividad", "ordu_errealak"], ascending=[True, True, True, False])
    )
    month_project.to_csv(DATA_PROCESSED_DIR / "16_prc01_actuals_annual_month_project.csv", sep=";", encoding="utf-8-sig", index=False)

    month_task = (
        detail.groupby(keys_base + ["grupo_actividad", "project_id", "project_name", "task_id", "task_name", "proiektua", "ataza", "proiektua_ataza"], as_index=False)
        .agg(ordu_errealak=("ordu_errealak", "sum"), lerroak=("ordu_errealak", "size"))
        .sort_values(["urtea", "hilabete_ordena", "grupo_actividad", "ordu_errealak"], ascending=[True, True, True, False])
    )
    month_task.to_csv(DATA_PROCESSED_DIR / "16_prc01_actuals_annual_month_task.csv", sep=";", encoding="utf-8-sig", index=False)

    review = (
        detail.groupby(["grupo_actividad", "subgrupo", "project_id", "project_name", "task_id", "task_name", "proiektua", "ataza"], as_index=False)
        .agg(ordu_errealak=("ordu_errealak", "sum"), lerroak=("ordu_errealak", "size"))
        .sort_values(["grupo_actividad", "ordu_errealak"], ascending=[True, False])
    )
    review.to_csv(DATA_PROCESSED_DIR / "16_prc01_classification_review.csv", sep=";", encoding="utf-8-sig", index=False)
    unclassified_path = save_unclassified_report(detail)
    diagnostics_path = save_classification_diagnostics(detail)

    print("Archivos generados:")
    print(detail_path)
    print(DATA_PROCESSED_DIR / "16_prc01_actuals_annual_month_group.csv")
    print(DATA_PROCESSED_DIR / "16_prc01_actuals_annual_month_project.csv")
    print(DATA_PROCESSED_DIR / "16_prc01_actuals_annual_month_task.csv")
    print(DATA_PROCESSED_DIR / "16_prc01_classification_review.csv")
    print(unclassified_path)
    print(diagnostics_path)

    return {
        "detail_path": str(detail_path),
        "unclassified_path": str(unclassified_path),
        "diagnostics_path": str(diagnostics_path),
        "rows": int(len(detail)),
        "hours": float(detail["ordu_errealak"].sum()),
        "pending_rows": int((detail["grupo_actividad"] == "Pendiente de clasificar").sum()),
        "source_file": str(detail["source_file"].iloc[0]) if not detail.empty else "",
        "source_date_from": str(detail["source_date_from"].iloc[0]) if not detail.empty else "",
        "source_date_to": str(detail["source_date_to"].iloc[0]) if not detail.empty else "",
    }


def run_transform(date_from: str | None = None, date_to: str | None = None) -> dict[str, object]:
    analytic_file, source_date_from, source_date_to, selection_mode = select_analytic_file(date_from, date_to)
    print(f"Usando fichero: {analytic_file}")
    print(f"Modo seleccion raw: {selection_mode}")
    if source_date_from or source_date_to:
        print(f"Rango fuente: {source_date_from} -> {source_date_to}")

    classification = load_classification()
    raw = read_csv(analytic_file)
    detail = build_detail(raw, classification, analytic_file, source_date_from, source_date_to)
    scoped = apply_scope(detail)

    print(f"LÃ­neas origen: {len(raw)}")
    print(f"LÃ­neas tras alcance: {len(scoped)}")
    print(f"Horas tras alcance: {scoped['ordu_errealak'].sum():.2f}")
    print("Horas por grupo:")
    print(scoped.groupby("grupo_actividad")["ordu_errealak"].sum().sort_values(ascending=False).to_string())

    summary = save_outputs(scoped)
    summary["selection_mode"] = selection_mode
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Construye dataset anual PRC-01 desde raw de horas Odoo.")
    parser.add_argument("--date-from", dest="date_from", default=None, help="Fecha inicio YYYY-MM-DD")
    parser.add_argument("--date-to", dest="date_to", default=None, help="Fecha fin YYYY-MM-DD")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_transform(date_from=args.date_from, date_to=args.date_to)


if __name__ == "__main__":
    main()

