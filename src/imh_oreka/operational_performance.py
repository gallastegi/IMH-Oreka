from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_PROCESSED_DIR = ROOT_DIR / "data" / "processed"
DATA_REPORTS_DIR = ROOT_DIR / "data" / "reports"
CONFIG_DIR = ROOT_DIR / "config"

PLANNING_DETAIL_FILE = DATA_PROCESSED_DIR / "17_prc01_planning_detail.csv"
ACTUALS_DETAIL_FILE = DATA_PROCESSED_DIR / "16_prc01_actuals_annual_detail.csv"
OPERATIONAL_DETAIL_FILE = DATA_PROCESSED_DIR / "18_prc01_operational_performance_detail.csv"

MANAGEMENT_UNITS_FILE = CONFIG_DIR / "prc01_management_units.csv"
WORK_NATURES_FILE = CONFIG_DIR / "prc01_work_natures.csv"
MANAGEMENT_RULES_FILE = CONFIG_DIR / "prc01_management_classification_rules.csv"

DIAGNOSTICS_FILE = DATA_REPORTS_DIR / "prc01_operational_performance_diagnostics.csv"
MATCH_CONFLICTS_FILE = DATA_REPORTS_DIR / "prc01_operational_match_conflicts.csv"
UNPLANNED_ACTUALS_FILE = DATA_REPORTS_DIR / "prc01_operational_unplanned_actuals.csv"
UNEXECUTED_PLANNING_FILE = DATA_REPORTS_DIR / "prc01_operational_unexecuted_planning.csv"
OVERCONSUMPTION_FILE = DATA_REPORTS_DIR / "prc01_operational_overconsumption.csv"
PEOPLE_COVERAGE_FILE = DATA_REPORTS_DIR / "prc01_operational_people_coverage.csv"
PENDING_CLASSIFICATION_FILE = DATA_REPORTS_DIR / "prc01_operational_pending_classification.csv"

MATCH_EXACT = "exact_employee_project_task_period"
MATCH_PROJECT = "employee_project_period"
MATCH_TASK = "employee_task_period"
MATCH_PROJECT_ONLY = "project_only_ambiguous"
MATCH_CONFLICT = "multiple_forecast_conflict"
MATCH_NONE = "no_planning_match"

LOAD_OK = "OK"
LOAD_RISK = "Riesgo"
LOAD_OVERLOAD = "Sobrecarga"
LOAD_NO_AVAILABILITY = "Sin disponibilidad"

PROJECT_ON_TRACK = "En linea"
PROJECT_ATTENTION = "Atencion"
PROJECT_DEVIATED = "Desviado"
PROJECT_CRITICAL = "Critico"
PROJECT_UNPLANNED = "Sin planificacion"
PROJECT_UNEXECUTED = "Sin ejecucion"
PROJECT_NO_DATA = "Sin datos suficientes"

OUTPUT_COLUMNS = [
    "year",
    "month",
    "period_start",
    "period_end",
    "person_key",
    "employee_id",
    "person_name",
    "department_name",
    "internal_group",
    "subdepartment",
    "project_id",
    "project_name",
    "task_id",
    "task_name",
    "unidad_destino",
    "unidad_destino_label",
    "naturaleza_trabajo",
    "naturaleza_trabajo_label",
    "grupo_gestion",
    "planned_minutes",
    "planned_hours",
    "actual_minutes",
    "actual_hours",
    "actual_minutes_with_planning",
    "actual_hours_with_planning",
    "actual_minutes_without_planning",
    "actual_hours_without_planning",
    "planned_minutes_not_executed",
    "planned_hours_not_executed",
    "deviation_minutes",
    "deviation_hours",
    "deviation_pct",
    "planning_coverage_pct",
    "planning_execution_pct",
    "available_hours",
    "occupation_planned_pct",
    "occupation_actual_pct",
    "projects_count",
    "tasks_count",
    "match_quality",
    "match_status",
    "classification_status",
    "source_planning_rows",
    "source_actual_rows",
    "generated_at",
]


@dataclass(frozen=True)
class BuildResult:
    detail: pd.DataFrame
    actual_matches: pd.DataFrame
    conflicts: pd.DataFrame
    diagnostics: dict[str, Any]


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if text.casefold() in {"nan", "none", "false", "nat"}:
        return ""
    return " ".join(text.split())


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", clean_text(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.casefold().replace("-", " ").split())


def normalize_id(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    if text.endswith(".0"):
        head = text[:-2]
        if head.isdigit():
            return head
    return text


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype=str).fillna("")


def _active_config(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "active" not in df.columns:
        return df.copy()
    return df[df["active"].astype(str).map(lambda value: normalize_text(value) in {"true", "1", "si", "yes", "y"})].copy()


def _label_lookup(df: pd.DataFrame, key_column: str, label_column: str = "label_es") -> dict[str, str]:
    if df.empty or key_column not in df.columns:
        return {}
    label_col = label_column if label_column in df.columns else key_column
    return {clean_text(row.get(key_column, "")): clean_text(row.get(label_col, "")) for _, row in df.iterrows()}


def _row_matches_management_rule(row: pd.Series, rule: pd.Series) -> bool:
    checks = [
        ("project_contains", ["project_name"]),
        ("task_contains", ["task_name"]),
        ("department_contains", ["department_name", "subdepartment", "saila"]),
        ("person_contains", ["person_name", "pertsona"]),
    ]
    has_condition = False
    for rule_column, data_columns in checks:
        needle = normalize_text(rule.get(rule_column, ""))
        if not needle:
            continue
        has_condition = True
        haystack = " ".join(normalize_text(row.get(column, "")) for column in data_columns)
        if needle not in haystack:
            return False
    return has_condition


def apply_management_classification(df: pd.DataFrame, config_dir: Path = CONFIG_DIR) -> pd.DataFrame:
    """Apply the PRC-01 management classification rules used by the dashboard."""
    if df.empty:
        return df.copy()
    units = _active_config(read_csv(config_dir / "prc01_management_units.csv"))
    natures = _active_config(read_csv(config_dir / "prc01_work_natures.csv"))
    rules = _active_config(read_csv(config_dir / "prc01_management_classification_rules.csv"))
    if not rules.empty and "priority" in rules.columns:
        rules["_priority"] = pd.to_numeric(rules["priority"], errors="coerce").fillna(999999).astype(int)
        rules = rules.sort_values(["_priority", "rule_id"])
    unit_keys = set(units.get("unit_key", pd.Series(dtype=str)).map(clean_text))
    nature_keys = set(natures.get("nature_key", pd.Series(dtype=str)).map(clean_text))
    unit_labels = _label_lookup(units, "unit_key")
    nature_labels = _label_lookup(natures, "nature_key")
    result = df.copy()
    assignments: list[tuple[str, str, str, str]] = []
    for _, row in result.iterrows():
        assigned_unit = "pendiente"
        assigned_nature = "pendiente"
        rule_id = ""
        status = "pendiente"
        for _, rule in rules.iterrows():
            if not _row_matches_management_rule(row, rule):
                continue
            candidate_unit = clean_text(rule.get("unidad_destino", ""))
            candidate_nature = clean_text(rule.get("naturaleza_trabajo", ""))
            assigned_unit = candidate_unit if candidate_unit in unit_keys else "pendiente"
            assigned_nature = candidate_nature if candidate_nature in nature_keys else "pendiente"
            rule_id = clean_text(rule.get("rule_id", ""))
            status = "clasificado" if assigned_unit != "pendiente" and assigned_nature != "pendiente" else "pendiente"
            break
        assignments.append((assigned_unit, assigned_nature, rule_id, status))
    result["unidad_destino"] = [item[0] for item in assignments]
    result["naturaleza_trabajo"] = [item[1] for item in assignments]
    result["classification_rule_id"] = [item[2] for item in assignments]
    result["classification_status"] = [item[3] for item in assignments]
    result["unidad_destino_label"] = result["unidad_destino"].map(lambda key: unit_labels.get(key, key))
    result["naturaleza_trabajo_label"] = result["naturaleza_trabajo"].map(lambda key: nature_labels.get(key, key))
    result["grupo_gestion"] = result["unidad_destino_label"] + " · " + result["naturaleza_trabajo_label"]
    return result


def hours_to_minutes(value: Any) -> int:
    if value is None or clean_text(value) == "":
        return 0
    if isinstance(value, str) and ":" in value:
        sign = -1 if value.strip().startswith("-") else 1
        text = value.strip().lstrip("+-")
        parts = text.split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid HH:MM duration: {value!r}")
        hours = int(parts[0] or "0")
        minutes = int(parts[1] or "0")
        if minutes < 0 or minutes >= 60:
            raise ValueError(f"Invalid minute component: {value!r}")
        return sign * (hours * 60 + minutes)
    numeric = pd.to_numeric(pd.Series([str(value).replace(",", ".")]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return 0
    return int(round(float(numeric) * 60))


def minutes_to_hours(value: Any) -> float:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return 0.0
    return float(numeric) / 60.0


def stable_row_id(row: pd.Series, prefix: str, ordinal: int | None = None) -> str:
    payload = json.dumps({key: clean_text(value) for key, value in row.items()}, ensure_ascii=False, sort_keys=True, default=str)
    if ordinal is not None:
        payload = f"{ordinal}|{payload}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _month_bounds(year: int, month: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = pd.Timestamp(year=int(year), month=int(month), day=1)
    end = start + pd.offsets.MonthEnd(0)
    return start.normalize(), pd.Timestamp(end).normalize()


def _safe_date_series(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.normalize()


def load_planning_detail(path: Path = PLANNING_DETAIL_FILE) -> pd.DataFrame:
    raw = read_csv(path)
    return normalize_planning_detail(raw, path)


def load_actuals_detail(path: Path = ACTUALS_DETAIL_FILE) -> pd.DataFrame:
    raw = read_csv(path)
    return normalize_actuals_detail(raw, path)


def normalize_planning_detail(df: pd.DataFrame, source_path: Path | None = None) -> pd.DataFrame:
    columns = [
        "forecast_id",
        "planning_row_id",
        "year",
        "month",
        "period_start",
        "period_end",
        "person_key",
        "employee_id",
        "person_name",
        "department_name",
        "internal_group",
        "subdepartment",
        "project_id",
        "project_name",
        "task_id",
        "task_name",
        "unidad_destino",
        "unidad_destino_label",
        "naturaleza_trabajo",
        "naturaleza_trabajo_label",
        "grupo_gestion",
        "classification_status",
        "planned_minutes",
        "planned_hours",
        "source_model",
        "source_file",
        "active",
    ]
    if df.empty:
        return pd.DataFrame(columns=columns)
    source = df.copy()
    active = source.get("active", "True").astype(str).map(lambda value: normalize_text(value) in {"true", "1", "si", "yes", "y", "verdadero"})
    source = source[active].copy()
    if source.empty:
        return pd.DataFrame(columns=columns)
    for column in [
        "source_id",
        "planning_id",
        "person_id",
        "person_key",
        "person_name",
        "department_name",
        "project_id",
        "project_name",
        "task_id",
        "task_name",
        "unidad_destino",
        "unidad_destino_label",
        "naturaleza_trabajo",
        "naturaleza_trabajo_label",
        "grupo_gestion",
        "classification_status",
        "source_model",
        "source_file",
    ]:
        if column not in source.columns:
            source[column] = ""
        source[column] = source[column].map(clean_text)
    source["forecast_id"] = source["source_id"].map(normalize_id)
    source["planning_row_id"] = source["planning_id"].where(source["planning_id"].ne(""), "FORECAST-" + source["forecast_id"])
    source["person_key"] = source["person_key"].where(source["person_key"].ne(""), source["person_name"].map(normalize_text))
    source["employee_id"] = source["person_id"].map(normalize_id)
    source["internal_group"] = source["department_name"].map(clean_text)
    source["subdepartment"] = source["department_name"].map(clean_text)
    source["date_start"] = _safe_date_series(source.get("date_start", ""))
    source["date_end"] = _safe_date_series(source.get("date_end", ""))
    source["year"] = pd.to_numeric(source.get("year", source["date_start"].dt.year), errors="coerce").fillna(source["date_start"].dt.year).astype(int)
    source["month"] = pd.to_numeric(source.get("month", source.get("month_number", source["date_start"].dt.month)), errors="coerce").fillna(source["date_start"].dt.month).astype(int)
    starts: list[pd.Timestamp] = []
    ends: list[pd.Timestamp] = []
    for _, row in source.iterrows():
        fallback_start, fallback_end = _month_bounds(int(row["year"]), int(row["month"]))
        starts.append(row["date_start"] if pd.notna(row["date_start"]) else fallback_start)
        ends.append(row["date_end"] if pd.notna(row["date_end"]) else fallback_end)
    source["period_start"] = starts
    source["period_end"] = ends
    source["planned_minutes"] = source.get("planned_hours", 0).map(hours_to_minutes)
    source["planned_hours"] = source["planned_minutes"].map(minutes_to_hours)
    source["source_model"] = source["source_model"].where(source["source_model"].ne(""), "project.forecast")
    source["source_file"] = source["source_file"].where(source["source_file"].ne(""), source_path.name if source_path else "")
    for column in ["unidad_destino", "unidad_destino_label", "naturaleza_trabajo", "naturaleza_trabajo_label", "grupo_gestion", "classification_status"]:
        source[column] = source[column].replace("", pd.NA)
    source["unidad_destino"] = source["unidad_destino"].fillna("pendiente")
    source["unidad_destino_label"] = source["unidad_destino_label"].fillna("Pendiente de clasificar")
    source["naturaleza_trabajo"] = source["naturaleza_trabajo"].fillna("pendiente")
    source["naturaleza_trabajo_label"] = source["naturaleza_trabajo_label"].fillna("Pendiente de clasificar")
    source["grupo_gestion"] = source["grupo_gestion"].fillna(source["unidad_destino_label"] + " · " + source["naturaleza_trabajo_label"])
    source["classification_status"] = source["classification_status"].fillna("pendiente")
    return source[columns].copy()


def normalize_actuals_detail(df: pd.DataFrame, source_path: Path | None = None) -> pd.DataFrame:
    columns = [
        "actual_line_id",
        "year",
        "month",
        "actual_date",
        "period_start",
        "period_end",
        "person_key",
        "employee_id",
        "person_name",
        "department_name",
        "internal_group",
        "subdepartment",
        "project_id",
        "project_name",
        "task_id",
        "task_name",
        "unidad_destino",
        "unidad_destino_label",
        "naturaleza_trabajo",
        "naturaleza_trabajo_label",
        "grupo_gestion",
        "classification_status",
        "actual_minutes",
        "actual_hours",
        "description",
        "source_model",
        "source_file",
    ]
    if df.empty:
        return pd.DataFrame(columns=columns)
    source = df.copy()
    source["actual_date"] = _safe_date_series(source.get("data", source.get("date", "")))
    source = source[source["actual_date"].notna()].copy()
    if source.empty:
        return pd.DataFrame(columns=columns)
    source["year"] = pd.to_numeric(source.get("urtea", source["actual_date"].dt.year), errors="coerce").fillna(source["actual_date"].dt.year).astype(int)
    source["month"] = pd.to_numeric(source.get("hilabete_zk", source["actual_date"].dt.month), errors="coerce").fillna(source["actual_date"].dt.month).astype(int)
    for column, fallback in [
        ("pertsona", ""),
        ("saila", ""),
        ("project_id", ""),
        ("project_name", "project_id"),
        ("task_id", ""),
        ("task_name", "task_id"),
        ("unidad_destino", ""),
        ("unidad_destino_label", ""),
        ("naturaleza_trabajo", ""),
        ("naturaleza_trabajo_label", ""),
        ("grupo_gestion", ""),
        ("classification_status", ""),
        ("azalpena", ""),
        ("source_file", ""),
    ]:
        if column not in source.columns:
            source[column] = source[fallback] if fallback in source.columns else ""
        source[column] = source[column].map(clean_text)
    source["person_name"] = source["pertsona"].map(clean_text)
    source["person_key"] = source["person_name"].map(normalize_text)
    source["employee_id"] = ""
    source["department_name"] = source["saila"].map(lambda value: clean_text(value).split("/")[0].strip())
    source["internal_group"] = source["saila"].map(clean_text)
    source["subdepartment"] = source["saila"].map(clean_text)
    starts: list[pd.Timestamp] = []
    ends: list[pd.Timestamp] = []
    for _, row in source.iterrows():
        start, end = _month_bounds(int(row["year"]), int(row["month"]))
        starts.append(start)
        ends.append(end)
    source["period_start"] = starts
    source["period_end"] = ends
    source["actual_minutes"] = source.get("ordu_errealak", 0).map(hours_to_minutes)
    source["actual_hours"] = source["actual_minutes"].map(minutes_to_hours)
    source["actual_line_id"] = [stable_row_id(row, "AAL", ordinal) for ordinal, (_, row) in enumerate(source.iterrows())]
    source["description"] = source["azalpena"]
    source["source_model"] = "account.analytic.line"
    source["source_file"] = source["source_file"].where(source["source_file"].ne(""), source_path.name if source_path else "")
    for column in ["unidad_destino", "unidad_destino_label", "naturaleza_trabajo", "naturaleza_trabajo_label", "grupo_gestion", "classification_status"]:
        source[column] = source[column].replace("", pd.NA)
    source["unidad_destino"] = source["unidad_destino"].fillna("pendiente")
    source["unidad_destino_label"] = source["unidad_destino_label"].fillna("Pendiente de clasificar")
    source["naturaleza_trabajo"] = source["naturaleza_trabajo"].fillna("pendiente")
    source["naturaleza_trabajo_label"] = source["naturaleza_trabajo_label"].fillna("Pendiente de clasificar")
    source["grupo_gestion"] = source["grupo_gestion"].fillna(source["unidad_destino_label"] + " · " + source["naturaleza_trabajo_label"])
    source["classification_status"] = source["classification_status"].fillna("pendiente")
    return source[columns].copy()


def organization_people_from_actuals(actuals: pd.DataFrame) -> pd.DataFrame:
    columns = ["person_key", "employee_id", "person_name", "department_name", "internal_group", "subdepartment", "actual_hours_period"]
    if actuals.empty:
        return pd.DataFrame(columns=columns)
    table = (
        actuals[actuals["person_name"].map(clean_text).ne("")]
        .groupby(["person_key", "employee_id", "person_name", "department_name", "internal_group", "subdepartment"], as_index=False, dropna=False)
        .agg(actual_hours_period=("actual_hours", "sum"))
        .sort_values(["department_name", "subdepartment", "person_name"])
    )
    return table[columns].copy()


def _candidate_planning_rows(actual: pd.Series, planning: pd.DataFrame, quality: str) -> pd.DataFrame:
    candidates = planning[
        (planning["person_key"] == actual["person_key"])
        & (planning["period_start"] <= actual["actual_date"])
        & (planning["period_end"] >= actual["actual_date"])
    ].copy()
    actual_project_id = clean_text(actual.get("_project_id_norm", normalize_id(actual["project_id"])))
    actual_project_name = clean_text(actual.get("_project_name_norm", normalize_text(actual.get("project_name", ""))))
    actual_task_id = clean_text(actual.get("_task_id_norm", normalize_id(actual["task_id"])))
    actual_task_name = clean_text(actual.get("_task_name_norm", normalize_text(actual.get("task_name", ""))))
    project_match = (
        (candidates["_project_id_norm"].eq(actual_project_id) & candidates["_project_id_norm"].ne("") & bool(actual_project_id))
        | (candidates["_project_name_norm"].eq(actual_project_name) & candidates["_project_name_norm"].ne("") & bool(actual_project_name))
    )
    task_match = (
        (candidates["_task_id_norm"].eq(actual_task_id) & candidates["_task_id_norm"].ne("") & bool(actual_task_id))
        | (candidates["_task_name_norm"].eq(actual_task_name) & candidates["_task_name_norm"].ne("") & bool(actual_task_name))
    )
    if quality == MATCH_EXACT:
        candidates = candidates[project_match & task_match].copy()
    elif quality == MATCH_PROJECT:
        candidates = candidates[project_match].copy()
    elif quality == MATCH_TASK:
        candidates = candidates[task_match].copy()
    return candidates


def match_actuals_to_planning(actuals: pd.DataFrame, planning: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    match_columns = [
        "actual_line_id",
        "actual_minutes",
        "forecast_id",
        "planning_row_id",
        "match_quality",
        "match_status",
        "conflict",
        "candidate_count",
        "conflict_forecast_ids",
    ]
    if actuals.empty:
        return pd.DataFrame(columns=match_columns), pd.DataFrame(columns=match_columns)
    if planning.empty:
        result = actuals[["actual_line_id", "actual_minutes"]].copy()
        result["forecast_id"] = ""
        result["planning_row_id"] = ""
        result["match_quality"] = MATCH_NONE
        result["match_status"] = "unplanned"
        result["conflict"] = False
        result["candidate_count"] = 0
        result["conflict_forecast_ids"] = ""
        return result[match_columns], pd.DataFrame(columns=match_columns)

    actuals_source = actuals.copy()
    for source in [actuals_source]:
        source["_project_id_norm"] = source["project_id"].map(normalize_id)
        source["_project_name_norm"] = source["project_name"].map(normalize_text)
        source["_task_id_norm"] = source["task_id"].map(normalize_id)
        source["_task_name_norm"] = source["task_name"].map(normalize_text)
    planning_source = planning.copy()
    planning_source["_project_id_norm"] = planning_source["project_id"].map(normalize_id)
    planning_source["_project_name_norm"] = planning_source["project_name"].map(normalize_text)
    planning_source["_task_id_norm"] = planning_source["task_id"].map(normalize_id)
    planning_source["_task_name_norm"] = planning_source["task_name"].map(normalize_text)
    planning_source["_interval_days"] = (planning_source["period_end"] - planning_source["period_start"]).dt.days.fillna(999999).astype(int)
    planning_source["_forecast_sort"] = planning_source["forecast_id"].map(lambda value: int(value) if clean_text(value).isdigit() else 10**12)
    planning_by_person = {person: subset.copy() for person, subset in planning_source.groupby("person_key", dropna=False)}
    rows: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    planning_cols = [
        "forecast_id",
        "planning_row_id",
        "period_start",
        "period_end",
        "_interval_days",
        "_forecast_sort",
        "_project_id_norm",
        "_project_name_norm",
        "_task_id_norm",
        "_task_name_norm",
    ]
    actual_cols = [
        "actual_line_id",
        "actual_minutes",
        "actual_date",
        "_project_id_norm",
        "_project_name_norm",
        "_task_id_norm",
        "_task_name_norm",
    ]
    quality_by_priority = {1: MATCH_EXACT, 2: MATCH_PROJECT, 3: MATCH_TASK}
    for person_key, actual_group in actuals_source.groupby("person_key", dropna=False):
        person_planning = planning_by_person.get(person_key, pd.DataFrame(columns=planning_source.columns))
        if person_planning.empty:
            for _, actual in actual_group.iterrows():
                rows.append(
                    {
                        "actual_line_id": actual["actual_line_id"],
                        "actual_minutes": int(actual["actual_minutes"]),
                        "forecast_id": "",
                        "planning_row_id": "",
                        "match_quality": MATCH_NONE,
                        "match_status": "unplanned",
                        "conflict": False,
                        "candidate_count": 0,
                        "conflict_forecast_ids": "",
                    }
                )
            continue
        cross = actual_group[actual_cols].merge(
            person_planning[planning_cols],
            how="cross",
            suffixes=("_actual", ""),
        )
        cross = cross[(cross["period_start"] <= cross["actual_date"]) & (cross["period_end"] >= cross["actual_date"])].copy()
        if cross.empty:
            matched_ids: set[str] = set()
            winners = pd.DataFrame()
        else:
            project_match = (
                (cross["_project_id_norm_actual"].ne("") & cross["_project_id_norm_actual"].eq(cross["_project_id_norm"]))
                | (cross["_project_name_norm_actual"].ne("") & cross["_project_name_norm_actual"].eq(cross["_project_name_norm"]))
            )
            task_match = (
                (cross["_task_id_norm_actual"].ne("") & cross["_task_id_norm_actual"].eq(cross["_task_id_norm"]))
                | (cross["_task_name_norm_actual"].ne("") & cross["_task_name_norm_actual"].eq(cross["_task_name_norm"]))
            )
            cross["_priority"] = 0
            cross.loc[task_match, "_priority"] = 3
            cross.loc[project_match, "_priority"] = 2
            cross.loc[project_match & task_match, "_priority"] = 1
            candidates = cross[cross["_priority"] > 0].copy()
            if candidates.empty:
                matched_ids = set()
                winners = pd.DataFrame()
            else:
                candidates = candidates.sort_values(["actual_line_id", "_priority", "_interval_days", "_forecast_sort", "forecast_id", "planning_row_id"])
                winners = candidates.drop_duplicates("actual_line_id", keep="first").copy()
                winning_priorities = winners[["actual_line_id", "_priority"]].rename(columns={"_priority": "_winning_priority"})
                same_priority = candidates.merge(winning_priorities, on="actual_line_id", how="inner")
                same_priority = same_priority[same_priority["_priority"].eq(same_priority["_winning_priority"])].copy()
                counts = same_priority.groupby("actual_line_id", as_index=False).agg(
                    candidate_count=("forecast_id", "size"),
                    conflict_forecast_ids=("forecast_id", _aggregate_source_ids),
                )
                winners = winners.merge(counts, on="actual_line_id", how="left")
                matched_ids = set(winners["actual_line_id"].tolist())
        winner_by_id = {row["actual_line_id"]: row for _, row in winners.iterrows()} if not winners.empty else {}
        for _, actual in actual_group.iterrows():
            actual_id = actual["actual_line_id"]
            if actual_id not in matched_ids:
                rows.append(
                    {
                        "actual_line_id": actual_id,
                        "actual_minutes": int(actual["actual_minutes"]),
                        "forecast_id": "",
                        "planning_row_id": "",
                        "match_quality": MATCH_NONE,
                        "match_status": "unplanned",
                        "conflict": False,
                        "candidate_count": 0,
                        "conflict_forecast_ids": "",
                    }
                )
                continue
            winner = winner_by_id[actual_id]
            candidate_count = int(winner.get("candidate_count", 1) or 1)
            conflict = candidate_count > 1
            base_quality = quality_by_priority.get(int(winner["_priority"]), MATCH_NONE)
            row = {
                "actual_line_id": actual_id,
                "actual_minutes": int(actual["actual_minutes"]),
                "forecast_id": clean_text(winner["forecast_id"]),
                "planning_row_id": clean_text(winner["planning_row_id"]),
                "match_quality": MATCH_CONFLICT if conflict else base_quality,
                "match_status": "matched",
                "conflict": conflict,
                "candidate_count": candidate_count,
                "conflict_forecast_ids": clean_text(winner.get("conflict_forecast_ids", "")),
            }
            rows.append(row)
            if conflict:
                conflicts.append(row | {"resolved_as_forecast_id": clean_text(winner["forecast_id"]), "base_quality": base_quality})
    result = pd.DataFrame(rows, columns=match_columns)
    conflict_df = pd.DataFrame(conflicts)
    return result, conflict_df


def _aggregate_source_ids(values: pd.Series) -> str:
    unique = sorted({clean_text(value) for value in values.tolist() if clean_text(value)})
    return "|".join(unique)


def _grain_columns() -> list[str]:
    return [
        "year",
        "month",
        "period_start",
        "period_end",
        "person_key",
        "employee_id",
        "person_name",
        "department_name",
        "internal_group",
        "subdepartment",
        "project_id",
        "project_name",
        "task_id",
        "task_name",
        "unidad_destino",
        "unidad_destino_label",
        "naturaleza_trabajo",
        "naturaleza_trabajo_label",
        "grupo_gestion",
        "classification_status",
    ]


def build_operational_performance_dataset(planning: pd.DataFrame, actuals: pd.DataFrame, organization_people: pd.DataFrame | None = None) -> BuildResult:
    generated_at = now_text()
    planning_norm = normalize_planning_detail(planning) if "planned_minutes" not in planning.columns else planning.copy()
    actuals_norm = normalize_actuals_detail(actuals) if "actual_minutes" not in actuals.columns else actuals.copy()
    matches, conflicts = match_actuals_to_planning(actuals_norm, planning_norm)
    actuals_matched = actuals_norm.merge(matches, on=["actual_line_id", "actual_minutes"], how="left")

    grain = _grain_columns()
    if planning_norm.empty:
        planning_agg = pd.DataFrame(columns=grain + ["planned_minutes", "source_planning_rows"])
    else:
        planning_agg = (
            planning_norm.groupby(grain, as_index=False, dropna=False)
            .agg(planned_minutes=("planned_minutes", "sum"), source_planning_rows=("planning_row_id", _aggregate_source_ids))
        )

    matched = actuals_matched[actuals_matched["match_status"].eq("matched")].copy()
    if matched.empty or planning_norm.empty:
        matched_agg = pd.DataFrame(columns=grain + ["actual_minutes_with_planning", "source_actual_rows", "match_quality"])
    else:
        matched = matched.merge(
            planning_norm[["planning_row_id"] + grain],
            on="planning_row_id",
            how="left",
            suffixes=("_actual", ""),
        )
        matched_agg = (
            matched.groupby(grain, as_index=False, dropna=False)
            .agg(
                actual_minutes_with_planning=("actual_minutes", "sum"),
                source_actual_rows=("actual_line_id", _aggregate_source_ids),
                match_quality=("match_quality", lambda values: MATCH_CONFLICT if MATCH_CONFLICT in set(values) else clean_text(next(iter(values), ""))),
            )
        )

    unplanned = actuals_matched[~actuals_matched["match_status"].eq("matched")].copy()
    if unplanned.empty:
        unplanned_agg = pd.DataFrame(columns=grain + ["actual_minutes_without_planning", "source_actual_rows", "match_quality"])
    else:
        period_ends = []
        for _, row in unplanned.iterrows():
            _, end = _month_bounds(int(row["year"]), int(row["month"]))
            period_ends.append(end)
        unplanned["period_start"] = unplanned.apply(lambda row: _month_bounds(int(row["year"]), int(row["month"]))[0], axis=1)
        unplanned["period_end"] = period_ends
        unplanned_agg = (
            unplanned.groupby(grain, as_index=False, dropna=False)
            .agg(
                actual_minutes_without_planning=("actual_minutes", "sum"),
                source_actual_rows=("actual_line_id", _aggregate_source_ids),
                match_quality=("match_quality", lambda values: MATCH_NONE),
            )
        )

    detail = planning_agg.merge(matched_agg, on=grain, how="outer", suffixes=("", "_matched"))
    detail = detail.merge(unplanned_agg, on=grain, how="outer", suffixes=("", "_unplanned"))
    for column in ["planned_minutes", "actual_minutes_with_planning", "actual_minutes_without_planning"]:
        detail[column] = pd.to_numeric(detail.get(column, 0), errors="coerce").fillna(0).astype(int)
    detail["actual_minutes"] = detail["actual_minutes_with_planning"] + detail["actual_minutes_without_planning"]
    detail["planned_minutes_not_executed"] = (detail["planned_minutes"] - detail["actual_minutes_with_planning"]).clip(lower=0).astype(int)
    detail["deviation_minutes"] = detail["actual_minutes"] - detail["planned_minutes"]
    detail["planned_hours"] = detail["planned_minutes"].map(minutes_to_hours)
    detail["actual_hours"] = detail["actual_minutes"].map(minutes_to_hours)
    detail["actual_hours_with_planning"] = detail["actual_minutes_with_planning"].map(minutes_to_hours)
    detail["actual_hours_without_planning"] = detail["actual_minutes_without_planning"].map(minutes_to_hours)
    detail["planned_hours_not_executed"] = detail["planned_minutes_not_executed"].map(minutes_to_hours)
    detail["deviation_hours"] = detail["deviation_minutes"].map(minutes_to_hours)
    detail["deviation_pct"] = detail.apply(lambda row: row["deviation_hours"] / row["planned_hours"] * 100 if row["planned_hours"] else math.nan, axis=1)
    detail["planning_coverage_pct"] = detail.apply(lambda row: row["actual_hours_with_planning"] / row["actual_hours"] * 100 if row["actual_hours"] else math.nan, axis=1)
    detail["planning_execution_pct"] = detail.apply(lambda row: row["actual_hours_with_planning"] / row["planned_hours"] * 100 if row["planned_hours"] else math.nan, axis=1)
    detail["available_hours"] = math.nan
    detail["occupation_planned_pct"] = math.nan
    detail["occupation_actual_pct"] = math.nan
    detail["projects_count"] = detail["project_name"].map(lambda value: 1 if clean_text(value) else 0)
    detail["tasks_count"] = detail["task_name"].map(lambda value: 1 if clean_text(value) else 0)
    quality_columns = [column for column in ["match_quality", "match_quality_unplanned"] if column in detail.columns]
    detail["match_quality"] = detail[quality_columns].bfill(axis=1).iloc[:, 0] if quality_columns else ""
    detail["match_quality"] = detail["match_quality"].fillna("")
    detail["match_status"] = detail.apply(
        lambda row: "mixed" if row["actual_minutes_with_planning"] and row["actual_minutes_without_planning"] else ("matched" if row["actual_minutes_with_planning"] else ("unplanned" if row["actual_minutes_without_planning"] else "planning_only")),
        axis=1,
    )
    source_cols = [col for col in ["source_actual_rows", "source_actual_rows_unplanned"] if col in detail.columns]
    if source_cols:
        detail["source_actual_rows"] = detail[source_cols].fillna("").agg(lambda row: "|".join([clean_text(v) for v in row if clean_text(v)]), axis=1)
    else:
        detail["source_actual_rows"] = ""
    detail["source_planning_rows"] = detail.get("source_planning_rows", "").fillna("")
    detail["generated_at"] = generated_at
    for column in OUTPUT_COLUMNS:
        if column not in detail.columns:
            detail[column] = "" if column not in {"planned_minutes", "actual_minutes", "actual_minutes_with_planning", "actual_minutes_without_planning", "planned_minutes_not_executed"} else 0
    detail = detail[OUTPUT_COLUMNS].sort_values(["year", "month", "person_name", "project_name", "task_name"]).reset_index(drop=True)

    diagnostics = {
        "planning_rows": int(len(planning_norm)),
        "actual_rows": int(len(actuals_norm)),
        "planning_hours": float(planning_norm["planned_hours"].sum()) if not planning_norm.empty else 0.0,
        "actual_hours": float(actuals_norm["actual_hours"].sum()) if not actuals_norm.empty else 0.0,
        "matched_actual_hours": float(detail["actual_hours_with_planning"].sum()) if not detail.empty else 0.0,
        "unmatched_actual_hours": float(detail["actual_hours_without_planning"].sum()) if not detail.empty else 0.0,
        "conflict_actual_hours": float(conflicts["actual_minutes"].sum() / 60.0) if not conflicts.empty and "actual_minutes" in conflicts else 0.0,
        "match_coverage_pct": float(detail["actual_hours_with_planning"].sum() / detail["actual_hours"].sum() * 100) if not detail.empty and detail["actual_hours"].sum() else 0.0,
        "projects": int(detail["project_name"].nunique()) if not detail.empty else 0,
        "people": int(detail["person_name"].nunique()) if not detail.empty else 0,
        "tasks": int(detail["task_name"].nunique()) if not detail.empty else 0,
        "conflicts": int(len(conflicts)),
        "pending_classification": int(detail["classification_status"].eq("pendiente").sum()) if not detail.empty else 0,
        "generated_at": generated_at,
    }
    return BuildResult(detail=detail, actual_matches=matches, conflicts=conflicts, diagnostics=diagnostics)


def project_status(planned_hours: float, actual_hours: float) -> str:
    if planned_hours <= 0 and actual_hours > 0:
        return PROJECT_UNPLANNED
    if planned_hours > 0 and actual_hours <= 0:
        return PROJECT_UNEXECUTED
    if planned_hours <= 0 and actual_hours <= 0:
        return PROJECT_NO_DATA
    deviation_pct = abs((actual_hours - planned_hours) / planned_hours * 100)
    if deviation_pct <= 10:
        return PROJECT_ON_TRACK
    if deviation_pct <= 20:
        return PROJECT_ATTENTION
    if deviation_pct <= 40:
        return PROJECT_DEVIATED
    return PROJECT_CRITICAL


def load_status(occupation_pct: float | None) -> str:
    if occupation_pct is None or pd.isna(occupation_pct):
        return LOAD_NO_AVAILABILITY
    if occupation_pct > 100:
        return LOAD_OVERLOAD
    if occupation_pct > 90:
        return LOAD_RISK
    return LOAD_OK


def calculate_operational_kpis(df: pd.DataFrame) -> dict[str, Any]:
    planned = float(df["planned_hours"].sum()) if not df.empty and "planned_hours" in df else 0.0
    actual = float(df["actual_hours"].sum()) if not df.empty and "actual_hours" in df else 0.0
    with_planning = float(df["actual_hours_with_planning"].sum()) if not df.empty and "actual_hours_with_planning" in df else 0.0
    without_planning = float(df["actual_hours_without_planning"].sum()) if not df.empty and "actual_hours_without_planning" in df else 0.0
    pending = float(df["planned_hours_not_executed"].sum()) if not df.empty and "planned_hours_not_executed" in df else 0.0
    deviation = actual - planned
    return {
        "planned_hours": planned,
        "actual_hours": actual,
        "deviation_hours": deviation,
        "planning_coverage_pct": with_planning / actual * 100 if actual else None,
        "actual_hours_without_planning": without_planning,
        "planned_hours_not_executed": pending,
        "overconsumption_hours": max(deviation, 0.0),
        "projects_with_overconsumption": int((aggregate_by_dimension(df, "project_name")["deviation_hours"] > 0).sum()) if not df.empty else 0,
        "people": int(df["person_name"].nunique()) if not df.empty and "person_name" in df else 0,
        "projects": int(df["project_name"].nunique()) if not df.empty and "project_name" in df else 0,
        "tasks": int(df["task_name"].nunique()) if not df.empty and "task_name" in df else 0,
        "conflicts": int(df["match_quality"].eq(MATCH_CONFLICT).sum()) if not df.empty and "match_quality" in df else 0,
        "pending_classification": int(df["classification_status"].eq("pendiente").sum()) if not df.empty and "classification_status" in df else 0,
    }


def aggregate_by_dimension(df: pd.DataFrame, dimension: str) -> pd.DataFrame:
    columns = [
        dimension,
        "planned_hours",
        "actual_hours",
        "actual_hours_with_planning",
        "actual_hours_without_planning",
        "planned_hours_not_executed",
        "deviation_hours",
        "overconsumption_hours",
        "deviation_pct",
        "planning_coverage_pct",
        "planning_execution_pct",
        "project_status",
    ]
    if df.empty or dimension not in df.columns:
        return pd.DataFrame(columns=columns)
    table = (
        df.groupby(dimension, as_index=False, dropna=False)
        .agg(
            planned_hours=("planned_hours", "sum"),
            actual_hours=("actual_hours", "sum"),
            actual_hours_with_planning=("actual_hours_with_planning", "sum"),
            actual_hours_without_planning=("actual_hours_without_planning", "sum"),
            planned_hours_not_executed=("planned_hours_not_executed", "sum"),
        )
        .sort_values("actual_hours", ascending=False)
    )
    table["deviation_hours"] = table["actual_hours"] - table["planned_hours"]
    table["overconsumption_hours"] = table["deviation_hours"].clip(lower=0)
    table["deviation_pct"] = table.apply(lambda row: row["deviation_hours"] / row["planned_hours"] * 100 if row["planned_hours"] else math.nan, axis=1)
    table["planning_coverage_pct"] = table.apply(lambda row: row["actual_hours_with_planning"] / row["actual_hours"] * 100 if row["actual_hours"] else math.nan, axis=1)
    table["planning_execution_pct"] = table.apply(lambda row: row["actual_hours_with_planning"] / row["planned_hours"] * 100 if row["planned_hours"] else math.nan, axis=1)
    table["project_status"] = table.apply(lambda row: project_status(float(row["planned_hours"]), float(row["actual_hours"])), axis=1)
    return table[columns].copy()


def calculate_people_load(df: pd.DataFrame, availability_people: pd.DataFrame | None = None, organization_people: pd.DataFrame | None = None) -> pd.DataFrame:
    columns = [
        "person_name",
        "department_name",
        "internal_group",
        "available_hours",
        "planned_hours",
        "actual_hours",
        "deviation_hours",
        "actual_hours_with_planning",
        "actual_hours_without_planning",
        "planning_coverage_pct",
        "occupation_planned_pct",
        "occupation_actual_pct",
        "direct_pct",
        "indirect_pct",
        "not_applicable_pct",
        "pending_pct",
        "projects_count",
        "tasks_count",
        "load_status",
        "planning_status",
    ]
    people = set(df["person_name"].dropna().map(clean_text).tolist()) if not df.empty and "person_name" in df.columns else set()
    if organization_people is not None and not organization_people.empty and "person_name" in organization_people.columns:
        people.update(organization_people["person_name"].dropna().map(clean_text).tolist())
    rows: list[dict[str, Any]] = []
    availability = (
        availability_people.groupby("person_name")["calculated_available_hours"].sum()
        if availability_people is not None and not availability_people.empty and "calculated_available_hours" in availability_people.columns
        else pd.Series(dtype=float)
    )
    for person in sorted([p for p in people if p], key=normalize_text):
        subset = df[df["person_name"].map(clean_text).eq(person)].copy() if not df.empty else pd.DataFrame()
        org = organization_people[organization_people["person_name"].map(clean_text).eq(person)].head(1) if organization_people is not None and not organization_people.empty else pd.DataFrame()
        planned = float(subset["planned_hours"].sum()) if not subset.empty else 0.0
        actual = float(subset["actual_hours"].sum()) if not subset.empty else 0.0
        with_planning = float(subset["actual_hours_with_planning"].sum()) if not subset.empty else 0.0
        without_planning = float(subset["actual_hours_without_planning"].sum()) if not subset.empty else 0.0
        available = float(availability.get(person, 0.0))
        occupation_planned = planned / available * 100 if available > 0 else None
        occupation_actual = actual / available * 100 if available > 0 else None
        nature_hours = subset.groupby("naturaleza_trabajo")["actual_hours"].sum() if not subset.empty else pd.Series(dtype=float)
        total_for_mix = float(nature_hours.sum())
        rows.append(
            {
                "person_name": person,
                "department_name": clean_text(org["department_name"].iloc[0]) if not org.empty and "department_name" in org.columns else "",
                "internal_group": clean_text(org["internal_group"].iloc[0]) if not org.empty and "internal_group" in org.columns else "",
                "available_hours": available,
                "planned_hours": planned,
                "actual_hours": actual,
                "deviation_hours": actual - planned,
                "actual_hours_with_planning": with_planning,
                "actual_hours_without_planning": without_planning,
                "planning_coverage_pct": with_planning / actual * 100 if actual else None,
                "occupation_planned_pct": occupation_planned,
                "occupation_actual_pct": occupation_actual,
                "direct_pct": float(nature_hours.get("directo", 0.0)) / total_for_mix * 100 if total_for_mix else None,
                "indirect_pct": float(nature_hours.get("indirecto", 0.0)) / total_for_mix * 100 if total_for_mix else None,
                "not_applicable_pct": float(nature_hours.get("no_aplica", 0.0)) / total_for_mix * 100 if total_for_mix else None,
                "pending_pct": float(nature_hours.get("pendiente", 0.0)) / total_for_mix * 100 if total_for_mix else None,
                "projects_count": int(subset["project_name"].nunique()) if not subset.empty else 0,
                "tasks_count": int(subset["task_name"].nunique()) if not subset.empty else 0,
                "load_status": load_status(occupation_actual if occupation_actual is not None else occupation_planned),
                "planning_status": "Sin planificacion" if planned <= 0 else ("Planificacion parcial" if without_planning > 0 else "Con planificacion"),
            }
        )
    return pd.DataFrame(rows, columns=columns).sort_values(["actual_hours", "planned_hours", "person_name"], ascending=[False, False, True])


def write_operational_diagnostics(result: BuildResult, report_dir: Path = DATA_REPORTS_DIR) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    detail = result.detail
    pd.DataFrame([result.diagnostics]).to_csv(report_dir / DIAGNOSTICS_FILE.name, sep=";", encoding="utf-8-sig", index=False)
    result.conflicts.to_csv(report_dir / MATCH_CONFLICTS_FILE.name, sep=";", encoding="utf-8-sig", index=False)
    detail[detail["actual_minutes_without_planning"] > 0].to_csv(report_dir / UNPLANNED_ACTUALS_FILE.name, sep=";", encoding="utf-8-sig", index=False)
    detail[(detail["planned_minutes"] > 0) & (detail["actual_minutes_with_planning"] == 0)].to_csv(report_dir / UNEXECUTED_PLANNING_FILE.name, sep=";", encoding="utf-8-sig", index=False)
    over = aggregate_by_dimension(detail, "project_name")
    over = over[over["overconsumption_hours"] > 0].copy()
    over.to_csv(report_dir / OVERCONSUMPTION_FILE.name, sep=";", encoding="utf-8-sig", index=False)
    people = calculate_people_load(detail)
    people.to_csv(report_dir / PEOPLE_COVERAGE_FILE.name, sep=";", encoding="utf-8-sig", index=False)
    pending = detail[detail["classification_status"].eq("pendiente")].copy()
    pending.to_csv(report_dir / PENDING_CLASSIFICATION_FILE.name, sep=";", encoding="utf-8-sig", index=False)
