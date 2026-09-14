from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from imh_oreka.odoo_planning_actuals_audit import (
    INACTIVE_CONTEXT,
    STANDARD_CONTEXT,
    build_annual_actuals_domain,
    build_annual_forecast_domain,
    build_current_forecast_domain,
    build_field_mapping,
    duration_hhmm_to_minutes,
    is_month_full_span,
    minutes_to_duration_hhmm,
    minutes_to_hours,
    odoo_hours_to_minutes,
    read_all_by_domain,
    reconcile_planning_actuals,
)


class FakeClient:
    db = "test"
    uid = 1

    def __init__(self, ids: list[int], rows: list[dict[str, Any]], count: int | None = None) -> None:
        self.ids = ids
        self.rows = rows
        self.count = len(ids) if count is None else count
        self.calls: list[tuple[str, str]] = []

    def execute(self, model: str, method: str, args: list[Any] | None = None, kwargs: dict[str, Any] | None = None) -> Any:
        self.calls.append((model, method))
        if method == "search_count":
            return self.count
        if method == "search":
            return self.ids
        if method == "read":
            requested = set(args[0])
            return [row for row in self.rows if row["id"] in requested]
        raise AssertionError(method)


def test_fields_get_mapping_selects_existing_candidates() -> None:
    fields = {
        "date_start": {"string": "Start", "type": "date", "relation": "", "store": True},
        "quantity": {"string": "Quantity", "type": "float", "relation": "", "store": True},
    }
    mapping = build_field_mapping(fields, {"start_date": ["date_start", "start_date"], "planned_hours": ["quantity", "planned_hours"]})
    assert mapping[0]["odoo_field"] == "date_start"
    assert mapping[1]["odoo_field"] == "quantity"
    assert mapping[1]["selected_for_extraction"] is True


def test_read_all_validates_search_count_ids_rows_and_duplicates() -> None:
    client = FakeClient([1, 2], [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}])
    result = read_all_by_domain(client, "x.model", [["id", "!=", False]], ["id", "name"], STANDARD_CONTEXT, batch_size=1)
    assert result.search_count == 2
    assert result.ids == [1, 2]
    assert len(result.rows) == 2
    assert result.metadata["duplicate_ids"] == []


def test_read_all_fails_when_search_count_differs() -> None:
    client = FakeClient([1, 2], [{"id": 1}, {"id": 2}], count=3)
    try:
        read_all_by_domain(client, "x.model", [], ["id"], STANDARD_CONTEXT)
    except RuntimeError as exc:
        assert "search_count=3 len(ids)=2" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")


def test_duration_and_odoo_float_conversions_are_minutes_based() -> None:
    assert duration_hhmm_to_minutes("523:12") == 31392
    assert duration_hhmm_to_minutes("46:00") == 2760
    assert duration_hhmm_to_minutes("477:12") == 28632
    assert duration_hhmm_to_minutes("04:12") == 252
    assert duration_hhmm_to_minutes("02:44") == 164
    assert duration_hhmm_to_minutes("04:27") == 267
    assert duration_hhmm_to_minutes("01:38") == 98
    assert duration_hhmm_to_minutes("04:33") == 273
    assert duration_hhmm_to_minutes("05:27") == 327
    assert odoo_hours_to_minutes(4.2) == 252
    assert minutes_to_hours(53520) == 892.0
    assert minutes_to_duration_hhmm(31392) == "523:12"


def test_domains_use_start_date_and_fixed_reference_date() -> None:
    assert build_annual_forecast_domain("employee_id", "date_start", 512, 2026) == [
        ["employee_id", "=", 512],
        ["date_start", ">=", "2026-01-01"],
        ["date_start", "<", "2027-01-01"],
    ]
    assert build_current_forecast_domain("employee_id", "date_start", "date_end", 512, "2026-07-17") == [
        ["employee_id", "=", 512],
        ["date_start", "<=", "2026-07-17"],
        ["date_end", ">=", "2026-07-17"],
    ]
    assert build_annual_actuals_domain("employee_id", "date", 512, 2026)[1:] == [
        ["date", ">=", "2026-01-01"],
        ["date", "<", "2027-01-01"],
    ]


def test_active_contexts_are_explicitly_distinct() -> None:
    assert STANDARD_CONTEXT["active_test"] is True
    assert INACTIVE_CONTEXT["active_test"] is False
    assert STANDARD_CONTEXT["tz"] == "Europe/Madrid"


def test_month_full_span_is_not_redistributed() -> None:
    assert is_month_full_span("2026-01-01", "2026-01-31") is True
    assert is_month_full_span("2026-01-01", "2026-02-28") is False


def test_reconciliation_assigns_actual_once_keeps_unplanned_and_conflicts() -> None:
    forecasts = [
        {
            "forecast_id": 1,
            "employee_id": 512,
            "project_id": 10,
            "task_id": 100,
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "planned_minutes": 60,
        },
        {
            "forecast_id": 2,
            "employee_id": 512,
            "project_id": 20,
            "task_id": 200,
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "planned_minutes": 60,
        },
        {
            "forecast_id": 3,
            "employee_id": 512,
            "project_id": 20,
            "task_id": 200,
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "planned_minutes": 60,
        },
    ]
    actuals = [
        {"analytic_line_id": 1, "employee_id": 512, "project_id": 10, "task_id": 100, "date": "2026-01-15", "actual_minutes": 90},
        {"analytic_line_id": 2, "employee_id": 512, "project_id": 99, "task_id": 999, "date": "2026-01-15", "actual_minutes": 30},
        {"analytic_line_id": 3, "employee_id": 512, "project_id": 20, "task_id": 200, "date": "2026-01-15", "actual_minutes": 15},
    ]
    links, conflicts, summary = reconcile_planning_actuals(forecasts, actuals)
    assert sum(1 for row in links if row["analytic_line_id"] == 1 and row["forecast_id"] == 1) == 1
    assert any(row["match_quality"] == "no_planning_match" for row in links)
    assert conflicts and conflicts[0]["analytic_line_id"] == 3
    assert summary["actual_minutes_with_planning"] == 90
    assert summary["actual_minutes_without_planning"] == 30
    assert summary["conflict_minutes"] == 15
    assert summary["actual_identity_difference"] == 0
    assert summary["planning_minutes_overrun"] == 30
