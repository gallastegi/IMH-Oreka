from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from imh_oreka import operational_performance as op


def _planning_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "planning_id": "FORECAST-1",
                "active": True,
                "source_id": "1",
                "date_start": "2026-01-01",
                "date_end": "2026-01-31",
                "year": 2026,
                "month": 1,
                "person_key": "persona a",
                "person_id": "100",
                "person_name": "Persona A",
                "department_name": "PROIEKTUAK ETA ZERBITZU TEKNIKOAK / Lantegi Digitala",
                "project_id": "10",
                "project_name": "Proyecto A",
                "task_id": "20",
                "task_name": "Tarea A",
                "planned_hours": 10.0,
                "unidad_destino": "ingeniaritza",
                "unidad_destino_label": "INGENIARITZA",
                "naturaleza_trabajo": "directo",
                "naturaleza_trabajo_label": "Directo",
                "grupo_gestion": "INGENIARITZA · Directo",
                "classification_status": "clasificado",
            },
            {
                "planning_id": "FORECAST-2",
                "active": True,
                "source_id": "2",
                "date_start": "2026-01-01",
                "date_end": "2026-01-31",
                "year": 2026,
                "month": 1,
                "person_key": "persona a",
                "person_id": "100",
                "person_name": "Persona A",
                "department_name": "PROIEKTUAK ETA ZERBITZU TEKNIKOAK / Lantegi Digitala",
                "project_id": "10",
                "project_name": "Proyecto A",
                "task_id": "21",
                "task_name": "Otra tarea",
                "planned_hours": 5.0,
                "unidad_destino": "ingeniaritza",
                "unidad_destino_label": "INGENIARITZA",
                "naturaleza_trabajo": "directo",
                "naturaleza_trabajo_label": "Directo",
                "grupo_gestion": "INGENIARITZA · Directo",
                "classification_status": "clasificado",
            },
        ]
    )


def _actual_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "data": "2026-01-15",
                "urtea": 2026,
                "hilabete_zk": 1,
                "pertsona": "Persona A",
                "saila": "PROIEKTUAK ETA ZERBITZU TEKNIKOAK / Lantegi Digitala",
                "project_id": "10",
                "project_name": "Proyecto A",
                "task_id": "20",
                "task_name": "Tarea A",
                "ordu_errealak": 4.0,
                "unidad_destino": "ingeniaritza",
                "unidad_destino_label": "INGENIARITZA",
                "naturaleza_trabajo": "directo",
                "naturaleza_trabajo_label": "Directo",
                "grupo_gestion": "INGENIARITZA · Directo",
                "classification_status": "clasificado",
            },
            {
                "data": "2026-01-16",
                "urtea": 2026,
                "hilabete_zk": 1,
                "pertsona": "Persona A",
                "saila": "PROIEKTUAK ETA ZERBITZU TEKNIKOAK / Lantegi Digitala",
                "project_id": "99",
                "project_name": "Proyecto sin plan",
                "task_id": "99",
                "task_name": "Sin plan",
                "ordu_errealak": 3.0,
                "unidad_destino": "pendiente",
                "unidad_destino_label": "Pendiente de clasificar",
                "naturaleza_trabajo": "pendiente",
                "naturaleza_trabajo_label": "Pendiente de clasificar",
                "grupo_gestion": "Pendiente de clasificar · Pendiente de clasificar",
                "classification_status": "pendiente",
            },
        ]
    )


def test_duration_and_minutes_conversion() -> None:
    assert op.hours_to_minutes("523:12") == 31392
    assert op.hours_to_minutes(4.2) == 252
    assert op.minutes_to_hours(31392) == 523.2


def test_match_exact_and_unplanned_are_preserved() -> None:
    planning = op.normalize_planning_detail(_planning_rows())
    actuals = op.normalize_actuals_detail(_actual_rows())
    matches, conflicts = op.match_actuals_to_planning(actuals, planning)
    assert conflicts.empty
    assert set(matches["match_status"]) == {"matched", "unplanned"}
    assert matches.loc[matches["match_status"].eq("matched"), "match_quality"].iloc[0] == op.MATCH_EXACT
    assert int(matches["actual_minutes"].sum()) == int(actuals["actual_minutes"].sum())


def test_build_dataset_reconciles_actual_hours_and_planning_hours() -> None:
    result = op.build_operational_performance_dataset(_planning_rows(), _actual_rows())
    detail = result.detail
    assert round(detail["planned_hours"].sum(), 6) == 15.0
    assert round(detail["actual_hours"].sum(), 6) == 7.0
    assert round(detail["actual_hours_with_planning"].sum(), 6) == 4.0
    assert round(detail["actual_hours_without_planning"].sum(), 6) == 3.0
    assert round(detail["actual_hours_with_planning"].sum() + detail["actual_hours_without_planning"].sum(), 6) == round(detail["actual_hours"].sum(), 6)
    assert round(detail["planned_hours_not_executed"].sum(), 6) == 11.0


def test_project_name_fallback_matches_when_ids_differ() -> None:
    planning = _planning_rows()
    actuals = _actual_rows().head(1).copy()
    actuals["project_id"] = "Proyecto A"
    actuals["task_id"] = "Tarea A"
    result = op.build_operational_performance_dataset(planning, actuals)
    assert round(result.detail["actual_hours_with_planning"].sum(), 6) == 4.0
    assert round(result.detail["actual_hours_without_planning"].sum(), 6) == 0.0


def test_multiple_forecast_conflict_is_diagnosed_once() -> None:
    planning = _planning_rows()
    actuals = _actual_rows().head(1).copy()
    actuals["task_id"] = ""
    actuals["task_name"] = ""
    result = op.build_operational_performance_dataset(planning, actuals)
    assert not result.conflicts.empty
    assert result.conflicts["match_quality"].iloc[0] == op.MATCH_CONFLICT
    assert round(result.detail["actual_hours"].sum(), 6) == 4.0


def test_people_load_keeps_people_without_planning() -> None:
    result = op.build_operational_performance_dataset(_planning_rows(), _actual_rows())
    organization = pd.DataFrame(
        [
            {"person_name": "Persona A", "department_name": "Dept", "internal_group": "Group"},
            {"person_name": "Unai", "department_name": "Dept", "internal_group": "Group"},
        ]
    )
    availability = pd.DataFrame(
        [
            {"person_name": "Persona A", "calculated_available_hours": 20.0},
            {"person_name": "Unai", "calculated_available_hours": 20.0},
        ]
    )
    people = op.calculate_people_load(result.detail, availability, organization)
    unai = people[people["person_name"].eq("Unai")].iloc[0]
    assert unai["planned_hours"] == 0
    assert unai["actual_hours"] == 0
    assert unai["planning_status"] == "Sin planificacion"
