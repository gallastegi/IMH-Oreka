from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from imh_oreka import planning_data


def load_streamlit_app_module(name: str = "prc01_app_for_test"):
    app_path = ROOT / "apps" / "streamlit" / "prc01_horas_imputadas.py"
    spec = importlib.util.spec_from_file_location(name, app_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_safe_parse_many2one_variants() -> None:
    assert planning_data.safe_parse_many2one([123, "Persona"]) == ("123", "Persona")
    assert planning_data.safe_parse_many2one((123, "Persona")) == ("123", "Persona")
    assert planning_data.safe_parse_many2one('[123, "Persona"]') == ("123", "Persona")
    assert planning_data.safe_parse_many2one("(123, 'Persona')") == ("123", "Persona")
    assert planning_data.safe_parse_many2one("Persona") == ("", "Persona")
    assert planning_data.safe_parse_many2one("123") == ("123", "")


def test_month_allocations_reconcile_and_last_month_absorbs_rounding() -> None:
    start = pd.Timestamp("2026-01-31")
    end = pd.Timestamp("2026-02-02")
    rows = planning_data.month_allocations(start, end, 10.0)
    assert [(year, month) for year, month, _, _ in rows] == [(2026, 1), (2026, 2)]
    assert round(sum(value for _, _, value, _ in rows), 6) == 10.0
    assert rows[-1][2] == round(10.0 - rows[0][2], 6)


def test_duration_hhmm_conversion_preserves_minutes() -> None:
    assert planning_data.duration_hhmm_to_hours("523:12") == 523.2
    assert planning_data.duration_hhmm_to_hours("04:12") == 4.2
    assert round(planning_data.duration_hhmm_to_hours("02:44"), 6) == round(2 + 44 / 60, 6)
    assert planning_data.hours_to_duration_hhmm(523.2) == "523:12"
    assert planning_data.hours_to_duration_hhmm(4.45) == "04:27"


def test_derive_planning_status_is_prudent() -> None:
    assert planning_data.derive_planning_status(pd.Series({"active": True, "project_id": [1, "P"], "name": "T"})) == "asegurada"
    assert planning_data.derive_planning_status(pd.Series({"active": False, "project_id": [1, "P"], "name": "T"})) == "pendiente"
    assert planning_data.derive_planning_status(pd.Series({"active": True, "project_id": "", "name": ""})) == "pendiente"


def _write_json(path: Path, records: list[dict]) -> None:
    path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")


def test_build_dataset_preserves_hours_unmatched_people_and_no_task(tmp_path, monkeypatch) -> None:
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    reports_dir = tmp_path / "reports"
    raw_dir.mkdir()
    processed_dir.mkdir()
    reports_dir.mkdir()
    source = raw_dir / "10_project_task_planning_all.json"
    _write_json(
        source,
        [
            {
                "id": 10,
                "name": "",
                "project_id": [5, "Proyecto real"],
                "user_id": [7, "Persona Sin Match"],
                "date_start": "2026-01-31 00:00:00",
                "date_deadline": "2026-02-02",
                "planned_hours": 10.0,
                "active": True,
                "create_date": "2026-01-01 00:00:00",
                "write_date": "2026-01-02 00:00:00",
            }
        ],
    )
    monkeypatch.setattr(planning_data, "RAW_DIR", raw_dir)
    monkeypatch.setattr(planning_data, "PROCESSED_DIR", processed_dir)
    monkeypatch.setattr(planning_data, "REPORTS_DIR", reports_dir)
    monkeypatch.setattr(planning_data, "PROCESSED_PLANNING_FILE", processed_dir / "17_prc01_planning_detail.csv")
    monkeypatch.setattr(planning_data, "SOURCE_DIAGNOSTICS_FILE", reports_dir / "prc01_planning_source_diagnostics.csv")
    monkeypatch.setattr(planning_data, "UNMATCHED_PEOPLE_FILE", reports_dir / "prc01_planning_unmatched_people.csv")
    monkeypatch.setattr(planning_data, "DUPLICATES_FILE", reports_dir / "prc01_planning_duplicates.csv")
    monkeypatch.setattr(planning_data, "MONTHLY_RECONCILIATION_FILE", reports_dir / "prc01_planning_monthly_reconciliation.csv")
    monkeypatch.setattr(planning_data, "INVALID_ROWS_FILE", reports_dir / "prc01_planning_invalid_rows.csv")

    result = planning_data.build_planning_dataset()
    processed = pd.read_csv(result["output"], sep=";", encoding="utf-8-sig")
    assert result["source"] == source
    assert result["raw_rows"] == 1
    assert result["processed_rows"] == 2
    assert result["difference"] == 0.0
    assert round(processed["planned_hours"].sum(), 6) == 10.0
    assert processed["planning_id"].tolist() == ["ODOO-10-2026-01", "ODOO-10-2026-02"]
    assert set(processed["task_name"]) == {"Sin tarea"}
    unmatched = pd.read_csv(reports_dir / "prc01_planning_unmatched_people.csv", sep=";", encoding="utf-8-sig")
    assert len(unmatched) == 1


def test_resolve_source_does_not_duplicate_csv_json_equivalents(tmp_path, monkeypatch) -> None:
    raw_dir = tmp_path / "raw"
    reports_dir = tmp_path / "reports"
    raw_dir.mkdir()
    reports_dir.mkdir()
    records = [{"id": 1, "name": "T", "planned_hours": 1, "active": True}]
    _write_json(raw_dir / "10_project_task_planning_all.json", records)
    pd.DataFrame(records).to_csv(raw_dir / "10_project_task_planning_all.csv", sep=";", index=False)
    monkeypatch.setattr(planning_data, "REPORTS_DIR", reports_dir)
    monkeypatch.setattr(planning_data, "SOURCE_DIAGNOSTICS_FILE", reports_dir / "prc01_planning_source_diagnostics.csv")
    decision = planning_data.resolve_planning_source(raw_dir)
    assert decision.selected.name == "10_project_task_planning_all.json"
    diagnostics = pd.read_csv(reports_dir / "prc01_planning_source_diagnostics.csv", sep=";", encoding="utf-8-sig")
    assert diagnostics["selected"].sum() == 1
    assert diagnostics["overlap_with_selected_ids"].tolist() == [1, 1]


def test_streamlit_planning_loader_uses_only_processed_odoo_dataset() -> None:
    app_path = ROOT / "apps" / "streamlit" / "prc01_horas_imputadas.py"
    module = load_streamlit_app_module("prc01_app_for_loader_test")
    module.ensure_config_files()
    processed = module.load_planning_data("es")
    assert set(module.PLANNING_COLUMNS).issubset(set(processed.columns))
    assert not processed["planning_id"].astype(str).str.contains("PLN001|PLN002", regex=True).any()
    source = app_path.read_text(encoding="utf-8")
    assert "load_planning_data(lang, source_mode" not in source
    assert "planning_source_mode" not in source
    assert "PLN001" not in source
    assert "PLN002" not in source


def test_connection_download_summary_formats_validated_result() -> None:
    module = load_streamlit_app_module("prc01_app_summary_test")
    download = {
        "csv_path": str(ROOT / "data" / "raw" / "11_analytic_lines_2026-01-01_to_2027-01-01.csv"),
        "json_path": str(ROOT / "data" / "raw" / "11_analytic_lines_2026-01-01_to_2027-01-01.json"),
        "rows": 16402,
        "hours": 46669.73333333333,
        "people": 51,
        "projects": 135,
        "min_date": "2026-01-02",
        "max_date": "2026-07-24",
    }
    transform = {
        "detail_path": str(ROOT / "data" / "processed" / "16_prc01_actuals_annual_detail.csv"),
        "pending_rows": 2729,
        "source_file": str(ROOT / "data" / "raw" / "11_analytic_lines_2026-01-01_to_2027-01-01.csv"),
        "source_date_from": "2026-01-01",
        "source_date_to": "2027-01-01",
    }
    summary = module.download_rebuild_summary(download, transform)
    assert summary["records_downloaded"] == 16402
    assert module.format_integer_es(summary["records_downloaded"]) == "16.402"
    assert module.format_number_es(summary["hours_downloaded"], 2) == "46.669,73"
    assert module.format_date_display(summary["min_date"]) == "02/01/2026"
    assert summary["raw_csv"] == "data\\raw\\11_analytic_lines_2026-01-01_to_2027-01-01.csv"
    assert "C:\\Users" not in summary["raw_csv"]


def test_connection_view_has_single_primary_download_action_and_no_visible_json() -> None:
    app_path = ROOT / "apps" / "streamlit" / "prc01_horas_imputadas.py"
    source = app_path.read_text(encoding="utf-8")
    assert "st.json(" not in source
    assert 'st.button(t("odoo.connection.download_rebuild"' in source
    assert 'st.button(t("odoo.connection.download", lang=lang))' not in source
    assert 'st.button(t("odoo.connection.build_dataset", lang=lang))' not in source
    assert 'st.button(t("odoo.connection.test_connection", lang=lang))' not in source


def test_cascading_multiselect_refreshes_select_all_when_scope_changes() -> None:
    module = load_streamlit_app_module("prc01_app_multiselect_all_test")
    result = module.reconcile_multiselect_selection(
        ["Proyecto NUEVO A", "Proyecto NUEVO B"],
        ["Proyecto anterior A", "Proyecto anterior B"],
        ["Proyecto anterior A", "Proyecto anterior B"],
    )
    assert result == ["Proyecto NUEVO A", "Proyecto NUEVO B"]


def test_cascading_multiselect_discards_fully_stale_hidden_filter() -> None:
    module = load_streamlit_app_module("prc01_app_multiselect_stale_test")
    result = module.reconcile_multiselect_selection(
        ["Tarea NUEVO A", "Tarea NUEVO B"],
        ["Tarea anterior A", "Tarea compartida"],
        ["Tarea anterior A"],
    )
    assert result == ["Tarea NUEVO A", "Tarea NUEVO B"]


def test_cascading_multiselect_preserves_valid_partial_selection() -> None:
    module = load_streamlit_app_module("prc01_app_multiselect_partial_test")
    result = module.reconcile_multiselect_selection(
        ["Compartido", "Nuevo"],
        ["Compartido", "Anterior"],
        ["Compartido"],
    )
    assert result == ["Compartido"]


def test_cascading_multiselect_preserves_explicit_empty_selection() -> None:
    module = load_streamlit_app_module("prc01_app_multiselect_empty_test")
    result = module.reconcile_multiselect_selection(
        ["A", "B"],
        ["A", "B"],
        [],
    )
    assert result == []


def test_analysis_person_load_distributes_all_actual_hours_by_person() -> None:
    module = load_streamlit_app_module("prc01_app_actual_person_load_test")
    actuals = pd.DataFrame(
        [
            {"pertsona": "Persona A", "project_name": "A", "task_name": "T1", "grupo_gestion": "Grupo 1", "ordu_errealak": 5.0},
            {"pertsona": "Persona A", "project_name": "B", "task_name": "T2", "grupo_gestion": "Grupo 2", "ordu_errealak": 3.0},
            {"pertsona": "Persona B", "project_name": "A", "task_name": "T1", "grupo_gestion": "Grupo 1", "ordu_errealak": 2.0},
        ]
    )
    actuals["unidad_destino"] = "unidad"
    actuals["unidad_destino_label"] = "Unidad"
    actuals["naturaleza_trabajo"] = "naturaleza"
    actuals["naturaleza_trabajo_label"] = "Naturaleza"
    fig, table = module.build_actual_person_load_figure(actuals, "grupo_gestion", 10, "es")
    bars = [trace for trace in fig.data if trace.type == "bar"]
    assert {trace.name for trace in bars} == {"Grupo 1", "Grupo 2"}
    assert round(sum(sum(trace.x) for trace in bars), 6) == 10.0
    assert table["pertsona"].tolist() == ["Persona A", "Persona B"]
    assert table["horas_imputadas"].tolist() == [8.0, 2.0]
    assert round(table["porcentaje_horas"].sum(), 6) == 100.0
    assert fig.layout.barmode == "stack"


def test_analysis_chart_selector_includes_person_load_after_pareto() -> None:
    source = (ROOT / "apps" / "streamlit" / "prc01_horas_imputadas.py").read_text(encoding="utf-8")
    assert '["monthly", "pareto", "person_load"]' in source
    assert 'elif chart_type == "person_load"' in source
    assert 'build_actual_person_load_figure(filtered, color_col' in source


def test_planning_uses_single_horizontal_chart_selector_without_tabs() -> None:
    app_path = ROOT / "apps" / "streamlit" / "prc01_horas_imputadas.py"
    source = app_path.read_text(encoding="utf-8")
    assert "st.tabs" not in source
    assert 'key="planning_chart_group"' in source
    assert 'key="planning_chart_type"' in source
    assert '["monthly", "pareto", "person_load"]' in source
    assert "horizontal=True" in source
    assert 'planning_chart_type_label(value, lang)' in source
    assert 'if chart_type == "monthly"' in source
    assert 'if chart_type == "pareto"' in source
    assert 'if chart_type == "person_load"' in source
    assert 'dimension == "person_name"' in source


def sample_planning_chart_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "person_name": "Persona A",
                "person_key": "emp-1",
                "project_id": "100",
                "project_name": "Proyecto A",
                "task_name": "T1",
                "hilabete_zk": 1,
                "mes_label": "01 - Enero",
                "display_hours": 10.0,
                "ordu_errealak": 10.0,
                "unidad_destino": "ingeniaritza",
                "unidad_destino_label": "INGENIARITZA",
                "naturaleza_trabajo": "directo",
                "naturaleza_trabajo_label": "Directo",
                "grupo_gestion": "INGENIARITZA · Directo",
            },
            {
                "person_name": "Persona A",
                "person_key": "emp-1",
                "project_id": "200",
                "project_name": "Proyecto B",
                "task_name": "T2",
                "hilabete_zk": 1,
                "mes_label": "01 - Enero",
                "display_hours": 7.0,
                "ordu_errealak": 7.0,
                "unidad_destino": "lanerako_prestakuntza",
                "unidad_destino_label": "LANERAKO PRESTAKUNTZA",
                "naturaleza_trabajo": "indirecto",
                "naturaleza_trabajo_label": "Indirecto",
                "grupo_gestion": "LANERAKO PRESTAKUNTZA · Indirecto",
            },
            {
                "person_name": "Persona B",
                "person_key": "emp-2",
                "project_id": "100",
                "project_name": "Proyecto A",
                "task_name": "T3",
                "hilabete_zk": 2,
                "mes_label": "02 - Febrero",
                "display_hours": 5.0,
                "ordu_errealak": 5.0,
                "unidad_destino": "ingeniaritza",
                "unidad_destino_label": "INGENIARITZA",
                "naturaleza_trabajo": "directo",
                "naturaleza_trabajo_label": "Directo",
                "grupo_gestion": "INGENIARITZA · Directo",
            },
            {
                "person_name": "Persona B",
                "person_key": "emp-2",
                "project_id": "300",
                "project_name": "Proyecto C",
                "task_name": "T4",
                "hilabete_zk": 2,
                "mes_label": "02 - Febrero",
                "display_hours": 3.0,
                "ordu_errealak": 3.0,
                "unidad_destino": "pendiente",
                "unidad_destino_label": "Pendiente de clasificar",
                "naturaleza_trabajo": "pendiente",
                "naturaleza_trabajo_label": "Pendiente de clasificar",
                "grupo_gestion": "Pendiente de clasificar · Pendiente de clasificar",
            },
        ]
    )


def sample_person_load() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"persona": "Persona A", "horas_planificadas": 17.0, "horas_disponibles": 20.0, "estado": "OK"},
            {"persona": "Persona B", "horas_planificadas": 8.0, "horas_disponibles": 10.0, "estado": "OK"},
        ]
    )


def test_project_color_map_is_distinct_stable_and_order_independent() -> None:
    module = load_streamlit_app_module("prc01_app_color_map_test")
    df = sample_planning_chart_df()
    color_map = module.build_dimension_color_map(df, "project_name")
    assert color_map["Proyecto A"] != color_map["Proyecto B"]
    assert color_map == module.build_dimension_color_map(df, "project_name")
    assert color_map == module.build_dimension_color_map(df.sample(frac=1, random_state=42), "project_name")
    assert color_map["Proyecto A"] == module.build_dimension_color_map(df[df["person_name"] == "Persona A"], "project_name")["Proyecto A"]


def test_project_color_map_uses_project_id_and_name_fallback() -> None:
    module = load_streamlit_app_module("prc01_app_project_id_color_test")
    df = sample_planning_chart_df()
    assert module.category_stable_key(df, "project_name", "Proyecto A") == "project_id:100"
    fallback_df = df.drop(columns=["project_id"])
    assert module.category_stable_key(fallback_df, "project_name", "Proyecto A") == "project_name:proyecto a"
    assert module.build_dimension_color_map(df, "project_name") == module.build_dimension_color_map(df, "project_name")


def test_management_dimension_color_map_is_preserved_and_otros_is_neutral() -> None:
    module = load_streamlit_app_module("prc01_app_management_color_test")
    df = sample_planning_chart_df()
    management = module.build_management_color_map(df, module.load_management_units(), module.load_work_natures())
    assert module.build_dimension_color_map(df, "grupo_gestion") == management
    top_source = module.top_n_planning_dimension(df, "project_name", 2)
    assert "Otros" in set(top_source["project_name"])
    assert module.build_dimension_color_map(top_source, "project_name")["Otros"] == module.OTHER_CATEGORY_COLOR


def test_person_load_project_traces_are_stacked_and_availability_stays_red() -> None:
    module = load_streamlit_app_module("prc01_app_person_load_color_test")
    df = sample_planning_chart_df()
    fig = module.build_person_load_figure(df, sample_person_load(), "project_name", 10, "es")
    bar_traces = [trace for trace in fig.data if trace.type == "bar"]
    assert {trace.name for trace in bar_traces} == {"Proyecto A", "Proyecto B", "Proyecto C"}
    assert len({trace.marker.color for trace in bar_traces}) == 3
    assert fig.layout.barmode == "stack"
    availability = [trace for trace in fig.data if trace.type == "scatter" and trace.name == "Horas disponibles"]
    assert availability
    assert availability[0].marker.color == "#FF4B4B"


def test_project_colors_match_between_planning_views_and_reports_use_builders() -> None:
    module = load_streamlit_app_module("prc01_app_project_view_color_test")
    df = sample_planning_chart_df()
    available = pd.DataFrame({"hilabete_zk": [1, 2], "available_hours": [20.0, 20.0], "configured": [True, True]})
    monthly = module.build_planning_monthly_figure(df, [1, 2], available, "project_name", 10, "es")
    pareto, _ = module.build_planning_pareto_figure(df, "project_name", 10, 40.0, "es")
    person = module.build_person_load_figure(df, sample_person_load(), "project_name", 10, "es")
    monthly_colors = {trace.name: trace.marker.color for trace in monthly.data if trace.type == "bar"}
    pareto_trace = next(trace for trace in pareto.data if trace.type == "bar")
    pareto_colors = dict(zip(pareto_trace.y, pareto_trace.marker.color))
    person_colors = {trace.name: trace.marker.color for trace in person.data if trace.type == "bar"}
    assert monthly_colors["Proyecto A"] == person_colors["Proyecto A"] == pareto_colors["Proyecto A"]
    assert monthly_colors["Proyecto B"] == person_colors["Proyecto B"] == pareto_colors["Proyecto B"]
    assert df["display_hours"].sum() == module.top_n_planning_dimension(df, "project_name", 2)["display_hours"].sum()
    source = (ROOT / "apps" / "streamlit" / "prc01_horas_imputadas.py").read_text(encoding="utf-8")
    assert "build_planning_monthly_figure(df, months, available, \"project_name\"" in source
    assert "build_planning_pareto_figure(df, \"project_name\"" in source


def test_planning_organization_people_uses_actuals_department_hierarchy() -> None:
    module = load_streamlit_app_module("prc01_app_org_people_test")
    actuals = pd.DataFrame(
        [
            {"urtea": 2026, "pertsona": "Persona A", "saila": "PROIEKTUAK ETA ZERBITZU TEKNIKOAK / Lantegi Digitala", "ordu_errealak": 5.0},
            {"urtea": 2026, "pertsona": "Persona B", "saila": "PROIEKTUAK ETA ZERBITZU TEKNIKOAK / Lantegi Digitala", "ordu_errealak": 7.0},
            {"urtea": 2026, "pertsona": "Persona C", "saila": "BESTE SAILA", "ordu_errealak": 3.0},
        ]
    )
    people = module.load_organization_people(actuals, 2026)
    scope = module.filter_organization_people(people, "PROIEKTUAK ETA ZERBITZU TEKNIKOAK", "PROIEKTUAK ETA ZERBITZU TEKNIKOAK / Lantegi Digitala")
    assert set(scope["person_name"]) == {"Persona A", "Persona B"}
    assert set(scope["department_name"]) == {"PROIEKTUAK ETA ZERBITZU TEKNIKOAK"}
    assert set(scope["subdepartment"]) == {"PROIEKTUAK ETA ZERBITZU TEKNIKOAK / Lantegi Digitala"}


def test_planning_person_filter_options_include_people_without_planning() -> None:
    module = load_streamlit_app_module("prc01_app_people_filter_options_test")
    people = pd.DataFrame({"person_name": ["Persona A", "Persona B", "Persona C"]})
    planning = pd.DataFrame({"person_name": ["Persona B"], "display_hours": [10.0]})
    assert module.people_filter_options(people, planning) == ["Persona B", "Persona A", "Persona C"]


def test_planning_person_load_left_join_keeps_zero_planning_people() -> None:
    module = load_streamlit_app_module("prc01_app_person_left_join_test")
    planning = pd.DataFrame(
        [
            {"person_name": "Persona B", "planned_hours": 10.0, "project_name": "Proyecto A", "task_name": "T1"},
        ]
    )
    organization = pd.DataFrame(
        [
            {"person_name": "Persona B", "department_name": "D", "internal_group": "D / G", "subdepartment": "D / G"},
            {"person_name": "Persona A", "department_name": "D", "internal_group": "D / G", "subdepartment": "D / G"},
        ]
    )
    availability = pd.DataFrame(
        [
            {"person_name": "Persona B", "calculated_available_hours": 20.0},
            {"person_name": "Persona A", "calculated_available_hours": 20.0},
        ]
    )
    table = module.planning_person_load_table(planning, organization, availability, include_zero_planning=True)
    assert float(table.loc[table["persona"] == "Persona A", "horas_planificadas"].iloc[0]) == 0.0
    assert float(table.loc[table["persona"] == "Persona A", "ocupacion_planificada_pct"].iloc[0]) == 0.0
    assert table.loc[table["persona"] == "Persona A", "planning_status"].iloc[0].startswith("Sin")
    assert float(table["horas_planificadas"].sum()) == 10.0
    without_zero = module.planning_person_load_table(planning, organization, availability, include_zero_planning=False)
    assert set(without_zero["persona"]) == {"Persona B"}


def test_planning_people_coverage_records_absence_reason_and_metrics() -> None:
    module = load_streamlit_app_module("prc01_app_people_coverage_test")
    organization = pd.DataFrame(
        [
            {"person_key": "persona_b", "person_name": "Persona B", "department_name": "D", "internal_group": "D / G", "subdepartment": "D / G", "active": True, "actual_hours_period": 4.0, "present_in_organization": True},
            {"person_key": "persona_a", "person_name": "Persona A", "department_name": "D", "internal_group": "D / G", "subdepartment": "D / G", "active": True, "actual_hours_period": 2.0, "present_in_organization": True},
        ]
    )
    planning = pd.DataFrame(
        [
            {"person_name": "Persona B", "display_hours": 10.0, "date_start": "2026-01-01", "date_end": "2026-01-31", "project_name": "P", "task_name": "T"},
        ]
    )
    availability = pd.DataFrame(
        [
            {"person_name": "Persona B", "calculated_available_hours": 20.0, "workload_factor": 1.0},
            {"person_name": "Persona A", "calculated_available_hours": 20.0, "workload_factor": 1.0},
        ]
    )
    coverage = module.build_planning_people_coverage(organization, planning, planning, availability)
    assert set(coverage["status"]) == {"con_planificacion", "sin_planificacion"}
    assert coverage.loc[coverage["person_name"] == "Persona A", "absence_reason"].iloc[0] == "sin_planificacion_en_periodo"
    person_load = module.planning_person_load_table(planning, organization, availability)
    metrics = module.planning_people_coverage_metrics(person_load)
    assert metrics["people_in_scope"] == 2
    assert metrics["people_with_planning"] == 1
    assert metrics["people_without_planning"] == 1
    assert metrics["person_planning_coverage_pct"] == 50.0


def test_planning_ui_no_longer_calls_person_reconciliation_message() -> None:
    source = (ROOT / "apps" / "streamlit" / "prc01_horas_imputadas.py").read_text(encoding="utf-8")
    assert "write_person_planning_reconciliation(planning)" not in source
    assert "Reconciliacion de persona pendiente" not in source
    assert "planning_show_people_without_planning" in source
    assert "planning_filters_with_organization" in source


def test_project_task_assignments_preserve_person_project_task_and_hours() -> None:
    module = load_streamlit_app_module("imh_oreka_project_task_assignments_test")
    planning = pd.DataFrame(
        [
            {"person_name": "Persona A", "project_name": "Proyecto A", "task_name": "Diseño", "display_hours": 6.0},
            {"person_name": "Persona A", "project_name": "Proyecto A", "task_name": "Diseño", "display_hours": 4.0},
            {"person_name": "Persona A", "project_name": "Proyecto A", "task_name": "Pruebas", "display_hours": 3.5},
            {"person_name": "Persona A", "project_name": "Proyecto B", "task_name": "Documentación", "display_hours": 2.0},
            {"person_name": "Persona B", "project_name": "Proyecto A", "task_name": "Pruebas", "display_hours": 5.0},
        ]
    )

    assignments = module.build_project_task_assignments_table(planning)

    assert assignments.columns.tolist() == ["person_name", "project_name", "task_name", "assigned_hours"]
    person_a_design = assignments[
        (assignments["person_name"] == "Persona A")
        & (assignments["project_name"] == "Proyecto A")
        & (assignments["task_name"] == "Diseño")
    ]
    assert float(person_a_design["assigned_hours"].iloc[0]) == 10.0
    assert float(assignments["assigned_hours"].sum()) == 20.5

    person_html = module.project_task_assignments_html(assignments[assignments["person_name"] == "Persona A"], "es")
    assert "Proyecto A" in person_html
    assert "Diseño" in person_html
    assert "10,00" in person_html
    assert "Horas asignadas" in person_html


def test_active_python_brand_and_package_are_imh_oreka() -> None:
    legacy_package = "asmaola" + "_" + "next"
    active_python = [
        path
        for base in (ROOT / "apps", ROOT / "src", ROOT / "scripts", ROOT / "tests")
        for path in base.rglob("*.py")
        if path.resolve() != Path(__file__).resolve()
    ]
    source = "\n".join(path.read_text(encoding="utf-8-sig") for path in active_python)
    assert f"from {legacy_package}" not in source
    assert f"import {legacy_package}" not in source
    assert 'page_title="IMH Oreka"' in source
    assert (ROOT / "src" / "imh_oreka" / "__init__.py").exists()
    assert not (ROOT / "src" / legacy_package).exists()
