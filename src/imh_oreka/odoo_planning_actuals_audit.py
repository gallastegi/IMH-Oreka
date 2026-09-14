from __future__ import annotations

import csv
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable


STANDARD_CONTEXT = {"active_test": True, "lang": "es_ES", "tz": "Europe/Madrid"}
INACTIVE_CONTEXT = {"active_test": False, "lang": "es_ES", "tz": "Europe/Madrid"}

FIELD_ATTRIBUTES = ["string", "type", "relation", "store", "readonly", "required"]

FORECAST_LOGICAL_CANDIDATES: dict[str, list[str]] = {
    "id": ["id"],
    "active": ["active"],
    "employee": ["employee_id"],
    "user": ["user_id"],
    "resource": ["resource_id"],
    "project": ["project_id"],
    "task": ["task_id"],
    "start_date": ["date_start", "start_date"],
    "end_date": ["date_end", "end_date"],
    "planned_hours": ["quantity", "planned_hours"],
    "effective_hours": ["effective_hours", "imputed_hours", "hours_spent"],
    "remaining_hours": ["remaining_hours"],
    "company": ["company_id"],
    "create_date": ["create_date"],
    "write_date": ["write_date"],
    "name": ["name", "display_name"],
}

ANALYTIC_LOGICAL_CANDIDATES: dict[str, list[str]] = {
    "id": ["id"],
    "date": ["date"],
    "employee": ["employee_id"],
    "user": ["user_id"],
    "project": ["project_id"],
    "task": ["task_id"],
    "account": ["account_id"],
    "duration": ["unit_amount"],
    "description": ["name"],
    "company": ["company_id"],
    "create_date": ["create_date"],
    "write_date": ["write_date"],
}


def json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=json_default), encoding="utf-8")


def flatten_cell(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        if len(value) == 2 and isinstance(value[0], int):
            return value[1]
        return json.dumps(value, ensure_ascii=False, default=json_default)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, default=json_default)
    return value


def save_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        seen: set[str] = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    fieldnames.append(key)
                    seen.add(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: flatten_cell(row.get(key, "")) for key in fieldnames})


def many2one_id(value: Any) -> int | None:
    if isinstance(value, (list, tuple)) and value and isinstance(value[0], int):
        return int(value[0])
    if isinstance(value, int):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def many2one_name(value: Any) -> str:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return str(value[1] or "")
    if isinstance(value, str) and not value.strip().isdigit():
        return value
    return ""


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(text[:19], fmt).date()
        except ValueError:
            continue
    return None


def duration_hhmm_to_minutes(value: Any) -> int:
    if value is None:
        return 0
    text = str(value).strip()
    match = re.fullmatch(r"([+-]?\d+):([0-5]\d)", text)
    if not match:
        raise ValueError(f"Duracion HH:MM no valida: {value!r}")
    hours = int(match.group(1))
    minutes = int(match.group(2))
    sign = -1 if hours < 0 else 1
    return hours * 60 + sign * minutes


def minutes_to_duration_hhmm(minutes: int | float) -> str:
    total = int(round(float(minutes)))
    sign = "-" if total < 0 else ""
    total = abs(total)
    return f"{sign}{total // 60:02d}:{total % 60:02d}"


def odoo_hours_to_minutes(value: Any) -> int:
    if value in (None, False, ""):
        return 0
    if isinstance(value, str) and ":" in value:
        return duration_hhmm_to_minutes(value)
    numeric = float(value)
    return int(round(numeric * 60))


def minutes_to_hours(minutes: int | float) -> float:
    return float(minutes) / 60.0


def field_meta(fields: dict[str, dict[str, Any]], field_name: str) -> dict[str, Any]:
    return fields.get(field_name, {})


def build_field_mapping(fields: dict[str, dict[str, Any]], candidates: dict[str, list[str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for logical, names in candidates.items():
        selected = next((name for name in names if name in fields), "")
        meta = field_meta(fields, selected)
        rows.append(
            {
                "logical_field": logical,
                "odoo_field": selected,
                "label": meta.get("string", ""),
                "type": meta.get("type", ""),
                "relation": meta.get("relation", ""),
                "stored": meta.get("store", ""),
                "available": bool(selected),
                "selected_for_extraction": bool(selected),
                "notes": "" if selected else f"No encontrado. Candidatos: {', '.join(names)}",
            }
        )
    return rows


def mapping_field(mapping: list[dict[str, Any]], logical_field: str, required: bool = True) -> str:
    for row in mapping:
        if row["logical_field"] == logical_field and row.get("odoo_field"):
            return str(row["odoo_field"])
    if required:
        raise RuntimeError(f"No hay campo Odoo para {logical_field}")
    return ""


def extraction_fields(mapping: list[dict[str, Any]], extra: Iterable[str] = ()) -> list[str]:
    fields = ["id"]
    for row in mapping:
        field = str(row.get("odoo_field") or "")
        if field and field not in fields:
            fields.append(field)
    for field in extra:
        if field and field not in fields:
            fields.append(field)
    return fields


@dataclass
class ExtractResult:
    ids: list[int]
    rows: list[dict[str, Any]]
    search_count: int
    metadata: dict[str, Any]


class ReadOnlyProtocol:
    db: str
    uid: int | None

    def execute(self, model: str, method: str, args: list[Any] | None = None, kwargs: dict[str, Any] | None = None) -> Any: ...


def read_all_by_domain(
    client: ReadOnlyProtocol,
    model: str,
    domain: list[Any],
    fields: list[str],
    context: dict[str, Any],
    batch_size: int = 100,
    order: str = "id",
) -> ExtractResult:
    search_count = int(client.execute(model, "search_count", args=[domain], kwargs={"context": context}))
    ids = [int(value) for value in client.execute(model, "search", args=[domain], kwargs={"context": context, "order": order})]
    if search_count != len(ids):
        raise RuntimeError(f"{model}: search_count={search_count} len(ids)={len(ids)}")
    rows: list[dict[str, Any]] = []
    for start in range(0, len(ids), batch_size):
        chunk = ids[start : start + batch_size]
        rows.extend(client.execute(model, "read", args=[chunk], kwargs={"fields": fields, "context": context, "load": "_classic_write"}))
    row_ids = [int(row["id"]) for row in rows if "id" in row]
    if len(rows) != len(ids):
        raise RuntimeError(f"{model}: len(rows)={len(rows)} len(ids)={len(ids)}")
    if set(row_ids) != set(ids):
        missing = sorted(set(ids) - set(row_ids))
        extra = sorted(set(row_ids) - set(ids))
        raise RuntimeError(f"{model}: IDs no reconciliados. missing={missing} extra={extra}")
    duplicates = sorted([item for item, count in _counts(row_ids).items() if count > 1])
    metadata = {
        "model": model,
        "domain": domain,
        "context": context,
        "search_count": search_count,
        "ids_received": len(ids),
        "rows_received": len(rows),
        "unique_ids": len(set(row_ids)),
        "duplicate_ids": duplicates,
        "extraction_status": "PASS" if not duplicates else "FAIL_DUPLICATES",
    }
    return ExtractResult(ids=ids, rows=rows, search_count=search_count, metadata=metadata)


def _counts(values: Iterable[int]) -> dict[int, int]:
    result: dict[int, int] = defaultdict(int)
    for value in values:
        result[int(value)] += 1
    return dict(result)


def rows_minutes(rows: list[dict[str, Any]], hour_field: str) -> int:
    return sum(odoo_hours_to_minutes(row.get(hour_field)) for row in rows)


def minmax_dates(rows: list[dict[str, Any]], field: str) -> tuple[str, str]:
    values = sorted(d.isoformat() for d in (parse_date(row.get(field)) for row in rows) if d)
    if not values:
        return "", ""
    return values[0], values[-1]


def enrich_forecast_metadata(metadata: dict[str, Any], rows: list[dict[str, Any]], mapping: list[dict[str, Any]]) -> dict[str, Any]:
    planned_field = mapping_field(mapping, "planned_hours", required=False)
    effective_field = mapping_field(mapping, "effective_hours", required=False)
    remaining_field = mapping_field(mapping, "remaining_hours", required=False)
    start_field = mapping_field(mapping, "start_date", required=False)
    end_field = mapping_field(mapping, "end_date", required=False)
    active_field = mapping_field(mapping, "active", required=False)
    planned_minutes = rows_minutes(rows, planned_field) if planned_field else 0
    effective_minutes = rows_minutes(rows, effective_field) if effective_field else 0
    remaining_minutes = rows_minutes(rows, remaining_field) if remaining_field else 0
    min_start, max_start = minmax_dates(rows, start_field) if start_field else ("", "")
    min_end, max_end = minmax_dates(rows, end_field) if end_field else ("", "")
    active_records = sum(1 for row in rows if bool(row.get(active_field, True))) if active_field else len(rows)
    metadata.update(
        {
            "planned_minutes": planned_minutes,
            "planned_hours": minutes_to_hours(planned_minutes),
            "effective_minutes": effective_minutes,
            "effective_hours": minutes_to_hours(effective_minutes),
            "remaining_minutes": remaining_minutes,
            "remaining_hours": minutes_to_hours(remaining_minutes),
            "min_start_date": min_start,
            "max_start_date": max_start,
            "min_end_date": min_end,
            "max_end_date": max_end,
            "active_records": active_records,
            "inactive_records": len(rows) - active_records,
        }
    )
    return metadata


def build_annual_forecast_domain(employee_field: str, start_field: str, employee_id: int, year: int) -> list[Any]:
    return [[employee_field, "=", employee_id], [start_field, ">=", f"{year}-01-01"], [start_field, "<", f"{year + 1}-01-01"]]


def build_current_forecast_domain(employee_field: str, start_field: str, end_field: str, employee_id: int, reference_date: str) -> list[Any]:
    return [[employee_field, "=", employee_id], [start_field, "<=", reference_date], [end_field, ">=", reference_date]]


def build_annual_actuals_domain(employee_field: str, date_field: str, employee_id: int, year: int) -> list[Any]:
    return [[employee_field, "=", employee_id], [date_field, ">=", f"{year}-01-01"], [date_field, "<", f"{year + 1}-01-01"]]


def normalize_fact_forecasts(rows: list[dict[str, Any]], mapping: list[dict[str, Any]], source_file: str, extracted_at: str) -> list[dict[str, Any]]:
    f = lambda logical, required=True: mapping_field(mapping, logical, required=required)
    fields = {
        "employee": f("employee"),
        "user": f("user", False),
        "resource": f("resource", False),
        "project": f("project"),
        "task": f("task", False),
        "start": f("start_date"),
        "end": f("end_date", False),
        "planned": f("planned_hours"),
        "effective": f("effective_hours", False),
        "remaining": f("remaining_hours", False),
        "active": f("active", False),
        "company": f("company", False),
        "create_date": f("create_date", False),
        "write_date": f("write_date", False),
    }
    result: list[dict[str, Any]] = []
    for row in rows:
        start = parse_date(row.get(fields["start"]))
        end = parse_date(row.get(fields["end"])) if fields["end"] else None
        planned_minutes = odoo_hours_to_minutes(row.get(fields["planned"]))
        effective_minutes = odoo_hours_to_minutes(row.get(fields["effective"])) if fields["effective"] else 0
        remaining_minutes = odoo_hours_to_minutes(row.get(fields["remaining"])) if fields["remaining"] else planned_minutes - effective_minutes
        employee_id = many2one_id(row.get(fields["employee"]))
        employee_name = many2one_name(row.get(fields["employee"]))
        user_id = many2one_id(row.get(fields["user"])) if fields["user"] else None
        resource_id = many2one_id(row.get(fields["resource"])) if fields["resource"] else None
        project_id = many2one_id(row.get(fields["project"]))
        task_id = many2one_id(row.get(fields["task"])) if fields["task"] else None
        result.append(
            {
                "forecast_id": int(row["id"]),
                "employee_id": employee_id,
                "user_id": user_id,
                "resource_id": resource_id,
                "person_key": f"employee:{employee_id}" if employee_id else f"user:{user_id}" if user_id else employee_name,
                "person_name": employee_name,
                "project_id": project_id,
                "project_name": many2one_name(row.get(fields["project"])),
                "task_id": task_id,
                "task_name": many2one_name(row.get(fields["task"])) if fields["task"] else "",
                "start_date": start.isoformat() if start else "",
                "end_date": end.isoformat() if end else "",
                "year": start.year if start else "",
                "month": start.month if start else "",
                "planned_minutes": planned_minutes,
                "planned_hours": minutes_to_hours(planned_minutes),
                "effective_minutes_odoo": effective_minutes,
                "effective_hours_odoo": minutes_to_hours(effective_minutes),
                "remaining_minutes_odoo": remaining_minutes,
                "remaining_hours_odoo": minutes_to_hours(remaining_minutes),
                "active": bool(row.get(fields["active"], True)) if fields["active"] else True,
                "company_id": many2one_id(row.get(fields["company"])) if fields["company"] else None,
                "create_date": row.get(fields["create_date"], "") if fields["create_date"] else "",
                "write_date": row.get(fields["write_date"], "") if fields["write_date"] else "",
                "source_model": "project.forecast",
                "source_file": source_file,
                "extraction_timestamp": extracted_at,
            }
        )
    return result


def normalize_fact_actuals(rows: list[dict[str, Any]], mapping: list[dict[str, Any]], source_file: str) -> list[dict[str, Any]]:
    f = lambda logical, required=True: mapping_field(mapping, logical, required=required)
    employee_field = f("employee", False)
    user_field = f("user", False)
    project_field = f("project", False)
    task_field = f("task", False)
    date_field = f("date")
    duration_field = f("duration")
    description_field = f("description", False)
    result: list[dict[str, Any]] = []
    for row in rows:
        employee_id = many2one_id(row.get(employee_field)) if employee_field else None
        person_name = many2one_name(row.get(employee_field)) if employee_field else ""
        actual_minutes = odoo_hours_to_minutes(row.get(duration_field))
        result.append(
            {
                "analytic_line_id": int(row["id"]),
                "employee_id": employee_id,
                "user_id": many2one_id(row.get(user_field)) if user_field else None,
                "person_name": person_name,
                "project_id": many2one_id(row.get(project_field)) if project_field else None,
                "project_name": many2one_name(row.get(project_field)) if project_field else "",
                "task_id": many2one_id(row.get(task_field)) if task_field else None,
                "task_name": many2one_name(row.get(task_field)) if task_field else "",
                "date": parse_date(row.get(date_field)).isoformat() if parse_date(row.get(date_field)) else "",
                "actual_minutes": actual_minutes,
                "actual_hours": minutes_to_hours(actual_minutes),
                "description": row.get(description_field, "") if description_field else "",
                "source_model": "account.analytic.line",
                "source_file": source_file,
            }
        )
    return result


def crosses_month(row: dict[str, Any]) -> bool:
    start = parse_date(row.get("start_date"))
    end = parse_date(row.get("end_date"))
    if not start or not end:
        return False
    return (start.year, start.month) != (end.year, end.month)


def reconcile_planning_actuals(forecasts: list[dict[str, Any]], actuals: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    forecast_by_id = {int(row["forecast_id"]): row for row in forecasts}
    assigned_actuals: set[int] = set()
    conflicts: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    consumed_by_forecast: dict[int, int] = defaultdict(int)

    for actual in actuals:
        actual_id = int(actual["analytic_line_id"])
        actual_date = parse_date(actual.get("date"))
        candidates: list[tuple[int, str, int]] = []
        for forecast in forecasts:
            if actual.get("employee_id") and forecast.get("employee_id") and actual["employee_id"] != forecast["employee_id"]:
                continue
            start = parse_date(forecast.get("start_date"))
            end = parse_date(forecast.get("end_date")) or start
            if not actual_date or not start or not end or not (start <= actual_date <= end):
                continue
            same_project = actual.get("project_id") and actual.get("project_id") == forecast.get("project_id")
            same_task = actual.get("task_id") and actual.get("task_id") == forecast.get("task_id")
            if same_project and same_task:
                quality = "exact_employee_project_task_period"
                score = 1
            elif same_project:
                quality = "employee_project_period"
                score = 2
            elif same_task:
                quality = "employee_task_period"
                score = 3
            else:
                continue
            interval_days = (end - start).days if end and start else 999999
            candidates.append((int(forecast["forecast_id"]), quality, score * 1000000 + interval_days))
        if not candidates:
            links.append({**actual, "forecast_id": "", "match_quality": "no_planning_match", "assigned_minutes": int(actual["actual_minutes"])})
            continue
        best_score = min(item[2] for item in candidates)
        best = [item for item in candidates if item[2] == best_score]
        if len(best) > 1:
            conflicts.append(
                {
                    "analytic_line_id": actual_id,
                    "actual_minutes": int(actual["actual_minutes"]),
                    "candidate_forecast_ids": ",".join(str(item[0]) for item in best),
                    "match_quality": "multiple_forecast_conflict",
                }
            )
            links.append({**actual, "forecast_id": "", "match_quality": "multiple_forecast_conflict", "assigned_minutes": 0})
            continue
        forecast_id, quality, _ = best[0]
        assigned_actuals.add(actual_id)
        consumed_by_forecast[forecast_id] += int(actual["actual_minutes"])
        links.append({**actual, "forecast_id": forecast_id, "match_quality": quality, "assigned_minutes": int(actual["actual_minutes"])})

    planning_records_with_actuals = sum(1 for value in consumed_by_forecast.values() if value)
    planning_records_without_actuals = len(forecasts) - planning_records_with_actuals
    planning_consumed = sum(consumed_by_forecast.values())
    planning_remaining = 0
    planning_overrun = 0
    for forecast_id, forecast in forecast_by_id.items():
        remaining = int(forecast.get("planned_minutes", 0)) - int(consumed_by_forecast.get(forecast_id, 0))
        if remaining >= 0:
            planning_remaining += remaining
        else:
            planning_overrun += abs(remaining)
    with_planning = sum(int(row["assigned_minutes"]) for row in links if row["match_quality"] not in {"no_planning_match", "multiple_forecast_conflict"})
    without_planning = sum(int(row["actual_minutes"]) for row in links if row["match_quality"] == "no_planning_match")
    conflict_minutes = sum(int(row["actual_minutes"]) for row in links if row["match_quality"] == "multiple_forecast_conflict")
    exact_minutes = sum(int(row["assigned_minutes"]) for row in links if row["match_quality"] == "exact_employee_project_task_period")
    approx_minutes = sum(int(row["assigned_minutes"]) for row in links if row["match_quality"] in {"employee_project_period", "employee_task_period"})
    total_actual = sum(int(row["actual_minutes"]) for row in actuals)
    summary = {
        "planning_records_annual": len(forecasts),
        "planning_minutes_annual": sum(int(row.get("planned_minutes", 0)) for row in forecasts),
        "actual_records_annual": len(actuals),
        "actual_minutes_annual": total_actual,
        "actual_minutes_with_planning": with_planning,
        "actual_minutes_without_planning": without_planning,
        "actual_hours_with_planning": minutes_to_hours(with_planning),
        "actual_hours_without_planning": minutes_to_hours(without_planning),
        "planning_records_with_actuals": planning_records_with_actuals,
        "planning_records_without_actuals": planning_records_without_actuals,
        "planning_minutes_consumed": planning_consumed,
        "planning_minutes_remaining": planning_remaining,
        "planning_minutes_overrun": planning_overrun,
        "match_exact_minutes": exact_minutes,
        "match_approximate_minutes": approx_minutes,
        "conflict_minutes": conflict_minutes,
        "unmatched_minutes": without_planning,
        "actual_identity_difference": total_actual - with_planning - without_planning - conflict_minutes,
    }
    return links, conflicts, summary


def waterfall_row(stage: str, rows: list[dict[str, Any]], id_field: str, minute_field: str, previous_count: int | None = None, previous_minutes: int | None = None, reason: str = "") -> dict[str, Any]:
    row_count = len(rows)
    unique_id_count = len({row.get(id_field) for row in rows})
    planned_hours = minutes_to_hours(sum(int(row.get(minute_field, 0) or 0) for row in rows))
    minutes = sum(int(row.get(minute_field, 0) or 0) for row in rows)
    return {
        "stage": stage,
        "row_count": row_count,
        "unique_id_count": unique_id_count,
        "planned_hours": planned_hours,
        "rows_removed": "" if previous_count is None else previous_count - row_count,
        "hours_removed": "" if previous_minutes is None else minutes_to_hours(previous_minutes - minutes),
        "reason": reason,
    }


def summarize_by_project(actuals: list[dict[str, Any]], expected: dict[int, int] | None = None) -> list[dict[str, Any]]:
    expected = expected or {}
    grouped: dict[tuple[Any, str], dict[str, Any]] = {}
    for row in actuals:
        key = (row.get("project_id"), row.get("project_name", ""))
        item = grouped.setdefault(
            key,
            {
                "project_id": row.get("project_id"),
                "project_name": row.get("project_name", ""),
                "analytic_line_count": 0,
                "actual_minutes": 0,
            },
        )
        item["analytic_line_count"] += 1
        item["actual_minutes"] += int(row.get("actual_minutes", 0))
    result = []
    for item in grouped.values():
        expected_value = expected.get(item["project_id"], "")
        difference = "" if expected_value == "" else item["actual_minutes"] - int(expected_value)
        item["actual_hours"] = minutes_to_hours(item["actual_minutes"])
        item["expected_from_screenshot_when_identifiable"] = expected_value
        item["difference"] = difference
        item["validation_status"] = "UNKNOWN" if expected_value == "" else "PASS" if difference == 0 else "FAIL"
        result.append(item)
    return sorted(result, key=lambda row: row["actual_minutes"], reverse=True)


def minute_difference_status(actual: int, expected: int, tolerance_minutes: int = 0) -> str:
    return "PASS" if abs(int(actual) - int(expected)) <= tolerance_minutes else "FAIL"


def is_month_full_span(start_value: Any, end_value: Any) -> bool:
    start = parse_date(start_value)
    end = parse_date(end_value)
    if not start or not end:
        return False
    if start.day != 1:
        return False
    if start.year != end.year or start.month != end.month:
        return False
    next_month = date(start.year + 1, 1, 1) if start.month == 12 else date(start.year, start.month + 1, 1)
    return end == date.fromordinal(next_month.toordinal() - 1)
