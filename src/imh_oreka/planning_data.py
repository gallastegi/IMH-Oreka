from __future__ import annotations

import argparse
import ast
import hashlib
import json
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
REPORTS_DIR = ROOT_DIR / "data" / "reports"
CONFIG_DIR = ROOT_DIR / "config"

RAW_PATTERN = "10_project_task_planning*"
FORECAST_PATTERN = "09_project_forecast*.json"
PROCESSED_PLANNING_FILE = PROCESSED_DIR / "17_prc01_planning_detail.csv"

SOURCE_DIAGNOSTICS_FILE = REPORTS_DIR / "prc01_planning_source_diagnostics.csv"
UNMATCHED_PEOPLE_FILE = REPORTS_DIR / "prc01_planning_unmatched_people.csv"
DUPLICATES_FILE = REPORTS_DIR / "prc01_planning_duplicates.csv"
MONTHLY_RECONCILIATION_FILE = REPORTS_DIR / "prc01_planning_monthly_reconciliation.csv"
INVALID_ROWS_FILE = REPORTS_DIR / "prc01_planning_invalid_rows.csv"

PLANNING_PROCESSED_COLUMNS = [
    "planning_id",
    "active",
    "planning_status",
    "source_system",
    "source_model",
    "source_id",
    "source_name",
    "date_start",
    "date_end",
    "year",
    "month",
    "month_number",
    "person_key",
    "person_id",
    "person_name",
    "department_name",
    "project_id",
    "project_name",
    "task_id",
    "task_name",
    "planned_hours",
    "probability",
    "weighted_planned_hours",
    "unidad_destino",
    "unidad_destino_label",
    "naturaleza_trabajo",
    "naturaleza_trabajo_label",
    "grupo_gestion",
    "classification_rule_id",
    "classification_status",
    "source_file",
    "raw_source_file",
    "source_row_id",
    "monthly_allocation_method",
    "created_at",
    "updated_at",
    "transformation_timestamp",
    "raw_rows",
    "processed_rows",
    "raw_hours",
    "processed_hours",
    "imputed_hours",
    "remaining_hours",
    "raw_planned_hours",
]


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if text.lower() in {"nan", "none", "false"}:
        return ""
    return text


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", clean_text(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.casefold().replace("-", " ").split())


def normalize_bool(value: Any) -> bool:
    return normalize_text(value) in {"true", "1", "1.0", "si", "sí", "yes", "y"}


def to_float(value: Any, default: float | None = 0.0) -> float | None:
    text = clean_text(value).replace(",", ".")
    if not text:
        return default
    number = pd.to_numeric(pd.Series([text]), errors="coerce").iloc[0]
    if pd.isna(number):
        return default
    return float(number)


def duration_hhmm_to_minutes(value: Any) -> int:
    text = clean_text(value)
    if not text:
        return 0
    sign = -1 if text.startswith("-") else 1
    text = text.lstrip("+-")
    if ":" not in text:
        hours = to_float(text, 0.0) or 0.0
        return int(round(sign * hours * 60))
    parts = text.split(":")
    if len(parts) != 2:
        raise ValueError(f"Duracion HH:MM no valida: {value!r}")
    hours_text, minutes_text = parts
    hours = int(hours_text or "0")
    minutes = int(minutes_text or "0")
    if minutes < 0 or minutes >= 60:
        raise ValueError(f"Minutos fuera de rango en duracion: {value!r}")
    return sign * (hours * 60 + minutes)


def duration_hhmm_to_hours(value: Any) -> float:
    return duration_hhmm_to_minutes(value) / 60.0


def hours_to_duration_hhmm(value: Any) -> str:
    hours = to_float(value, 0.0) or 0.0
    minutes = int(round(hours * 60))
    sign = "-" if minutes < 0 else ""
    minutes = abs(minutes)
    return f"{sign}{minutes // 60:02d}:{minutes % 60:02d}"


def safe_parse_many2one(value: Any) -> tuple[str, str]:
    if value is None:
        return "", ""
    if isinstance(value, (list, tuple)):
        if len(value) >= 2:
            return clean_text(value[0]), clean_text(value[1])
        if len(value) == 1:
            first = clean_text(value[0])
            return (first, "") if first.isdigit() else ("", first)
        return "", ""
    text = clean_text(value)
    if not text:
        return "", ""
    if text.startswith("[") or text.startswith("("):
        try:
            parsed = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            parsed = None
        if isinstance(parsed, (list, tuple)):
            return safe_parse_many2one(parsed)
    if text.isdigit():
        return text, ""
    return "", text


def read_raw_file(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"El JSON no contiene una lista de registros: {path}")
        return pd.DataFrame(data)
    return pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype=str).fillna("")


def raw_planned_hours(df: pd.DataFrame) -> pd.Series:
    if "planned_hours" in df.columns:
        return pd.to_numeric(df["planned_hours"].astype(str).str.replace(",", ".", regex=False), errors="coerce").fillna(0.0)
    if "quantity" in df.columns:
        quantity = pd.to_numeric(df["quantity"].astype(str).str.replace(",", ".", regex=False), errors="coerce")
        if quantity.notna().any():
            return quantity.fillna(0.0)
    effective = pd.to_numeric(df.get("effective_hours", 0), errors="coerce").fillna(0.0)
    remaining = pd.to_numeric(df.get("remaining_hours", 0), errors="coerce").fillna(0.0)
    return effective + remaining


def raw_active_mask(df: pd.DataFrame) -> pd.Series:
    if "active" not in df.columns:
        return pd.Series([True] * len(df), index=df.index)
    return df["active"].map(normalize_bool)


def file_profile(path: Path) -> dict[str, Any]:
    df = read_raw_file(path)
    ids = df["id"].map(clean_text) if "id" in df.columns else pd.Series(dtype=str)
    hours = raw_planned_hours(df)
    active = raw_active_mask(df)
    date_values: list[pd.Series] = []
    for column in ["date_start", "date_deadline", "date_end", "create_date", "write_date"]:
        if column in df.columns:
            parsed = pd.to_datetime(df[column].replace("", pd.NA), errors="coerce")
            if parsed.notna().any():
                date_values.append(parsed.dropna())
    all_dates = pd.concat(date_values, ignore_index=True) if date_values else pd.Series(dtype="datetime64[ns]")
    return {
        "file": path.name,
        "path": str(path),
        "modified_at": datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        "rows": int(len(df)),
        "columns": "|".join(df.columns.astype(str).tolist()),
        "ids_unique": int(ids.nunique()) if not ids.empty else 0,
        "ids_empty": int(ids.eq("").sum()) if not ids.empty else int(len(df)),
        "hours": float(hours.sum()),
        "active_rows": int(active.sum()),
        "inactive_rows": int((~active).sum()),
        "date_min": all_dates.min().strftime("%Y-%m-%d") if not all_dates.empty else "",
        "date_max": all_dates.max().strftime("%Y-%m-%d") if not all_dates.empty else "",
        "id_set": set(ids.tolist()) if not ids.empty else set(),
    }


@dataclass
class SourceDecision:
    selected: Path
    profiles: pd.DataFrame
    reason: str


def resolve_planning_source(raw_dir: Path = RAW_DIR, explicit_source: Path | None = None) -> SourceDecision:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    if explicit_source is not None:
        source = explicit_source if explicit_source.is_absolute() else ROOT_DIR / explicit_source
        if not source.exists():
            raise FileNotFoundError(f"No existe la fuente explicita de planificación: {source}")
        profiles = [file_profile(path) for path in sorted(raw_dir.glob(RAW_PATTERN)) if path.is_file()]
        selected_profile = file_profile(source)
        if selected_profile["file"] not in [item["file"] for item in profiles]:
            profiles.append(selected_profile)
        reason = "Fuente indicada explícitamente mediante --source."
    else:
        forecast_files = [
            path
            for path in sorted(raw_dir.glob(FORECAST_PATTERN))
            if path.name != "09_project_forecast_fields.json" and path.is_file()
        ]
        task_files = [path for path in sorted(raw_dir.glob(RAW_PATTERN)) if path.suffix.lower() in {".csv", ".json"}]
        files = forecast_files + task_files
        if not files:
            raise FileNotFoundError(f"No hay fuentes raw de planificaci?n en {raw_dir}")
        profiles = [file_profile(path) for path in files]
        profile_by_name = {item["file"]: item for item in profiles}
        candidates = [path for path in files if path.name == "09_project_forecast.json"]
        if not candidates:
            candidates = [path for path in files if path.name == "09_project_forecast_v2.json"]
        if not candidates:
            candidates = [path for path in files if path.name == "09_project_forecast_v3_SAFE.json"]
        if not candidates:
            candidates = [path for path in files if path.name == "10_project_task_planning_all.json"]
        if candidates:
            source = candidates[0]
            reason = "Se elige project.forecast porque contiene planificaci?n por empleado/fecha; project.task queda como fallback agregado por tarea."
        else:
            ranked = sorted(
                files,
                key=lambda path: (
                    profile_by_name[path.name]["ids_unique"],
                    profile_by_name[path.name]["rows"],
                    1 if path.suffix.lower() == ".json" else 0,
                    path.stat().st_mtime,
                ),
                reverse=True,
            )
            source = ranked[0]
            reason = "Se elige la fuente con mayor cobertura de IDs/filas, priorizando JSON por trazabilidad relacional."
    selected_ids = file_profile(source)["id_set"]
    rows = []
    for item in profiles:
        overlap = len(selected_ids & item["id_set"])
        row = {key: value for key, value in item.items() if key != "id_set"}
        row["selected_file"] = source.name
        row["selected"] = item["file"] == source.name
        row["selection_reason"] = reason if row["selected"] else ""
        row["overlap_with_selected_ids"] = overlap
        row["is_subset_of_selected"] = overlap == len(item["id_set"]) if item["id_set"] else False
        rows.append(row)
    diagnostics = pd.DataFrame(rows)
    diagnostics.to_csv(SOURCE_DIAGNOSTICS_FILE, sep=";", encoding="utf-8-sig", index=False)
    return SourceDecision(selected=source, profiles=diagnostics, reason=reason)


def stable_hash(parts: list[Any]) -> str:
    text = "|".join(clean_text(part) for part in parts)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def safe_relative_path(path: Path, root: Path = ROOT_DIR) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def dedupe_raw(df: pd.DataFrame, source_file: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    result = df.copy()
    if "id" in result.columns:
        result["_dedupe_key"] = result["id"].map(clean_text).map(lambda value: f"id:{value}" if value else "")
    else:
        result["_dedupe_key"] = ""
    missing = result["_dedupe_key"].eq("")
    if missing.any():
        result.loc[missing, "_dedupe_key"] = result.loc[missing].apply(
            lambda row: "hash:" + stable_hash(
                [
                    row.get("user_id", ""),
                    row.get("project_id", ""),
                    row.get("name", ""),
                    row.get("date_start", ""),
                    row.get("date_deadline", ""),
                    row.get("date_end", ""),
                    row.get("planned_hours", ""),
                ]
            ),
            axis=1,
        )
    dup_mask = result.duplicated("_dedupe_key", keep="first")
    duplicate_rows = result[result.duplicated("_dedupe_key", keep=False)].copy()
    if duplicate_rows.empty:
        duplicates = pd.DataFrame(columns=["duplicate_key", "rows_involved", "source_id", "person", "project", "task", "dates", "hours", "action"])
    else:
        records = []
        for key, group in duplicate_rows.groupby("_dedupe_key"):
            records.append(
                {
                    "duplicate_key": key,
                    "rows_involved": "|".join(group.index.astype(str).tolist()),
                    "source_id": "|".join(group.get("id", pd.Series(dtype=str)).map(clean_text).tolist()),
                    "person": "|".join(group.get("user_id", pd.Series(dtype=str)).map(lambda value: safe_parse_many2one(value)[1] or clean_text(value)).tolist()),
                    "project": "|".join(group.get("project_id", pd.Series(dtype=str)).map(lambda value: safe_parse_many2one(value)[1] or clean_text(value)).tolist()),
                    "task": "|".join(group.get("name", pd.Series(dtype=str)).map(clean_text).tolist()),
                    "dates": "|".join((group.get("date_start", "") .astype(str) + "->" + group.get("date_deadline", "").astype(str)).tolist()),
                    "hours": "|".join(group.get("planned_hours", pd.Series(dtype=str)).map(clean_text).tolist()),
                    "action": "Se conserva la primera fila de la clave estable.",
                }
            )
        duplicates = pd.DataFrame(records)
    duplicates["source_file"] = source_file
    deduped = result[~dup_mask].drop(columns=["_dedupe_key"]).copy()
    duplicates.to_csv(DUPLICATES_FILE, sep=";", encoding="utf-8-sig", index=False)
    return deduped, duplicates


def load_department_lookup(actuals_path: Path = PROCESSED_DIR / "16_prc01_actuals_annual_detail.csv") -> dict[str, str]:
    if not actuals_path.exists():
        return {}
    usecols = ["pertsona", "saila"]
    try:
        actuals = pd.read_csv(actuals_path, sep=";", encoding="utf-8-sig", dtype=str, usecols=usecols).fillna("")
    except ValueError:
        return {}
    lookup: dict[str, str] = {}
    for person, rows in actuals.groupby(actuals["pertsona"].map(normalize_text)):
        if not person:
            continue
        departments = rows["saila"].map(clean_text)
        departments = departments[departments.ne("")]
        if not departments.empty:
            lookup[person] = departments.value_counts().index[0]
    return lookup


def derive_planning_status(row: pd.Series) -> str:
    active = normalize_bool(row.get("active", True))
    project_id, project_name = safe_parse_many2one(row.get("project_id", ""))
    task_name = clean_text(row.get("name", ""))
    if active and (project_id or project_name or task_name):
        return "asegurada"
    return "pendiente"


def date_bounds(row: pd.Series) -> tuple[pd.Timestamp | None, pd.Timestamp | None, str]:
    start = pd.to_datetime(clean_text(row.get("date_start", "")) or clean_text(row.get("create_date", "")), errors="coerce")
    end = pd.to_datetime(
        clean_text(row.get("date_deadline", ""))
        or clean_text(row.get("date_end", ""))
        or clean_text(row.get("write_date", ""))
        or clean_text(row.get("date_start", ""))
        or clean_text(row.get("create_date", "")),
        errors="coerce",
    )
    if pd.isna(start) and not pd.isna(end):
        start = end
    if pd.isna(end) and not pd.isna(start):
        end = start
    if pd.isna(start) or pd.isna(end):
        return None, None, "invalid_dates"
    start = pd.Timestamp(start).normalize()
    end = pd.Timestamp(end).normalize()
    if end < start:
        start, end = end, start
    if start.year == end.year and start.month == end.month:
        return start, end, "single_month"
    return start, end, "natural_days"


def month_allocations(start: pd.Timestamp, end: pd.Timestamp, hours: float) -> list[tuple[int, int, float, str]]:
    if start.year == end.year and start.month == end.month:
        return [(int(start.year), int(start.month), round(hours, 6), "single_month")]
    total_days = int((end - start).days) + 1
    rows: list[tuple[int, int, float, str]] = []
    cursor = start
    allocated = 0.0
    while cursor <= end:
        month_end = min(end, cursor + pd.offsets.MonthEnd(0))
        days = int((month_end - cursor).days) + 1
        value = round(hours * days / total_days, 6)
        rows.append((int(cursor.year), int(cursor.month), value, "natural_days"))
        allocated += value
        cursor = month_end + pd.Timedelta(days=1)
    if rows:
        diff = round(hours - allocated, 6)
        year, month, value, method = rows[-1]
        rows[-1] = (year, month, round(value + diff, 6), method)
    return rows


def row_forecast_hours(row: pd.Series) -> tuple[float | None, float, float, str]:
    quantity_text = clean_text(row.get("quantity", ""))
    effective = to_float(row.get("effective_hours", ""), 0.0) or 0.0
    remaining = to_float(row.get("remaining_hours", ""), 0.0) or 0.0
    if quantity_text:
        quantity = to_float(quantity_text, None)
        if quantity is not None:
            return quantity, effective, remaining, "quantity"
    return effective + remaining, effective, remaining, "effective_plus_remaining"


def forecast_date_bounds(row: pd.Series) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    start = pd.to_datetime(clean_text(row.get("date_start", "")), errors="coerce")
    end = pd.to_datetime(clean_text(row.get("date_end", "")), errors="coerce")
    if pd.isna(start):
        return None, None
    start = pd.Timestamp(start).normalize()
    if pd.isna(end):
        end = start + pd.offsets.MonthEnd(0)
    end = pd.Timestamp(end).normalize()
    if end < start:
        start, end = end, start
    return start, end


def build_forecast_planning_dataset(raw: pd.DataFrame, decision: SourceDecision, raw_rows: int, raw_hours_total: float, transformation_timestamp: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    department_lookup = load_department_lookup()
    invalid_records: list[dict[str, Any]] = []
    unmatched_people: list[dict[str, Any]] = []
    processed_records: list[dict[str, Any]] = []
    reconciliation_records: list[dict[str, Any]] = []

    for _, row in raw.iterrows():
        source_id = clean_text(row.get("id", ""))
        hours, imputed_hours, remaining_hours, formula = row_forecast_hours(row)
        employee_id, employee_name = safe_parse_many2one(row.get("employee_id", ""))
        user_id, user_name = safe_parse_many2one(row.get("user_id", ""))
        project_id, project_name = safe_parse_many2one(row.get("project_id", ""))
        task_id, task_name = safe_parse_many2one(row.get("task_id", ""))
        person_id = employee_id or user_id
        person_name = employee_name or user_name or "Persona pendiente"
        if not task_name:
            task_name = clean_text(row.get("name", "")) or "Sin tarea"
        start, end = forecast_date_bounds(row)
        errors = []
        if hours is None:
            errors.append("planned_hours no numerico")
        elif hours < 0:
            errors.append("planned_hours negativo")
        if not source_id:
            errors.append("id de Odoo ausente")
        if start is None or end is None:
            errors.append("fechas invalidas")
        if errors:
            invalid_records.append(
                {
                    "source_file": decision.selected.name,
                    "source_row_id": clean_text(row.get("_source_row_id", "")),
                    "source_id": source_id,
                    "person": person_name,
                    "project": project_name,
                    "task": task_name,
                    "planned_hours": clean_text(row.get("quantity", "")) or clean_text(row.get("remaining_hours", "")),
                    "date_start": clean_text(row.get("date_start", "")),
                    "date_end": clean_text(row.get("date_end", "")),
                    "errors": "; ".join(errors),
                }
            )
            continue
        assert hours is not None and start is not None and end is not None
        person_key = normalize_text(person_name)
        department = department_lookup.get(person_key, "Pendiente")
        if department == "Pendiente":
            unmatched_people.append(
                {
                    "odoo_person_id": person_id,
                    "odoo_person_name": person_name,
                    "user": user_name,
                    "email": "",
                    "project": project_name or "Sin proyecto",
                    "task": task_name,
                    "hours": hours,
                    "reason": "No encontrado en horas reales por nombre normalizado.",
                }
            )
        processed_records.append(
            {
                "planning_id": f"FORECAST-{source_id}",
                "active": "TRUE",
                "planning_status": "asegurada",
                "source_system": "odoo",
                "source_model": "project.forecast",
                "source_id": source_id,
                "source_name": clean_text(row.get("display_name", "")) or task_name,
                "date_start": start.date().isoformat(),
                "date_end": end.date().isoformat(),
                "year": int(start.year),
                "month": int(start.month),
                "month_number": int(start.month),
                "person_key": person_key,
                "person_id": person_id,
                "person_name": person_name,
                "department_name": department,
                "project_id": project_id,
                "project_name": project_name or "Sin proyecto",
                "task_id": task_id,
                "task_name": task_name,
                "planned_hours": hours,
                "probability": 1.0,
                "weighted_planned_hours": hours,
                "unidad_destino": "",
                "unidad_destino_label": "",
                "naturaleza_trabajo": "",
                "naturaleza_trabajo_label": "",
                "grupo_gestion": "",
                "classification_rule_id": "",
                "classification_status": "",
                "source_file": decision.selected.name,
                "raw_source_file": safe_relative_path(decision.selected),
                "source_row_id": clean_text(row.get("_source_row_id", "")),
                "monthly_allocation_method": "forecast_monthly",
                "created_at": clean_text(row.get("create_date", "")),
                "updated_at": clean_text(row.get("write_date", "")),
                "transformation_timestamp": transformation_timestamp,
                "raw_rows": raw_rows,
                "processed_rows": "",
                "raw_hours": raw_hours_total,
                "processed_hours": "",
                "imputed_hours": imputed_hours,
                "remaining_hours": remaining_hours,
                "raw_planned_hours": hours,
            }
        )
        reconciliation_records.append(
            {
                "source_id": source_id,
                "raw_hours": hours,
                "distributed_hours": hours,
                "difference": 0.0,
                "months": 1,
                "allocation_method": formula,
            }
        )
    processed = pd.DataFrame(processed_records, columns=PLANNING_PROCESSED_COLUMNS)
    invalid = pd.DataFrame(invalid_records)
    unmatched = pd.DataFrame(unmatched_people).drop_duplicates() if unmatched_people else pd.DataFrame(columns=["odoo_person_id", "odoo_person_name", "user", "email", "project", "task", "hours", "reason"])
    reconciliation = pd.DataFrame(reconciliation_records)
    return processed, invalid, unmatched, reconciliation


def build_planning_dataset(source: Path | None = None) -> dict[str, Any]:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    decision = resolve_planning_source(RAW_DIR, source)
    raw = read_raw_file(decision.selected)
    raw["_source_row_id"] = raw.index.astype(str)
    raw_rows = len(raw)
    raw_hours_total = float(raw_planned_hours(raw).sum())
    raw, duplicates = dedupe_raw(raw, decision.selected.name)
    department_lookup = load_department_lookup()
    invalid_records: list[dict[str, Any]] = []
    unmatched_people: list[dict[str, Any]] = []
    processed_records: list[dict[str, Any]] = []
    reconciliation_records: list[dict[str, Any]] = []
    transformation_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if decision.selected.name.startswith("09_project_forecast"):
        processed, invalid, unmatched, reconciliation = build_forecast_planning_dataset(raw, decision, raw_rows, raw_hours_total, transformation_timestamp)
        processed_hours_total = float(processed["planned_hours"].sum()) if not processed.empty else 0.0
        if not processed.empty:
            processed["processed_rows"] = len(processed)
            processed["processed_hours"] = processed_hours_total
        invalid.to_csv(INVALID_ROWS_FILE, sep=";", encoding="utf-8-sig", index=False)
        unmatched.to_csv(UNMATCHED_PEOPLE_FILE, sep=";", encoding="utf-8-sig", index=False)
        reconciliation.to_csv(MONTHLY_RECONCILIATION_FILE, sep=";", encoding="utf-8-sig", index=False)
        processed.to_csv(PROCESSED_PLANNING_FILE, sep=";", encoding="utf-8-sig", index=False)
        valid_raw_hours = raw_hours_total - (float(invalid["planned_hours"].map(lambda v: to_float(v, 0.0)).sum()) if not invalid.empty and "planned_hours" in invalid else 0.0)
        diff = round(valid_raw_hours - processed_hours_total, 6)
        if abs(diff) > 0.001:
            raise RuntimeError(f"Reconciliacion de planificacion fallida: raw valido={valid_raw_hours}, procesado={processed_hours_total}, diferencia={diff}")
        return {
            "source": decision.selected,
            "reason": decision.reason,
            "raw_rows": raw_rows,
            "valid_rows": int(len(raw) - len(invalid)),
            "processed_rows": int(len(processed)),
            "raw_hours": raw_hours_total,
            "processed_hours": processed_hours_total,
            "excluded_hours": raw_hours_total - valid_raw_hours,
            "difference": diff,
            "duplicates_removed": int(len(duplicates)),
            "invalid_rows": int(len(invalid)),
            "unmatched_people": int(len(unmatched)),
            "output": PROCESSED_PLANNING_FILE,
        }

    for _, row in raw.iterrows():
        source_id = clean_text(row.get("id", ""))
        hours = to_float(row.get("planned_hours", ""), None)
        person_id, person_name = safe_parse_many2one(row.get("user_id", ""))
        project_id, project_name = safe_parse_many2one(row.get("project_id", ""))
        parent_id, parent_name = safe_parse_many2one(row.get("parent_id", ""))
        task_name = clean_text(row.get("name", "")) or "Sin tarea"
        start, end, date_method = date_bounds(row)
        errors = []
        if hours is None:
            errors.append("planned_hours no numerico")
        elif hours < 0:
            errors.append("planned_hours negativo")
        if not source_id:
            errors.append("id de Odoo ausente")
        if start is None or end is None:
            errors.append("fechas invalidas")
        if errors:
            invalid_records.append(
                {
                    "source_file": decision.selected.name,
                    "source_row_id": clean_text(row.get("_source_row_id", "")),
                    "source_id": source_id,
                    "person": person_name,
                    "project": project_name,
                    "task": task_name,
                    "planned_hours": clean_text(row.get("planned_hours", "")),
                    "date_start": clean_text(row.get("date_start", "")),
                    "date_end": clean_text(row.get("date_end", "")),
                    "errors": "; ".join(errors),
                }
            )
            continue
        assert hours is not None and start is not None and end is not None
        if not person_name:
            person_name = "Persona pendiente"
        person_key = normalize_text(person_name)
        department = department_lookup.get(person_key, "Pendiente")
        if department == "Pendiente":
            unmatched_people.append(
                {
                    "odoo_person_id": person_id,
                    "odoo_person_name": person_name,
                    "user": person_name,
                    "email": "",
                    "project": project_name or "Sin proyecto",
                    "task": task_name,
                    "hours": hours,
                    "reason": "No encontrado en horas reales por nombre normalizado.",
                }
            )
        if not project_name:
            project_name = "Sin proyecto"
        if not project_id:
            project_id = ""
        if not parent_name:
            parent_name = ""
        status = derive_planning_status(row)
        probability = 1.0
        allocations = month_allocations(start, end, hours)
        distributed = 0.0
        for year, month, allocated_hours, allocation_method in allocations:
            distributed += allocated_hours
            planning_id = f"ODOO-{source_id}-{year}-{month:02d}" if source_id else f"ODOO-HASH-{stable_hash([person_name, project_name, task_name, year, month, hours])}"
            processed_records.append(
                {
                    "planning_id": planning_id,
                    "active": "TRUE" if normalize_bool(row.get("active", True)) else "FALSE",
                    "planning_status": status,
                    "source_system": "odoo",
                    "source_model": "project.task",
                    "source_id": source_id,
                    "source_name": task_name,
                    "date_start": start.date().isoformat(),
                    "date_end": end.date().isoformat(),
                    "year": year,
                    "month": month,
                    "month_number": month,
                    "person_key": person_key,
                    "person_id": person_id,
                    "person_name": person_name,
                    "department_name": department,
                    "project_id": project_id,
                    "project_name": project_name,
                    "task_id": source_id,
                    "task_name": task_name,
                    "planned_hours": allocated_hours,
                    "probability": probability,
                    "weighted_planned_hours": allocated_hours * probability,
                    "unidad_destino": "",
                    "unidad_destino_label": "",
                    "naturaleza_trabajo": "",
                    "naturaleza_trabajo_label": "",
                    "grupo_gestion": "",
                    "classification_rule_id": "",
                    "classification_status": "",
                    "source_file": decision.selected.name,
                    "raw_source_file": safe_relative_path(decision.selected),
                    "source_row_id": clean_text(row.get("_source_row_id", "")),
                    "monthly_allocation_method": allocation_method if date_method != "single_month" else "single_month",
                    "created_at": clean_text(row.get("create_date", "")),
                    "updated_at": clean_text(row.get("write_date", "")),
                    "transformation_timestamp": transformation_timestamp,
                    "raw_rows": raw_rows,
                    "processed_rows": "",
                    "raw_hours": raw_hours_total,
                    "processed_hours": "",
                }
            )
        reconciliation_records.append(
            {
                "source_id": source_id,
                "raw_hours": hours,
                "distributed_hours": round(distributed, 6),
                "difference": round(hours - distributed, 6),
                "months": len(allocations),
                "allocation_method": allocations[0][3] if allocations else date_method,
            }
        )

    processed = pd.DataFrame(processed_records, columns=PLANNING_PROCESSED_COLUMNS)
    processed_hours_total = float(processed["planned_hours"].sum()) if not processed.empty else 0.0
    if not processed.empty:
        processed["processed_rows"] = len(processed)
        processed["processed_hours"] = processed_hours_total
    invalid = pd.DataFrame(invalid_records)
    unmatched = pd.DataFrame(unmatched_people).drop_duplicates() if unmatched_people else pd.DataFrame(columns=["odoo_person_id", "odoo_person_name", "user", "email", "project", "task", "hours", "reason"])
    reconciliation = pd.DataFrame(reconciliation_records)
    invalid.to_csv(INVALID_ROWS_FILE, sep=";", encoding="utf-8-sig", index=False)
    unmatched.to_csv(UNMATCHED_PEOPLE_FILE, sep=";", encoding="utf-8-sig", index=False)
    reconciliation.to_csv(MONTHLY_RECONCILIATION_FILE, sep=";", encoding="utf-8-sig", index=False)
    processed.to_csv(PROCESSED_PLANNING_FILE, sep=";", encoding="utf-8-sig", index=False)

    valid_raw_hours = raw_hours_total - (float(invalid["planned_hours"].map(lambda v: to_float(v, 0.0)).sum()) if not invalid.empty and "planned_hours" in invalid else 0.0)
    diff = round(valid_raw_hours - processed_hours_total, 6)
    if abs(diff) > 0.001:
        raise RuntimeError(f"Reconciliación de planificación fallida: raw válido={valid_raw_hours}, procesado={processed_hours_total}, diferencia={diff}")
    return {
        "source": decision.selected,
        "reason": decision.reason,
        "raw_rows": raw_rows,
        "valid_rows": int(len(raw) - len(invalid)),
        "processed_rows": int(len(processed)),
        "raw_hours": raw_hours_total,
        "processed_hours": processed_hours_total,
        "excluded_hours": raw_hours_total - valid_raw_hours,
        "difference": diff,
        "duplicates_removed": int(len(duplicates)),
        "invalid_rows": int(len(invalid)),
        "unmatched_people": int(len(unmatched)),
        "output": PROCESSED_PLANNING_FILE,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Construye el dataset procesado de planificación PRC-01 desde raw Odoo.")
    parser.add_argument("--source", type=Path, default=None, help="Fuente raw explícita CSV/JSON.")
    args = parser.parse_args(argv)
    result = build_planning_dataset(args.source)
    for key, value in result.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
