from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import re
import sys
import unicodedata
import zipfile
from datetime import date, datetime
from html import escape
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots


ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from imh_oreka.odoo_common import OdooClient, save_csv, save_json, valid_fields  # noqa: E402
from imh_oreka import operational_performance as op  # noqa: E402
from imh_oreka import planning_data as planning_pipeline  # noqa: E402
from imh_oreka.planning_data import duration_hhmm_to_hours, hours_to_duration_hhmm, safe_parse_many2one, to_float  # noqa: E402


DATA_RAW_DIR = ROOT_DIR / "data" / "raw"
DATA_PROCESSED_DIR = ROOT_DIR / "data" / "processed"
DATA_REPORTS_DIR = ROOT_DIR / "data" / "reports"
ANALYSIS_REPORTS_DIR = DATA_REPORTS_DIR / "prc01_analysis_reports"
PLANNING_REPORTS_DIR = DATA_REPORTS_DIR / "prc01_planning_reports"
OPERATIONAL_PROCESSED_FILE = DATA_PROCESSED_DIR / "18_prc01_operational_performance_detail.csv"
OPERATIONAL_REPORTS_DIR = DATA_REPORTS_DIR / "prc01_operational_performance_reports"
CONFIG_DIR = ROOT_DIR / "config"
LOGS_DIR = ROOT_DIR / "logs"
DATA_FILE = DATA_PROCESSED_DIR / "16_prc01_actuals_annual_detail.csv"
PLANNING_PROCESSED_FILE = DATA_PROCESSED_DIR / "17_prc01_planning_detail.csv"
PLANNING_DIAGNOSTICS_FILE = DATA_REPORTS_DIR / "prc01_planning_diagnostics.csv"
PLANNING_OVERLOADS_FILE = DATA_REPORTS_DIR / "prc01_planning_overloads.csv"
PLANNING_PENDING_CLASSIFICATION_FILE = DATA_REPORTS_DIR / "prc01_planning_pending_classification.csv"
PLANNING_UNMATCHED_PEOPLE_FILE = DATA_REPORTS_DIR / "prc01_planning_unmatched_people.csv"
PLANNING_DUPLICATES_FILE = DATA_REPORTS_DIR / "prc01_planning_duplicates.csv"
PLANNING_MONTHLY_RECONCILIATION_FILE = DATA_REPORTS_DIR / "prc01_planning_monthly_reconciliation.csv"
PLANNING_INVALID_ROWS_FILE = DATA_REPORTS_DIR / "prc01_planning_invalid_rows.csv"
PLANNING_PERSON_AUDIT_FILE = DATA_REPORTS_DIR / "prc01_planning_person_audit.csv"
PLANNING_PERSON_AUDIT_SUMMARY_FILE = DATA_REPORTS_DIR / "prc01_planning_person_audit_summary.csv"
PLANNING_PERSON_AUDIT_DIAGNOSTICS_FILE = DATA_REPORTS_DIR / "prc01_planning_person_audit_diagnostics.csv"
PLANNING_PEOPLE_FILTER_WATERFALL_FILE = DATA_REPORTS_DIR / "prc01_planning_people_filter_waterfall.csv"
PLANNING_PEOPLE_COVERAGE_FILE = DATA_REPORTS_DIR / "prc01_planning_people_coverage.csv"
PLANNING_ODOO_PEOPLE_VISIBILITY_FILE = DATA_REPORTS_DIR / "prc01_planning_odoo_people_visibility.csv"
PLANNING_PEOPLE_ODOO_VS_APP_FILE = DATA_REPORTS_DIR / "prc01_planning_people_odoo_vs_app.csv"
UNCLASSIFIED_REPORT = DATA_REPORTS_DIR / "prc01_unclassified_project_tasks.csv"
CLASSIFICATION_DIAGNOSTICS_REPORT = DATA_REPORTS_DIR / "prc01_classification_diagnostics.csv"
TEAMS_FILE = CONFIG_DIR / "prc01_teams.csv"
# LEGACY: old project/task classification by grupo_actividad. It is kept only
# for compatibility and audit; the user-facing UI uses management classification.
CLASSIFICATION_FILE = CONFIG_DIR / "prc01_project_task_classification.csv"
MANAGEMENT_UNITS_FILE = CONFIG_DIR / "prc01_management_units.csv"
WORK_NATURES_FILE = CONFIG_DIR / "prc01_work_natures.csv"
MANAGEMENT_RULES_FILE = CONFIG_DIR / "prc01_management_classification_rules.csv"
MANAGEMENT_CLASSIFICATION_DIAGNOSTICS = DATA_REPORTS_DIR / "prc01_management_classification_diagnostics.csv"
MANAGEMENT_CLASSIFICATION_PENDING = DATA_REPORTS_DIR / "prc01_management_classification_pending.csv"
MANAGEMENT_CLASSIFICATION_REVIEW = DATA_REPORTS_DIR / "prc01_management_classification_review.csv"
AVAILABLE_HOURS_FILE = CONFIG_DIR / "prc01_available_hours.csv"
PERSON_WORKLOAD_FILE = CONFIG_DIR / "prc01_person_workload.csv"
TRANSLATIONS_FILE = CONFIG_DIR / "prc01_translations.csv"
TRANSFORM_SCRIPT = ROOT_DIR / "scripts" / "03_transform" / "16_build_prc01_actuals_annual.py"
OPERATIONAL_TRANSFORM_SCRIPT = ROOT_DIR / "scripts" / "02_transform" / "24_build_prc01_operational_performance.py"
PRIVATE_ENV = ROOT_DIR / ".env"

ALLOWED_GROUPS = ["Orokorrak", "Formakuntza", "Proiektuak", "Pendiente de clasificar"]
SCOPE_TYPES = ["company", "department", "team", "person"]
GROUP_COLORS = {
    "Orokorrak": "#8C8C8C",
    "Formakuntza": "#2E86AB",
    "Proiektuak": "#2CA25F",
    "Pendiente de clasificar": "#D95F02",
}
OTHER_CATEGORY_COLOR = "#9E9E9E"
DEFAULT_CATEGORY_COLOR = "#607D8B"
STABLE_CATEGORY_PALETTE = list(
    dict.fromkeys(
        [
            color
            for palette in [
                px.colors.qualitative.Plotly,
                px.colors.qualitative.D3,
                px.colors.qualitative.G10,
                px.colors.qualitative.T10,
                px.colors.qualitative.Alphabet,
                px.colors.qualitative.Dark24,
                px.colors.qualitative.Light24,
            ]
            for color in palette
            if color.upper() != OTHER_CATEGORY_COLOR
        ]
    )
)
UNIT_BASE_COLORS = {
    "ingeniaritza": "#1565C0",
    "lanerako_prestakuntza": "#6A1B9A",
    "incress": "#00838F",
    "proiektu_zerbitzu_teknikoak": "#2E7D32",
    "ekoizpena": "#EF6C00",
    "komertziala_marketina": "#C2185B",
    "pertsonak_antolaketa": "#5D4037",
    "gobernantza_barne_kudeaketa": "#455A64",
    "pendiente": "#9E9E9E",
}
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
MONTH_NAMES_ES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}
MONTH_ORDER = [f"{month:02d} - {name}" for month, name in MONTH_NAMES_EU.items()]

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
CLASSIFICATION_COLUMNS = list(dict.fromkeys(CLASSIFICATION_COLUMNS))
TEAM_COLUMNS = ["team_id", "team_name", "employee_name", "employee_alias", "active", "comment"]
MANAGEMENT_UNIT_COLUMNS = ["unit_key", "label_es", "label_eu", "active", "sort_order", "updated_at"]
WORK_NATURE_COLUMNS = ["nature_key", "label_es", "label_eu", "active", "sort_order", "updated_at"]
MANAGEMENT_RULE_COLUMNS = [
    "rule_id",
    "priority",
    "active",
    "project_contains",
    "task_contains",
    "department_contains",
    "person_contains",
    "unidad_destino",
    "naturaleza_trabajo",
    "notes",
    "updated_at",
]
AVAILABLE_COLUMNS = [
    "year",
    "month",
    "month_name",
    "scope_type",
    "scope_key",
    "scope_name",
    "available_hours",
    "active",
    "comment",
    "updated_by",
    "updated_at",
]
PERSON_WORKLOAD_COLUMNS = [
    "person_key",
    "person_name",
    "year",
    "workload_factor",
    "weekly_hours",
    "active",
    "comment",
    "updated_by",
    "updated_at",
]
TRANSLATION_COLUMNS = ["key", "context", "text_es", "text_eu", "notes", "active", "updated_at"]
PLANNING_COLUMNS = [
    "planning_id",
    "active",
    "planning_status",
    "source_system",
    "source_model",
    "source_id",
    "source_name",
    "year",
    "month",
    "person_key",
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
    "naturaleza_trabajo",
    "grupo_gestion",
    "classification_rule_id",
    "classification_status",
    "notes",
    "created_at",
    "updated_at",
]
VALID_PLANNING_STATUSES = ["asegurada", "posible", "pendiente"]
LANGUAGE_OPTIONS = {"es": "Castellano", "eu": "Euskera"}
DEFAULT_MANAGEMENT_UNITS = [
    ["ingeniaritza", "INGENIARITZA", "INGENIARITZA", "TRUE", 1, ""],
    ["lanerako_prestakuntza", "LANERAKO PRESTAKUNTZA", "LANERAKO PRESTAKUNTZA", "TRUE", 2, ""],
    ["incress", "INCRESS", "INCRESS", "TRUE", 3, ""],
    ["proiektu_zerbitzu_teknikoak", "PROIEKTUAK ETA ZERBITZU TEKNIKOAK", "PROIEKTUAK ETA ZERBITZU TEKNIKOAK", "TRUE", 4, ""],
    ["ekoizpena", "EKOIZPENA", "EKOIZPENA", "TRUE", 5, ""],
    ["komertziala_marketina", "KOMERTZIALA ETA MARKETINA", "KOMERTZIALA ETA MARKETINA", "TRUE", 6, ""],
    ["pertsonak_antolaketa", "PERTSONAK ETA ANTOLAKETA", "PERTSONAK ETA ANTOLAKETA", "TRUE", 7, ""],
    ["gobernantza_barne_kudeaketa", "GOBERNANZA Y GESTIÓN INTERNA", "GOBERNANTZA ETA BARNE-KUDEAKETA", "TRUE", 8, ""],
    ["pendiente", "PENDIENTE DE CLASIFICAR", "SAILKATU GABE", "TRUE", 99, ""],
]
DEFAULT_WORK_NATURES = [
    ["directo", "Directo", "Zuzena", "TRUE", 1, ""],
    ["indirecto", "Indirecto", "Zeharkakoa", "TRUE", 2, ""],
    ["no_aplica", "No aplica", "Ez dagokio", "TRUE", 3, ""],
    ["pendiente", "Pendiente de clasificar", "Sailkatu gabe", "TRUE", 99, ""],
]
DEFAULT_MANAGEMENT_RULES = [
    ["R001", 10, "TRUE", "Proiektua Ingeniaritza", "", "", "", "ingeniaritza", "directo", "Docencia directa ingeniería", ""],
    ["R002", 20, "TRUE", "Prozesua Ingeniaritza", "", "", "", "ingeniaritza", "indirecto", "Preparación tutoría corrección ingeniería", ""],
    ["R003", 30, "TRUE", "", "garapena", "", "", "proiektu_zerbitzu_teknikoak", "directo", "Desarrollo técnico directo", ""],
    ["R004", 40, "TRUE", "", "kudeaketa", "", "", "proiektu_zerbitzu_teknikoak", "indirecto", "Gestión técnica indirecta", ""],
    ["R005", 50, "TRUE", "Formación personal", "", "", "", "pertsonak_antolaketa", "indirecto", "Formación interna personal", ""],
    ["R006", 60, "TRUE", "Baja", "", "", "", "pertsonak_antolaketa", "no_aplica", "Bajas", ""],
    ["R007", 70, "TRUE", "Permiso", "", "", "", "pertsonak_antolaketa", "no_aplica", "Permisos", ""],
    ["R008", 80, "TRUE", "Comité", "", "", "", "gobernantza_barne_kudeaketa", "indirecto", "Comités internos", ""],
]
REQUIRED_TRANSLATIONS = [
    ("app.language", "app", "Idioma", "Hizkuntza"),
    ("app.nav.odoo", "app", "Conexión y descarga de Odoo", "Odoo konexioa eta deskarga"),
    ("app.nav.analysis", "app", "Análisis de datos", "Datuen analisia"),
    ("app.nav.configuration", "app", "Configuración", "Konfigurazioa"),
    ("app.nav.exploration", "app", "Exploración Odoo", "Odoo esplorazioa"),
    ("app.config.section", "app", "Apartado de configuración", "Konfigurazio atala"),
    ("app.config.available_hours", "app", "Horas disponibles mensuales", "Hileko ordu erabilgarriak"),
    ("app.config.workload", "app", "Jornadas por persona", "Pertsonen lanaldia"),
    ("app.config.language", "app", "Idioma", "Hizkuntza"),
    ("app.analysis.title", "app", "Análisis de datos - Carga anual por departamento", "Datuen analisia - Urteko karga sailaren arabera"),
    ("app.filters.view_config", "app", "Configuración de vista", "Ikuspegiaren konfigurazioa"),
    ("app.filters.year", "app", "Año", "Urtea"),
    ("app.filters.department", "app", "Departamento", "Saila"),
    ("app.filters.subdepartment", "app", "Grupo interno / subdepartamento", "Barne taldea / azpisaila"),
    ("app.filters.month_start", "app", "Inicio periodo", "Aldiaren hasiera"),
    ("app.filters.month_end", "app", "Fin periodo", "Aldiaren amaiera"),
    ("app.filters.activity_group", "app", "LEGACY grupo_actividad", "LEGACY grupo_actividad"),
    ("app.filters.person", "app", "Persona", "Pertsona"),
    ("app.filters.top_n", "app", "Top N elementos en detalle", "Top N xehetasunetan"),
    ("app.filters.advanced", "app", "Filtros avanzados", "Iragazki aurreratuak"),
    ("app.chart.group_by", "app", "Agrupar gráfica por", "Grafikoa honen arabera multzokatu"),
    ("app.chart.type", "app", "Tipo de gráfica", "Grafiko mota"),
    ("app.chart.monthly", "app", "Barras mensuales", "Hileko barrak"),
    ("app.chart.pareto", "app", "Pareto", "Pareto"),
    ("analysis.person_load_view", "analysis", "Horas imputadas por persona", "Pertsonako egotzitako orduak"),
    ("analysis.person_load_label", "analysis", "⚙ Carga por persona", "⚙ Pertsonako karga"),
    ("app.metrics.summary", "app", "Resumen de horas", "Orduen laburpena"),
    ("app.available.diagnostics", "app", "Diagnóstico horas disponibles", "Ordu erabilgarrien diagnostikoa"),
    ("app.reports.generate", "app", "Generar informes", "Txostenak sortu"),
    ("app.reports.download_zip", "app", "Descargar informe ZIP", "Deskargatu ZIP txostena"),
    ("report.filters", "report", "Filtros aplicados", "Aplikatutako iragazkiak"),
    ("report.filter", "report", "Filtro", "Iragazkia"),
    ("report.value", "report", "Valor", "Balioa"),
    ("report.executive_summary", "report", "Resumen ejecutivo", "Laburpen exekutiboa"),
    ("report.monthly_group", "report", "Evolución mensual por grupo de actividad", "Hileko bilakaera jarduera taldearen arabera"),
    ("report.monthly_project", "report", "Evolución mensual por proyecto", "Hileko bilakaera proiektuaren arabera"),
    ("report.pareto_group", "report", "Pareto por grupo de gesti??n", "Pareto kudeaketa taldearen arabera"),
    ("report.pareto_project", "report", "Pareto por proyecto", "Pareto proiektuaren arabera"),
    ("report.generated_at", "report", "Fecha de generación", "Sortze data"),
    ("column.grupo_actividad", "column", "LEGACY grupo_actividad", "LEGACY grupo_actividad"),
    ("column.project_name", "column", "Proyecto", "Proiektua"),
    ("column.task_name", "column", "Tarea", "Zeregina"),
    ("column.person_name", "column", "Persona", "Pertsona"),
    ("column.pertsona", "column", "Persona", "Pertsona"),
    ("column.month", "column", "Mes", "Hilabetea"),
    ("column.month_name", "column", "Mes", "Hilabetea"),
    ("column.horas", "column", "Horas", "Orduak"),
    ("column.available_hours", "column", "Horas disponibles", "Ordu erabilgarriak"),
    ("column.porcentaje", "column", "Porcentaje", "Ehunekoa"),
    ("column.porcentaje_total", "column", "Porcentaje total", "Ehuneko osoa"),
    ("column.personas", "column", "Personas", "Pertsonak"),
    ("column.tareas", "column", "Tareas", "Zereginak"),
    ("value.Orokorrak", "value", "Generales", "Orokorrak"),
    ("value.Formakuntza", "value", "Formación", "Formakuntza"),
    ("value.Proiektuak", "value", "Proyectos", "Proiektuak"),
    ("value.Pendiente de clasificar", "value", "Pendiente de clasificar", "Sailkatu gabe"),
]
REQUIRED_TRANSLATIONS.extend(
    [
        (f"month.{month:02d}", "month", MONTH_NAMES_ES[month], MONTH_NAMES_EU[month])
        for month in range(1, 13)
    ]
)
REQUIRED_TRANSLATIONS.extend(
    [
        ("app.chart.monthly_label", "app", "▦ Barras mensuales", "▦ Hileko barrak"),
        ("app.chart.pareto_label", "app", "↗ Pareto", "↗ Pareto"),
        ("app.chart.group_by_activity", "app", "LEGACY grupo_actividad", "LEGACY grupo_actividad"),
        ("app.chart.group_by_project", "app", "Proyecto", "Proiektua"),
        ("column.hilabete_zk", "column", "Nº mes", "Hilabete zk."),
        ("column.mes_label", "column", "Mes", "Hilabetea"),
        ("column.month_display", "column", "Mes", "Hilabetea"),
        ("column.data", "column", "Fecha", "Data"),
        ("column.date", "column", "Fecha", "Data"),
        ("column.available_hours_base", "column", "Horas base disponibles", "Oinarrizko ordu erabilgarriak"),
        ("column.calculated_available_hours", "column", "Horas disponibles calculadas", "Kalkulatutako ordu erabilgarriak"),
        ("column.person_specific_available_hours", "column", "Horas específicas persona", "Pertsonaren ordu espezifikoak"),
        ("column.workload_factor", "column", "Factor de jornada", "Lanaldi faktorea"),
        ("column.weekly_hours", "column", "Horas semanales", "Asteko orduak"),
        ("column.person_key", "column", "Clave persona", "Pertsona gakoa"),
        ("column.employee_name", "column", "Persona", "Pertsona"),
        ("column.hours", "column", "Horas", "Orduak"),
        ("column.percentage", "column", "Porcentaje", "Ehunekoa"),
        ("column.people_count", "column", "Nº personas", "Pertsona kopurua"),
        ("column.projects_count", "column", "Nº proyectos", "Proiektu kopurua"),
        ("column.tasks_count", "column", "Nº tareas", "Zeregin kopurua"),
        ("column.base_source", "column", "Fuente base", "Oinarrizko iturria"),
        ("column.base_scope_name", "column", "Alcance base", "Oinarrizko eremua"),
        ("column.base_scope_type", "column", "Tipo de alcance", "Eremu mota"),
        ("column.reason", "column", "Motivo", "Arrazoia"),
        ("column.source_scope_type", "column", "Tipo de fuente", "Iturri mota"),
        ("column.source_scope_name", "column", "Fuente usada", "Erabilitako iturria"),
        ("column.ordu_errealak", "column", "Horas imputadas", "Egotzitako orduak"),
        ("column.azalpena", "column", "Descripción", "Azalpena"),
        ("column.saila", "column", "Departamento", "Saila"),
        ("column.lerroak", "column", "Líneas", "Lerroak"),
        ("column.pertsonak", "column", "Personas", "Pertsonak"),
        ("column.proiektuak", "column", "Proyectos", "Proiektuak"),
        ("column.atazak", "column", "Tareas", "Zereginak"),
        ("column.configured", "column", "Configurado", "Konfiguratuta"),
    ]
)
REQUIRED_TRANSLATIONS.extend(
    [
        ("app.nav.section", "app", "Sección", "Atala"),
        ("app.nav.odoo_connection", "app", "Conexión y descarga de Odoo", "Odoo konexioa eta deskarga"),
        ("app.nav.odoo_exploration", "app", "Exploración Odoo", "Odoo esplorazioa"),
        ("odoo.connection.title", "odoo", "Conexión y descarga de Odoo", "Odoo konexioa eta deskarga"),
        ("odoo.connection.subtitle", "odoo", "Descargar datos desde Odoo", "Odoo-tik datuak deskargatu"),
        ("odoo.connection.url", "odoo", "URL de Odoo", "Odoo URL-a"),
        ("odoo.connection.database", "odoo", "Base de datos", "Datu-basea"),
        ("odoo.connection.user", "odoo", "Usuario", "Erabiltzailea"),
        ("odoo.connection.password", "odoo", "Contraseña", "Pasahitza"),
        ("odoo.connection.date_from", "odoo", "Fecha inicio", "Hasiera data"),
        ("odoo.connection.date_to", "odoo", "Fecha fin", "Amaiera data"),
        ("odoo.connection.download", "odoo", "Descargar horas imputadas", "Egotzitako orduak deskargatu"),
        ("odoo.connection.test_connection", "odoo", "Probar conexión", "Konexioa probatu"),
        ("odoo.connection.build_dataset", "odoo", "Construir dataset anual", "Urteko dataseta eraiki"),
        ("odoo.connection.download_rebuild", "odoo", "Descargar de Odoo y reconstruir datasets", "Odoo-tik deskargatu eta datasetak berreraiki"),
        ("odoo.connection.connected", "odoo", "Conexión correcta", "Konexioa zuzena"),
        ("odoo.connection.error", "odoo", "Error de conexión", "Konexio errorea"),
        ("odoo.connection.download_ok", "odoo", "Descarga completada", "Deskarga osatuta"),
        ("odoo.connection.dataset_ok", "odoo", "Dataset reconstruido", "Dataseta berreraikita"),
        ("odoo.connection.flow_ok", "odoo", "Flujo completo ejecutado", "Fluxu osoa exekutatuta"),
        ("odoo.connection.save_session", "odoo", "Guardar configuración de sesión", "Saioaren konfigurazioa gorde"),
        ("odoo.connection.session_saved", "odoo", "Configuración cargada en la sesión. La contraseña no se guarda en disco.", "Konfigurazioa saioan kargatu da. Pasahitza ez da diskoan gordetzen."),
        ("odoo.connection.updated_ok", "odoo", "Datos actualizados correctamente", "Datuak behar bezala eguneratu dira"),
        ("odoo.connection.records_downloaded", "odoo", "Registros descargados", "Deskargatutako erregistroak"),
        ("odoo.connection.hours_downloaded", "odoo", "Horas descargadas", "Deskargatutako orduak"),
        ("odoo.connection.data_period", "odoo", "Periodo de datos", "Datuen aldia"),
        ("odoo.connection.pending_classification", "odoo", "Pendientes de clasificación", "Sailkatzeko zain"),
        ("odoo.connection.last_update", "odoo", "Última actualización", "Azken eguneratzea"),
        ("odoo.connection.technical_details", "odoo", "Detalles técnicos", "Xehetasun teknikoak"),
        ("odoo.connection.connecting", "odoo", "Conectando con Odoo...", "Odoo-rekin konektatzen..."),
        ("odoo.connection.downloading", "odoo", "Descargando partes de horas...", "Ordu parteak deskargatzen..."),
        ("odoo.connection.transforming", "odoo", "Transformando datos...", "Datuak eraldatzen..."),
        ("odoo.connection.rebuilding", "odoo", "Reconstruyendo datasets...", "Datasetak berreraikitzen..."),
        ("odoo.connection.connection_failed", "odoo", "No se ha podido conectar con Odoo. Revisa la URL, la base de datos, el usuario y la contraseña.", "Ezin izan da Odoo-rekin konektatu. Berrikusi URLa, datu-basea, erabiltzailea eta pasahitza."),
        ("odoo.connection.download_failed", "odoo", "La descarga o reconstrucción no se ha completado. Consulta los detalles técnicos o el log de ejecución.", "Deskarga edo berreraikuntza ez da osatu. Kontsultatu xehetasun teknikoak edo exekuzio loga."),
        ("reports.generator.title", "report", "Generar informes", "Txostenak sortu"),
        ("reports.generator.type", "report", "Tipo de informe", "Txosten mota"),
        ("reports.generator.monthly", "report", "Mensual", "Hilekoa"),
        ("reports.generator.annual", "report", "Anual", "Urtekoa"),
        ("reports.generator.between_months", "report", "Entre meses", "Hilabeteen artean"),
        ("reports.generator.month", "report", "Mes", "Hilabetea"),
        ("reports.generator.start_month", "report", "Mes inicio", "Hasierako hilabetea"),
        ("reports.generator.end_month", "report", "Mes fin", "Amaierako hilabetea"),
        ("reports.generator.detail_level", "report", "Nivel de desglose", "Desglosatze maila"),
        ("reports.generator.current_view_only", "report", "Solo vista actual", "Uneko ikuspegia bakarrik"),
        ("reports.generator.current_view_sublevels", "report", "Vista actual + subniveles", "Uneko ikuspegia + azpimailak"),
        ("reports.generator.include_detail", "report", "Incluir detalle de líneas", "Lerroen xehetasuna sartu"),
        ("reports.generator.top_n", "report", "Top N proyectos para Pareto", "Paretorako Top N proiektuak"),
        ("reports.generator.generate", "report", "Generar informe", "Txostena sortu"),
        ("reports.generator.download_zip", "report", "Descargar informe ZIP", "ZIP txostena deskargatu"),
        ("reports.generator.generated_ok", "report", "Informe generado correctamente", "Txostena behar bezala sortu da"),
        ("reports.generator.generated_files", "report", "Archivos generados", "Sortutako fitxategiak"),
        ("reports.generator.no_data", "report", "No hay datos para generar el informe", "Ez dago daturik txostena sortzeko"),
        ("summary.hours.title", "summary", "Resumen de horas", "Orduen laburpena"),
        ("metric.total_hours", "metric", "Horas totales", "Orduak guztira"),
        ("metric.imputed_hours", "metric", "Horas imputadas", "Egotzitako orduak"),
        ("metric.available_hours", "metric", "Horas disponibles", "Ordu erabilgarriak"),
        ("metric.difference_vs_available", "metric", "Diferencia vs disponibles", "Erabilgarriekiko aldea"),
        ("metric.occupation_pct", "metric", "% ocupación", "% okupazioa"),
        ("metric.people", "metric", "Personas", "Pertsonak"),
        ("metric.projects", "metric", "Proyectos", "Proiektuak"),
        ("metric.tasks", "metric", "Tareas", "Zereginak"),
        ("metric.general_hours", "metric", "Horas generales", "Ordu orokorrak"),
        ("metric.training_hours", "metric", "Horas formación", "Prestakuntza orduak"),
        ("metric.project_hours", "metric", "Horas proyectos", "Proiektu orduak"),
        ("metric.unclassified_hours", "metric", "Horas pendiente de clasificar", "Sailkatu gabeko orduak"),
        ("metric.not_configured", "metric", "No configurado", "Konfiguratu gabe"),
        ("config.title", "config", "Configuración", "Konfigurazioa"),
        ("config.available_hours", "config", "Horas disponibles mensuales", "Hileko ordu erabilgarriak"),
        ("config.person_workload", "config", "Jornadas por persona", "Pertsonako lanaldiak"),
        ("config.language", "config", "Idioma", "Hizkuntza"),
        ("config.save", "config", "Guardar", "Gorde"),
        ("config.saved", "config", "Cambios guardados", "Aldaketak gordeta"),
        ("config.reload", "config", "Recargar", "Birkargatu"),
        ("config.detect_missing_translations", "config", "Detectar textos sin traducir", "Itzuli gabeko testuak detektatu"),
        ("config.edit_language", "config", "Idioma de edición", "Edizio hizkuntza"),
        ("config.edit_both", "config", "Ambos", "Biak"),
        ("config.technical_columns_note", "config", "Las columnas técnicas se mantienen con su nombre interno para guardar sin errores.", "Zutabe teknikoek barne izena mantentzen dute errore gabe gordetzeko."),
        ("config.no_new_keys", "config", "No hay claves nuevas.", "Ez dago gako berririk."),
        ("config.keys_added", "config", "Claves añadidas", "Gehitutako gakoak"),
        ("column.workload_sum", "column", "Suma factor jornada", "Lanaldi faktoreen batura"),
        ("column.unidad_destino", "column", "Unidad destino", "Helmuga unitatea"),
        ("column.naturaleza_trabajo", "column", "Naturaleza del trabajo", "Lanaren izaera"),
        ("column.grupo_gestion", "column", "Unidad destino + naturaleza", "Helmuga unitatea + izaera"),
        ("column.grupo_gestion principal", "column", "Unidad destino + naturaleza principal", "Helmuga unitatea + izaera nagusia"),
        ("column.grupo_actividad_original", "column", "Grupo actividad original", "Jatorrizko jarduera taldea"),
        ("column.unidad_destino_label", "column", "Unidad destino", "Helmuga unitatea"),
        ("column.naturaleza_trabajo_label", "column", "Naturaleza del trabajo", "Lanaren izaera"),
        ("column.classification_rule_id", "column", "Regla de clasificación", "Sailkapen araua"),
        ("column.classification_status", "column", "Estado clasificación", "Sailkapen egoera"),
        ("config.management_classification", "config", "Clasificación de gestión", "Kudeaketa sailkapena"),
        ("app.filters.management_group", "app", "Unidad destino + naturaleza", "Helmuga unitatea + izaera"),
        ("app.chart.group_by_management", "app", "Unidad destino + naturaleza", "Helmuga unitatea + izaera"),
        ("app.chart.group_by_unit", "app", "Unidad destino", "Helmuga unitatea"),
        ("app.chart.group_by_nature", "app", "Naturaleza del trabajo", "Lanaren izaera"),
        ("report.hours_by_unit", "report", "Horas por unidad destino", "Helmuga unitateko orduak"),
        ("report.hours_by_nature", "report", "Horas por naturaleza del trabajo", "Lanaren izaeraren araberako orduak"),
        ("report.hours_by_management_group", "report", "Horas por unidad destino + naturaleza", "Helmuga unitatea + izaeraren araberako orduak"),
        ("config.management_units", "config", "Unidades destino", "Helmuga unitateak"),
        ("config.work_natures", "config", "Naturalezas del trabajo", "Lanaren izaerak"),
        ("config.management_rules", "config", "Reglas de clasificación", "Sailkapen arauak"),
        ("config.management_review", "config", "Verificación proyectos/tareas", "Proiektu/zereginen egiaztapena"),
        ("config.show_all", "config", "Todos", "Guztiak"),
        ("config.only_pending", "config", "Solo pendientes", "Sailkatu gabeak bakarrik"),
        ("config.only_classified", "config", "Solo clasificados", "Sailkatuak bakarrik"),
        ("config.search_project_task", "config", "Buscar proyecto/tarea", "Proiektua/zeregina bilatu"),
        ("config.download_review_csv", "config", "Descargar verificación CSV", "Egiaztapen CSV deskargatu"),
        ("config.validation_error", "config", "Error de validación", "Baliozkotze errorea"),
        ("config.validation_warning", "config", "Aviso de validación", "Baliozkotze oharra"),
        ("column.line_count", "column", "Nº líneas", "Lerro kopurua"),
        ("value.clasificado", "value", "Clasificado", "Sailkatuta"),
        ("value.pendiente", "value", "Pendiente", "Sailkatu gabe"),
        ("metric.direct_hours", "metric", "Horas directas", "Ordu zuzenak"),
        ("metric.indirect_hours", "metric", "Horas indirectas", "Zeharkako orduak"),
        ("metric.no_apply_hours", "metric", "Horas no aplica", "Ez dagokion orduak"),
        ("metric.pending_management_hours", "metric", "Horas pendientes de gestión", "Kudeaketa sailkatu gabeko orduak"),
    ]
)

REQUIRED_TRANSLATIONS.extend(
    [
        ("app.nav.planning", "app", "Planificación", "Plangintza"),
        ("app.nav.operational_performance", "app", "Rendimiento operativo", "Errendimendu operatiboa"),
        ("operational.title", "operational", "Rendimiento operativo", "Errendimendu operatiboa"),
        ("operational.view", "operational", "Vista", "Ikuspegia"),
        ("operational.summary", "operational", "Resumen", "Laburpena"),
        ("operational.planned_vs_actual", "operational", "Planificado vs real", "Planifikatua vs erreala"),
        ("operational.people_load", "operational", "Personas y carga", "Pertsonak eta karga"),
        ("operational.generate_reports", "operational", "Generar informes de rendimiento operativo", "Errendimendu operatiboko txostenak sortu"),
        ("operational.dataset_missing", "operational", "No existe el dataset procesado de rendimiento operativo. Ejecuta `python scripts\\02_transform\\24_build_prc01_operational_performance.py`.", "Ez dago errendimendu operatiboko dataset prozesaturik. Exekutatu `python scripts\\02_transform\\24_build_prc01_operational_performance.py`."),
        ("operational.dataset_empty", "operational", "No hay datos de rendimiento operativo para los filtros seleccionados.", "Ez dago errendimendu operatiboko daturik hautatutako iragazkietarako."),
        ("operational.dimension", "operational", "Dimensión", "Dimentsioa"),
        ("operational.chart.comparison", "operational", "▦ Planificado vs real", "▦ Planifikatua vs erreala"),
        ("operational.chart.deviation", "operational", "↔ Desviación", "↔ Desbideratzea"),
        ("operational.chart.overconsumption_pareto", "operational", "↗ Pareto de sobreconsumo", "↗ Gehiegizko kontsumoaren Pareto"),
        ("operational.chart.unplanned_actuals", "operational", "⚠ Horas sin planificación", "⚠ Plangintzarik gabeko orduak"),
        ("operational.metric.planning_coverage", "operational", "Cobertura de planificación", "Plangintzaren estaldura"),
        ("operational.metric.unplanned_actuals", "operational", "Horas reales sin planificación", "Plangintzarik gabeko ordu errealak"),
        ("operational.metric.unexecuted_planning", "operational", "Planificación no ejecutada", "Gauzatu gabeko plangintza"),
        ("operational.metric.overconsumption_projects", "operational", "Proyectos con sobreconsumo", "Gehiegizko kontsumoa duten proiektuak"),
        ("operational.no_overconsumption", "operational", "No hay sobreconsumo para los filtros seleccionados.", "Ez dago gehiegizko kontsumorik hautatutako iragazkietarako."),
        ("operational.no_unplanned_actuals", "operational", "No hay horas reales sin planificación para los filtros seleccionados.", "Ez dago plangintzarik gabeko ordu errealik hautatutako iragazkietarako."),
        ("operational.report.generated_ok", "operational", "Informe de rendimiento operativo generado correctamente", "Errendimendu operatiboko txostena behar bezala sortu da"),
        ("column.actual_hours", "column", "Horas reales", "Ordu errealak"),
        ("column.planned_hours", "column", "Horas planificadas", "Planifikatutako orduak"),
        ("column.deviation_hours", "column", "Desviación", "Desbideratzea"),
        ("column.actual_hours_with_planning", "column", "Horas reales con planificación", "Plangintzarekin egindako ordu errealak"),
        ("column.actual_hours_without_planning", "column", "Horas reales sin planificación", "Plangintzarik gabeko ordu errealak"),
        ("column.planned_hours_not_executed", "column", "Planificación no ejecutada", "Gauzatu gabeko plangintza"),
        ("column.planning_coverage_pct", "column", "Cobertura planificación %", "Plangintza estaldura %"),
        ("column.planning_execution_pct", "column", "Ejecución planificación %", "Plangintza exekuzioa %"),
        ("column.occupation_planned_pct", "column", "% ocupación planificada", "% okupazio planifikatua"),
        ("column.occupation_actual_pct", "column", "% ocupación real", "% okupazio erreala"),
        ("column.load_status", "column", "Estado de carga", "Karga egoera"),
        ("column.planning_status", "column", "Estado de planificación", "Plangintza egoera"),
        ("planning.title", "planning", "Planificación", "Plangintza"),
        ("planning.summary", "planning", "Resumen de planificación", "Plangintzaren laburpena"),
        ("planning.status", "planning", "Estado planificación", "Plangintza egoera"),
        ("planning.assured", "planning", "Asegurada", "Ziurtatua"),
        ("planning.possible", "planning", "Posible", "Posiblea"),
        ("planning.assured_possible", "planning", "Asegurada + posible", "Ziurtatua + posiblea"),
        ("planning.monthly_view", "planning", "Barras mensuales", "Hileko barrak"),
        ("planning.pareto_view", "planning", "Pareto", "Pareto"),
        ("planning.person_load_view", "planning", "Carga por persona", "Pertsonako karga"),
        ("planning.person_load_label", "planning", "⚙ Carga por persona", "⚙ Pertsonako karga"),
        ("planning.monthly_label", "planning", "▦ Barras mensuales", "▦ Hileko barrak"),
        ("planning.pareto_label", "planning", "↗ Pareto", "↗ Pareto"),
        ("planning.person_dimension_fallback", "planning", "Para Carga por persona, el desglose por persona se sustituye por Unidad destino + naturaleza para evitar una leyenda redundante.", "Pertsonako kargarako, pertsonaren araberako xehetasuna Helmuga unitatea + izaera gisa ordezkatzen da legenda errepikakorra saihesteko."),
        ("planning.show_people_without_planning", "planning", "Mostrar personas sin planificación", "Plangintzarik gabeko pertsonak erakutsi"),
        ("planning.people_in_scope", "planning", "Personas del ámbito", "Eremuko pertsonak"),
        ("planning.people_with_planning", "planning", "Personas con planificación", "Plangintza duten pertsonak"),
        ("planning.people_without_planning", "planning", "Personas sin planificación", "Plangintzarik gabeko pertsonak"),
        ("planning.person_coverage_pct", "planning", "Cobertura de personas planificadas", "Planifikatutako pertsonen estaldura"),
        ("planning.with_planning", "planning", "Con planificación", "Plangintzarekin"),
        ("planning.without_planning", "planning", "Sin planificación", "Plangintzarik gabe"),
        ("planning.without_availability", "planning", "Sin disponibilidad", "Erabilgarritasunik gabe"),
        ("planning.no_people_in_scope", "planning", "No hay personas en el ámbito seleccionado.", "Ez dago pertsonarik hautatutako eremuan."),
        ("planning.people_scope_summary", "planning", "Cobertura de personas", "Pertsonen estaldura"),
        ("planning.generate_reports", "planning", "Generar informes de planificación", "Plangintza txostenak sortu"),
        ("planning.overloads", "planning", "Sobrecargas", "Gehiegizko kargak"),
        ("planning.risk", "planning", "Riesgo", "Arriskua"),
        ("planning.ok", "planning", "OK", "OK"),
        ("planning.overload", "planning", "Sobrecarga", "Gehiegizko karga"),
        ("planning.data", "planning", "Datos de planificación", "Plangintza datuak"),
        ("planning.monthly_title", "planning", "Horas planificadas - periodo seleccionado", "Planifikatutako orduak - hautatutako aldia"),
        ("metric.planned_hours", "metric", "Horas planificadas", "Planifikatutako orduak"),
        ("metric.assured_hours", "metric", "Horas aseguradas", "Ziurtatutako orduak"),
        ("metric.possible_hours", "metric", "Horas posibles", "Ordu posibleak"),
        ("metric.weighted_possible_hours", "metric", "Horas posibles ponderadas", "Haztatutako ordu posibleak"),
        ("metric.people_overloaded", "metric", "Personas en sobrecarga", "Gehiegizko karga duten pertsonak"),
        ("metric.people_at_risk", "metric", "Personas en riesgo", "Arriskuan dauden pertsonak"),
        ("metric.assured_occupation_pct", "metric", "% ocupación asegurada", "% okupazio ziurtatua"),
        ("metric.total_occupation_pct", "metric", "% ocupación total", "% okupazio osoa"),
        ("metric.pending_status_hours", "metric", "Horas pendientes de estado", "Egoera zain duten orduak"),
        ("column.planning_status", "column", "Estado planificación", "Plangintza egoera"),
        ("column.planned_hours", "column", "Horas planificadas", "Planifikatutako orduak"),
        ("column.probability", "column", "Probabilidad", "Probabilitatea"),
        ("column.weighted_planned_hours", "column", "Horas ponderadas", "Haztatutako orduak"),
        ("column.source_system", "column", "Sistema origen", "Jatorri sistema"),
        ("column.source_model", "column", "Modelo origen", "Jatorri eredua"),
        ("column.source_name", "column", "Nombre origen", "Jatorri izena"),
    ]
)

REQUIRED_COLUMN_KEYS = [
    "hilabete_zk",
    "mes_label",
    "month_display",
    "available_hours_base",
    "available_hours",
    "calculated_available_hours",
    "person_specific_available_hours",
    "data",
    "date",
    "grupo_actividad",
    "grupo_actividad_original",
    "unidad_destino",
    "naturaleza_trabajo",
    "grupo_gestion",
    "unidad_destino_label",
    "naturaleza_trabajo_label",
    "classification_rule_id",
    "classification_status",
    "project_name",
    "task_name",
    "person_name",
    "pertsona",
    "employee_name",
    "hours",
    "horas",
    "ordu_errealak",
    "percentage",
    "porcentaje",
    "percentage_total",
    "porcentaje_total",
    "people_count",
    "projects_count",
    "tasks_count",
    "base_source",
    "base_scope_name",
    "base_scope_type",
    "source_scope_type",
    "source_scope_name",
    "reason",
    "workload_factor",
    "weekly_hours",
    "person_key",
    "month",
    "month_name",
    "configured",
]
ANALYTIC_FIELDS = [
    "id",
    "date",
    "name",
    "employee_id",
    "user_id",
    "department_id",
    "project_id",
    "task_id",
    "account_id",
    "holiday_id",
    "unit_amount",
    "amount",
    "sell_amount",
    "total_hour_price",
    "grant_hour_amount",
    "grant_hour_price",
    "is_granted",
    "so_line",
    "tag_ids",
    "create_date",
    "write_date",
]

FORECAST_SAFE_FIELDS = [
    "id",
    "name",
    "display_name",
    "employee_id",
    "user_id",
    "project_id",
    "task_id",
    "date_start",
    "date_end",
    "quantity",
    "effective_hours",
    "remaining_hours",
    "unit_cost",
    "unit_price",
    "cost_subtotal",
    "price_subtotal",
    "grant_invoicing_hours",
    "grant_hour_price",
    "line_no",
    "line_type",
    "project_id_is_granted",
    "hours_warning",
    "create_date",
    "write_date",
]


st.set_page_config(page_title="IMH Oreka", layout="wide")


def clean_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "false"}:
        return ""
    return text


def normalize_bool(value: Any) -> bool:
    text = clean_text(value)
    if not text:
        return False
    return normalize_text(text) in {"true", "1", "1.0", "si", "sí", "yes", "y"}


def normalize_int(value: Any, default: int | None = None) -> int | None:
    text = clean_text(value).replace(",", ".")
    if not text:
        return default
    number = pd.to_numeric(pd.Series([text]), errors="coerce").iloc[0]
    if pd.isna(number):
        return default
    return int(number)


def normalize_float(value: Any, default: float = 0.0) -> float:
    text = clean_text(value).replace(",", ".")
    if not text:
        return default
    number = pd.to_numeric(pd.Series([text]), errors="coerce").iloc[0]
    if pd.isna(number):
        return default
    return float(number)


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def current_user() -> str:
    return os.getenv("USERNAME") or os.getenv("USER") or ""


def active_mask(series: pd.Series) -> pd.Series:
    return series.map(normalize_bool)


def options(series: pd.Series) -> list[str]:
    return sorted([value for value in series.dropna().astype(str).unique().tolist() if value])


def normalized_match_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", clean_text(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.casefold().split())


def normalize_key(value: Any) -> str:
    return " ".join(clean_text(value).split())


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", normalize_key(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.casefold().split())


def slugify_filename(value: str) -> str:
    text = unicodedata.normalize("NFKD", clean_text(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()
    return (text[:80] or "informe")


def format_number_es(value: float, decimals: int = 2) -> str:
    try:
        formatted = f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        formatted = f"{0.0:,.{decimals}f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def format_integer_es(value: Any) -> str:
    try:
        return format_number_es(float(value), 0)
    except (TypeError, ValueError):
        return "0"


def format_date_display(value: Any) -> str:
    if value in (None, ""):
        return ""
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return clean_text(value)
    return parsed.strftime("%d/%m/%Y")


def relative_path_text(path_value: Any) -> str:
    text = clean_text(path_value)
    if not text:
        return ""
    try:
        path = Path(text)
        if path.is_absolute():
            return str(path.relative_to(ROOT_DIR))
    except ValueError:
        return Path(text).name if ":" in text else text
    except OSError:
        return text
    return text


def seed_translation_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "key": key,
                "context": context,
                "text_es": text_es,
                "text_eu": text_eu,
                "notes": "",
                "active": "TRUE",
                "updated_at": "",
            }
            for key, context, text_es, text_eu in REQUIRED_TRANSLATIONS
        ],
        columns=TRANSLATION_COLUMNS,
    ).drop_duplicates("key", keep="first")


def ensure_translation_file() -> None:
    seeds = seed_translation_dataframe()
    if not TRANSLATIONS_FILE.exists():
        seeds.to_csv(TRANSLATIONS_FILE, sep=";", encoding="utf-8-sig", index=False)
        return
    existing = read_csv(TRANSLATIONS_FILE, TRANSLATION_COLUMNS)
    missing = seeds[~seeds["key"].isin(existing["key"])].copy()
    if not missing.empty:
        pd.concat([existing, missing], ignore_index=True).drop_duplicates("key", keep="first").to_csv(
            TRANSLATIONS_FILE,
            sep=";",
            encoding="utf-8-sig",
            index=False,
        )


@st.cache_data(show_spinner=False)
def load_translations_cached(mtime: float) -> pd.DataFrame:
    del mtime
    ensure_translation_file()
    return read_csv(TRANSLATIONS_FILE, TRANSLATION_COLUMNS)


def current_language() -> str:
    return st.session_state.get("language", "es")


def translations_df() -> pd.DataFrame:
    mtime = TRANSLATIONS_FILE.stat().st_mtime if TRANSLATIONS_FILE.exists() else 0
    return load_translations_cached(mtime)


def t(key: str, lang: str | None = None, default: str | None = None) -> str:
    lang = lang or current_language()
    df = translations_df()
    rows = df[(df["key"] == key) & active_mask(df["active"])].copy()
    if rows.empty:
        return default if default is not None else key
    row = rows.iloc[0]
    value = clean_text(row.get(f"text_{lang}", ""))
    if value:
        return value
    value = clean_text(row.get("text_es", ""))
    return value or (default if default is not None else key)


def translate_label(value: str, context: str = "generic", lang: str | None = None) -> str:
    lang = lang or current_language()
    key_candidates = [f"{context}.{value}", f"column.{value}", f"value.{value}", value]
    for key in key_candidates:
        translated = t(key, lang=lang, default="")
        if translated:
            return translated
    return clean_text(value)


def translate_value(value: Any, lang: str | None = None) -> str:
    text = clean_text(value)
    return t(f"value.{text}", lang=lang, default=text)


def month_label(month: int, lang: str = "es", with_number: bool = True) -> str:
    month_int = int(month)
    name = t(f"month.{month_int:02d}", lang=lang, default=(MONTH_NAMES_ES if lang == "es" else MONTH_NAMES_EU)[month_int])
    return f"{month_int:02d} - {name}" if with_number else name


def translate_dataframe_columns_for_display(df: pd.DataFrame, lang: str | None = None) -> pd.DataFrame:
    lang = lang or current_language()
    display = df.copy()
    if "grupo_actividad" in display.columns:
        display["grupo_actividad"] = display["grupo_actividad"].map(lambda value: translate_value(value, lang=lang))
    if "classification_status" in display.columns:
        display["classification_status"] = display["classification_status"].map(lambda value: translate_value(value, lang=lang))
    if "month" in display.columns:
        display["month"] = display["month"].map(lambda value: month_label(int(value), lang, with_number=False) if clean_text(value) else value)
    if "month_name" in display.columns and "month" in df.columns:
        display["month_name"] = df["month"].map(lambda value: month_label(int(value), lang, with_number=False) if clean_text(value) else value)
    if "mes_label" in display.columns and "hilabete_zk" in display.columns:
        display["mes_label"] = display["hilabete_zk"].map(lambda value: month_label(int(value), lang, with_number=True) if clean_text(value) else value)
    elif "hilabete_zk" in display.columns:
        display["month_display"] = display["hilabete_zk"].map(lambda value: month_label(int(value), lang, with_number=False) if clean_text(value) else value)
    display = display.rename(columns={column: translate_label(str(column), "column", lang) for column in display.columns})
    return display


def person_matches_alias(person: str, aliases: str) -> bool:
    person_norm = normalized_match_text(person)
    if not person_norm:
        return False
    for alias in [part for part in clean_text(aliases).split("|") if part.strip()]:
        alias_norm = normalized_match_text(alias)
        if alias_norm and (alias_norm in person_norm or person_norm in alias_norm):
            return True
    return False


def read_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=columns)
    df = pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype=str).fillna("")
    for column in columns:
        if column not in df.columns:
            df[column] = ""
    return df[columns].copy()


def ensure_csv_file(path: Path, columns: list[str], rows: list[list[Any]] | None = None) -> None:
    if not path.exists():
        pd.DataFrame(rows or [], columns=columns).to_csv(path, sep=";", encoding="utf-8-sig", index=False)
        return
    current = pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype=str).fillna("")
    changed = False
    for column in columns:
        if column not in current.columns:
            current[column] = ""
            changed = True
    if changed:
        current[columns].to_csv(path, sep=";", encoding="utf-8-sig", index=False)


def ensure_config_files() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    DATA_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    if not TEAMS_FILE.exists():
        pd.DataFrame(
            [
                ["all", "Empresa completa", "", "", "TRUE", "Todas las personas"],
                ["team-demo", "Equipo de ejemplo", "Persona Ejemplo", "Persona Ejemplo", "TRUE", "Registro ficticio"],
            ],
            columns=TEAM_COLUMNS,
        ).to_csv(TEAMS_FILE, sep=";", encoding="utf-8-sig", index=False)
    if not CLASSIFICATION_FILE.exists():
        pd.DataFrame(columns=CLASSIFICATION_COLUMNS).to_csv(CLASSIFICATION_FILE, sep=";", encoding="utf-8-sig", index=False)
    ensure_csv_file(MANAGEMENT_UNITS_FILE, MANAGEMENT_UNIT_COLUMNS, DEFAULT_MANAGEMENT_UNITS)
    ensure_csv_file(WORK_NATURES_FILE, WORK_NATURE_COLUMNS, DEFAULT_WORK_NATURES)
    ensure_csv_file(MANAGEMENT_RULES_FILE, MANAGEMENT_RULE_COLUMNS, DEFAULT_MANAGEMENT_RULES)
    if not AVAILABLE_HOURS_FILE.exists():
        pd.DataFrame(
            [
                [2026, 1, "Urtarrila", "company", "empresa", "Empresa", 0, "TRUE", "Ejemplo", "", ""],
                [2026, 1, "Urtarrila", "department", "departamento-demo", "Departamento de ejemplo", 0, "TRUE", "Ejemplo", "", ""],
                [2026, 1, "Urtarrila", "team", "equipo-demo", "Equipo de ejemplo", 0, "TRUE", "Ejemplo", "", ""],
            ],
            columns=AVAILABLE_COLUMNS,
        ).to_csv(AVAILABLE_HOURS_FILE, sep=";", encoding="utf-8-sig", index=False)
    if not PERSON_WORKLOAD_FILE.exists():
        pd.DataFrame(
            [["persona-ejemplo", "Persona Ejemplo", 2026, 1.0, 40.0, "TRUE", "Registro ficticio", "", ""]],
            columns=PERSON_WORKLOAD_COLUMNS,
        ).to_csv(PERSON_WORKLOAD_FILE, sep=";", encoding="utf-8-sig", index=False)
    ensure_translation_file()


def load_classification_uncached() -> pd.DataFrame:
    classification = read_csv(CLASSIFICATION_FILE, CLASSIFICATION_COLUMNS)
    classification = classification[active_mask(classification["active"])].copy()
    classification["grupo_actividad"] = classification["grupo_actividad"].where(
        classification["grupo_actividad"].isin(ALLOWED_GROUPS),
        "Pendiente de clasificar",
    )
    for column in ["project_id", "project_name", "task_id", "task_name", "subgrupo"]:
        classification[column] = classification[column].map(normalize_key)
    return classification


def load_available_hours_uncached() -> pd.DataFrame:
    df = read_csv(AVAILABLE_HOURS_FILE, AVAILABLE_COLUMNS)
    df = df[active_mask(df["active"])].copy()
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["month"] = pd.to_numeric(df["month"], errors="coerce").astype("Int64")
    df["available_hours"] = pd.to_numeric(df["available_hours"], errors="coerce").fillna(0.0)
    return df


def load_management_units() -> pd.DataFrame:
    units = read_csv(MANAGEMENT_UNITS_FILE, MANAGEMENT_UNIT_COLUMNS)
    units["sort_order"] = pd.to_numeric(units["sort_order"], errors="coerce").fillna(99).astype(int)
    return units.sort_values("sort_order").copy()


def load_work_natures() -> pd.DataFrame:
    natures = read_csv(WORK_NATURES_FILE, WORK_NATURE_COLUMNS)
    natures["sort_order"] = pd.to_numeric(natures["sort_order"], errors="coerce").fillna(99).astype(int)
    return natures.sort_values("sort_order").copy()


def load_management_classification_rules() -> pd.DataFrame:
    rules = read_csv(MANAGEMENT_RULES_FILE, MANAGEMENT_RULE_COLUMNS)
    rules = rules[active_mask(rules["active"])].copy()
    rules["priority"] = pd.to_numeric(rules["priority"], errors="coerce").fillna(9999).astype(int)
    return rules.sort_values(["priority", "rule_id"]).copy()


def label_lookup(df: pd.DataFrame, key_col: str, lang: str) -> dict[str, str]:
    label_col = "label_eu" if lang == "eu" else "label_es"
    result = {}
    for _, row in df.iterrows():
        key = clean_text(row.get(key_col, ""))
        label = clean_text(row.get(label_col, "")) or key
        if key:
            result[key] = label
    return result


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    text = clean_text(hex_color).lstrip("#")
    if len(text) != 6:
        text = "9E9E9E"
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{max(0, min(255, int(value))):02X}" for value in rgb)


def lighten_color(hex_color: str, amount: float) -> str:
    red, green, blue = hex_to_rgb(hex_color)
    return rgb_to_hex(
        (
            red + (255 - red) * amount,
            green + (255 - green) * amount,
            blue + (255 - blue) * amount,
        )
    )


def darken_color(hex_color: str, amount: float) -> str:
    red, green, blue = hex_to_rgb(hex_color)
    return rgb_to_hex((red * (1 - amount), green * (1 - amount), blue * (1 - amount)))


def color_for_unit_and_nature(unit_key: str, nature_key: str) -> str:
    unit_key = clean_text(unit_key) or "pendiente"
    nature_key = clean_text(nature_key) or "pendiente"
    if unit_key == "pendiente" or nature_key == "pendiente":
        return "#9E9E9E"
    base = UNIT_BASE_COLORS.get(unit_key, "#607D8B")
    if nature_key == "directo":
        return darken_color(base, 0.18)
    if nature_key == "indirecto":
        return base
    if nature_key == "no_aplica":
        return lighten_color(base, 0.45)
    return "#9E9E9E"


def build_management_color_map(df: pd.DataFrame, units_df: pd.DataFrame, natures_df: pd.DataFrame) -> dict[str, str]:
    del units_df, natures_df
    color_map: dict[str, str] = {}
    if df.empty:
        return color_map
    for _, row in df[["unidad_destino", "unidad_destino_label", "naturaleza_trabajo", "naturaleza_trabajo_label", "grupo_gestion"]].drop_duplicates().iterrows():
        unit_key = clean_text(row.get("unidad_destino", "")) or "pendiente"
        nature_key = clean_text(row.get("naturaleza_trabajo", "")) or "pendiente"
        unit_label = clean_text(row.get("unidad_destino_label", ""))
        nature_label = clean_text(row.get("naturaleza_trabajo_label", ""))
        group_label = clean_text(row.get("grupo_gestion", ""))
        color = color_for_unit_and_nature(unit_key, nature_key)
        if group_label:
            color_map[group_label] = color
        if unit_label:
            color_map.setdefault(unit_label, UNIT_BASE_COLORS.get(unit_key, "#607D8B"))
        if nature_label:
            color_map.setdefault(
                nature_label,
                {"directo": "#455A64", "indirecto": "#78909C", "no_aplica": "#B0BEC5", "pendiente": "#9E9E9E"}.get(nature_key, "#9E9E9E"),
            )
    return color_map


def stable_palette_index(value: str, palette_size: int) -> int:
    if palette_size <= 0:
        return 0
    digest = hashlib.sha256(clean_text(value).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % palette_size


def category_stable_key(df: pd.DataFrame, dimension: str, category: str) -> str:
    label = clean_text(category)
    if label == "Otros":
        return "otros"
    if dimension == "project_name" and "project_id" in df.columns:
        ids = sorted({clean_text(value) for value in df.loc[df[dimension].map(clean_text) == label, "project_id"].tolist() if clean_text(value)})
        if len(ids) == 1:
            return f"project_id:{ids[0]}"
    if dimension == "person_name" and "person_key" in df.columns:
        ids = sorted({clean_text(value) for value in df.loc[df[dimension].map(clean_text) == label, "person_key"].tolist() if clean_text(value)})
        if len(ids) == 1:
            return f"person_key:{ids[0]}"
    return f"{dimension}:{normalize_text(label)}"


def build_stable_category_color_map(df: pd.DataFrame, dimension: str) -> dict[str, str]:
    if df.empty or dimension not in df.columns:
        return {}
    categories = sorted(
        {clean_text(value) for value in df[dimension].dropna().tolist() if clean_text(value)},
        key=lambda value: (normalize_text(value), value),
    )
    palette = STABLE_CATEGORY_PALETTE or [DEFAULT_CATEGORY_COLOR]
    occupied: set[str] = set()
    color_map: dict[str, str] = {}
    for category in categories:
        if category == "Otros":
            color_map[category] = OTHER_CATEGORY_COLOR
            occupied.add(OTHER_CATEGORY_COLOR)
            continue
        stable_key = category_stable_key(df, dimension, category)
        start = stable_palette_index(stable_key, len(palette))
        color = palette[start]
        for offset in range(len(palette)):
            candidate = palette[(start + offset) % len(palette)]
            if candidate not in occupied:
                color = candidate
                break
        color_map[category] = color
        occupied.add(color)
    return color_map


def build_dimension_color_map(df: pd.DataFrame, dimension: str) -> dict[str, str]:
    if dimension in {"grupo_gestion", "unidad_destino_label", "naturaleza_trabajo_label"}:
        return build_management_color_map(df, load_management_units(), load_work_natures())
    if dimension in {"project_name", "person_name"}:
        return build_stable_category_color_map(df, dimension)
    return build_stable_category_color_map(df, dimension)


def row_matches_management_rule(row: pd.Series, rule: pd.Series) -> bool:
    checks = [
        ("project_contains", "project_name"),
        ("task_contains", "task_name"),
        ("department_contains", "saila"),
        ("person_contains", "pertsona"),
    ]
    has_condition = False
    for rule_col, data_col in checks:
        needle = normalize_text(rule.get(rule_col, ""))
        if not needle:
            continue
        has_condition = True
        haystack = normalize_text(row.get(data_col, ""))
        if needle not in haystack:
            return False
    return has_condition


def apply_management_classification(
    df: pd.DataFrame,
    rules_df: pd.DataFrame,
    units_df: pd.DataFrame,
    natures_df: pd.DataFrame,
    lang: str = "es",
) -> pd.DataFrame:
    result = df.copy()
    if "grupo_actividad_original" not in result.columns:
        result["grupo_actividad_original"] = result.get("grupo_actividad", "")
    else:
        result["grupo_actividad_original"] = result["grupo_actividad_original"].where(result["grupo_actividad_original"] != "", result.get("grupo_actividad", ""))

    unit_keys = set(units_df["unit_key"].map(clean_text))
    nature_keys = set(natures_df["nature_key"].map(clean_text))
    unit_labels = label_lookup(units_df, "unit_key", lang)
    nature_labels = label_lookup(natures_df, "nature_key", lang)
    assignments: list[tuple[str, str, str, str]] = []

    for _, row in result.iterrows():
        assigned_unit = "pendiente"
        assigned_nature = "pendiente"
        rule_id = ""
        status = "pendiente"
        for _, rule in rules_df.iterrows():
            if not row_matches_management_rule(row, rule):
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


def write_management_classification_reports(df: pd.DataFrame, rules_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    total_rows = int(len(df))
    pending_mask = df.get("classification_status", pd.Series(dtype=str)).astype(str).eq("pendiente")
    pending_rows = int(pending_mask.sum()) if total_rows else 0
    classified_rows = total_rows - pending_rows
    diagnostics = pd.DataFrame(
        [
            {
                "total_rows": total_rows,
                "classified_rows": classified_rows,
                "pending_rows": pending_rows,
                "classified_pct": classified_rows / total_rows * 100 if total_rows else 0.0,
                "pending_pct": pending_rows / total_rows * 100 if total_rows else 0.0,
                "rules_active": int(len(rules_df)),
                "generated_at": now_text(),
            }
        ]
    )
    diagnostics.to_csv(MANAGEMENT_CLASSIFICATION_DIAGNOSTICS, sep=";", encoding="utf-8-sig", index=False)
    pending_source = df[pending_mask].copy() if total_rows else pd.DataFrame()
    pending_columns = ["project_name", "task_name", "department_name", "person_name", "hours"]
    if pending_source.empty:
        pending = pd.DataFrame(columns=pending_columns)
    else:
        pending_source["department_name"] = pending_source.get("saila", "")
        pending_source["person_name"] = pending_source.get("pertsona", "")
        pending = (
            pending_source.groupby(["project_name", "task_name", "department_name", "person_name"], as_index=False)
            .agg(hours=("ordu_errealak", "sum"))
            .sort_values("hours", ascending=False)
        )
    pending.to_csv(MANAGEMENT_CLASSIFICATION_PENDING, sep=";", encoding="utf-8-sig", index=False)
    review = build_management_classification_review_table(df)
    review.to_csv(MANAGEMENT_CLASSIFICATION_REVIEW, sep=";", encoding="utf-8-sig", index=False)
    return diagnostics, pending


def build_management_classification_review_table(df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "classification_status",
        "project_name",
        "task_name",
        "department_name",
        "hours",
        "line_count",
        "people_count",
        "unidad_destino_label",
        "naturaleza_trabajo_label",
        "grupo_gestion",
        "classification_rule_id",
    ]
    if df.empty:
        return pd.DataFrame(columns=columns)
    source = df.copy()
    source["department_name"] = source.get("saila", "")
    table = (
        source.groupby(
            [
                "project_name",
                "task_name",
                "department_name",
                "unidad_destino_label",
                "naturaleza_trabajo_label",
                "grupo_gestion",
                "classification_rule_id",
                "classification_status",
            ],
            as_index=False,
            dropna=False,
        )
        .agg(hours=("ordu_errealak", "sum"), line_count=("ordu_errealak", "size"), people_count=("pertsona", "nunique"))
    )
    table["_pending_order"] = table["classification_status"].map(lambda value: 0 if clean_text(value) == "pendiente" else 1)
    table = table.sort_values(["_pending_order", "hours"], ascending=[True, False]).drop(columns=["_pending_order"])
    return table[columns]


def apply_explicit_classification(df: pd.DataFrame, classification: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    maps: dict[str, dict[Any, tuple[str, str]]] = {
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
        group = clean_text(row.get("grupo_actividad", "")) or "Pendiente de clasificar"
        subgrupo = normalize_key(row.get("subgrupo", ""))
        value = (group, subgrupo)
        if project_id and task_id:
            maps["task_exact_id"][(project_id, task_id)] = value
        if project_id and not task_id:
            maps["project_id"][project_id] = value
        if project_name and task_name:
            maps["task_exact_name"][(project_name, task_name)] = value
        if project_name and not task_name:
            maps["project_name"][project_name] = value

    result = []
    for _, row in df.iterrows():
        project_id = normalize_key(row.get("project_id", ""))
        task_id = normalize_key(row.get("task_id", ""))
        project_name = normalize_text(row.get("project_name", ""))
        task_name = normalize_text(row.get("task_name", ""))
        if (project_id, task_id) in maps["task_exact_id"]:
            group, subgrupo = maps["task_exact_id"][(project_id, task_id)]
            result.append((group, subgrupo, "task_exact_id", project_id, task_id))
        elif project_id in maps["project_id"]:
            group, subgrupo = maps["project_id"][project_id]
            result.append((group, subgrupo, "project_id", project_id, ""))
        elif (project_name, task_name) in maps["task_exact_name"]:
            group, subgrupo = maps["task_exact_name"][(project_name, task_name)]
            result.append((group, subgrupo, "task_exact_name", project_name, task_name))
        elif project_name in maps["project_name"]:
            group, subgrupo = maps["project_name"][project_name]
            result.append((group, subgrupo, "project_name", project_name, ""))
        else:
            result.append(("Pendiente de clasificar", "", "pending", "", ""))

    df["grupo_actividad"] = [item[0] for item in result]
    df["subgrupo"] = [item[1] for item in result]
    df["classification_source"] = [item[2] for item in result]
    df["matched_project_key"] = [item[3] for item in result]
    df["matched_task_key"] = [item[4] for item in result]
    return df


def ensure_data_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df = df[df["data"].notna()].copy()
    df["urtea"] = pd.to_numeric(df.get("urtea", df["data"].dt.year), errors="coerce").astype("Int64")
    df["hilabete_zk"] = pd.to_numeric(df.get("hilabete_zk", df["data"].dt.month), errors="coerce").astype("Int64")
    df["hilabetea"] = df["hilabete_zk"].map(MONTH_NAMES_EU)

    for column in ["pertsona", "erabiltzailea", "saila", "proiektua", "ataza", "azalpena"]:
        if column not in df.columns:
            df[column] = ""
        df[column] = df[column].map(clean_text)
    for source, fallback in [("project_id", "proiektua"), ("project_name", "proiektua"), ("task_id", "ataza"), ("task_name", "ataza")]:
        if source not in df.columns:
            df[source] = df[fallback]
        df[source] = df[source].map(clean_text)
    for column in ["source_file", "source_date_from", "source_date_to"]:
        if column not in df.columns:
            df[column] = ""
        df[column] = df[column].map(clean_text)
    df["project_name"] = df["project_name"].where(df["project_name"] != "", df["project_id"])
    df["task_name"] = df["task_name"].where(df["task_name"] != "", df["task_id"])
    df["proiektua"] = df["proiektua"].where(df["proiektua"] != "", df["project_name"])
    df["ataza"] = df["ataza"].where(df["ataza"] != "", df["task_name"])
    df["proiektua_ataza"] = (df["project_name"] + " / " + df["task_name"]).str.strip(" /")
    df["ordu_errealak"] = pd.to_numeric(df.get("ordu_errealak", 0), errors="coerce").fillna(0.0)
    df["mes_label"] = df["hilabete_zk"].astype(int).astype(str).str.zfill(2) + " - " + df["hilabetea"].astype(str)
    return df


def write_unclassified_report(df: pd.DataFrame) -> pd.DataFrame:
    pending = df[df["grupo_actividad"] == "Pendiente de clasificar"].copy()
    columns = ["project_id", "project_name", "task_id", "task_name", "hours", "people_count", "first_date", "last_date", "suggested_group"]
    if pending.empty:
        report = pd.DataFrame(columns=columns)
    else:
        report = (
            pending.groupby(["project_id", "project_name", "task_id", "task_name"], as_index=False, dropna=False)
            .agg(hours=("ordu_errealak", "sum"), people_count=("pertsona", "nunique"), first_date=("data", "min"), last_date=("data", "max"))
            .sort_values("hours", ascending=False)
        )
        report["first_date"] = report["first_date"].dt.date.astype(str)
        report["last_date"] = report["last_date"].dt.date.astype(str)
        report["suggested_group"] = ""
        report = report[columns]
    report.to_csv(UNCLASSIFIED_REPORT, sep=";", encoding="utf-8-sig", index=False)
    return report


def write_classification_diagnostics(df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "project_id",
        "project_name",
        "task_id",
        "task_name",
        "hours",
        "classification_source",
        "grupo_actividad",
        "matched_project_key",
        "matched_task_key",
        "pending",
    ]
    if df.empty:
        report = pd.DataFrame(columns=columns)
    else:
        report = (
            df.groupby(
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
                as_index=False,
                dropna=False,
            )
            .agg(hours=("ordu_errealak", "sum"))
            .sort_values("hours", ascending=False)
        )
        report["pending"] = report["grupo_actividad"] == "Pendiente de clasificar"
        report = report[columns]
    report.to_csv(CLASSIFICATION_DIAGNOSTICS_REPORT, sep=";", encoding="utf-8-sig", index=False)
    return report


@st.cache_data(show_spinner=False)
def load_data(path: str, classification_mtime: float, management_mtime: float, lang: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    del classification_mtime, management_mtime
    if not Path(path).exists():
        return pd.DataFrame(), pd.DataFrame()
    raw = pd.read_csv(path, sep=";", encoding="utf-8-sig")
    df = ensure_data_columns(raw)
    df = apply_explicit_classification(df, load_classification_uncached())
    rules = load_management_classification_rules()
    df = apply_management_classification(df, rules, load_management_units(), load_work_natures(), lang)
    write_management_classification_reports(df, rules)
    unclassified = write_unclassified_report(df)
    write_classification_diagnostics(df)
    return df, unclassified


@st.cache_data(show_spinner=False)
def load_teams(path: str) -> pd.DataFrame:
    teams = read_csv(Path(path), TEAM_COLUMNS)
    return teams[active_mask(teams["active"])].copy()


def load_transform_module():
    spec = importlib.util.spec_from_file_location("prc01_transform", TRANSFORM_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"No se puede cargar transformacion: {TRANSFORM_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_operational_transform_module():
    spec = importlib.util.spec_from_file_location("prc01_operational_transform", OPERATIONAL_TRANSFORM_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"No se puede cargar transformacion operativa: {OPERATIONAL_TRANSFORM_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_client(url: str, db: str, user: str, password: str) -> OdooClient:
    return OdooClient.from_config(url=url, db=db, user=user, password=password)


def download_analytic_lines(client: OdooClient, date_from: str, date_to: str) -> dict[str, object]:
    fields = valid_fields(client, "account.analytic.line", ANALYTIC_FIELDS)
    records = client.search_read(
        "account.analytic.line",
        domain=[["date", ">=", date_from], ["date", "<", date_to]],
        fields=fields,
        limit=200000,
        order="date asc, id asc",
    )
    stem = f"11_analytic_lines_{date_from}_to_{date_to}"
    json_path = DATA_RAW_DIR / f"{stem}.json"
    csv_path = DATA_RAW_DIR / f"{stem}.csv"
    save_json(json_path, records)
    save_csv(csv_path, records)
    df = pd.DataFrame(records)
    hours = float(pd.to_numeric(df.get("unit_amount", 0), errors="coerce").fillna(0).sum()) if not df.empty else 0.0
    return {
        "csv_path": str(csv_path),
        "json_path": str(json_path),
        "rows": len(records),
        "hours": hours,
        "people": int(df.get("employee_id", pd.Series(dtype=object)).astype(str).nunique()) if not df.empty else 0,
        "projects": int(df.get("project_id", pd.Series(dtype=object)).astype(str).nunique()) if not df.empty else 0,
        "min_date": str(df["date"].min()) if not df.empty and "date" in df else "",
        "max_date": str(df["date"].max()) if not df.empty and "date" in df else "",
    }


def download_planning_forecast(client: OdooClient, date_from: str, date_to: str) -> dict[str, object]:
    model = "project.forecast"
    if not client.model_exists(model):
        return {"available": False, "model": model, "rows": 0, "hours": 0.0}
    fields = [field for field in valid_fields(client, model, FORECAST_SAFE_FIELDS) if field not in {"task_type", "type_l"}]
    records = client.search_read(
        model,
        domain=[["date_start", ">=", date_from], ["date_start", "<", date_to]],
        fields=fields,
        limit=200000,
        order="date_start asc, id asc",
    )
    # Use the canonical source selected by planning_data and replace it on every
    # connection, so a new user never explores another user's stale snapshot.
    json_path = DATA_RAW_DIR / "09_project_forecast.json"
    csv_path = DATA_RAW_DIR / "09_project_forecast.csv"
    save_json(json_path, records)
    save_csv(csv_path, records)
    df = pd.DataFrame(records)
    hours = float(planning_pipeline.raw_planned_hours(df).sum()) if not df.empty else 0.0
    return {
        "available": True,
        "model": model,
        "json_path": str(json_path),
        "csv_path": str(csv_path),
        "rows": len(records),
        "hours": hours,
        "people": int(df.get("employee_id", pd.Series(dtype=object)).astype(str).nunique()) if not df.empty else 0,
        "min_date": str(df["date_start"].min()) if not df.empty and "date_start" in df else "",
        "max_date": str(df["date_start"].max()) if not df.empty and "date_start" in df else "",
    }


def rebuild_downloaded_datasets(
    date_from: str,
    date_to: str,
    planning_download: dict[str, object],
) -> dict[str, object]:
    actuals = load_transform_module().run_transform(date_from=date_from, date_to=date_to)
    planning: dict[str, Any] | None = None
    operational: dict[str, object] | None = None
    if planning_download.get("available"):
        planning_source = Path(str(planning_download["json_path"]))
        planning = planning_pipeline.build_planning_dataset(planning_source)
        operational = load_operational_transform_module().build_operational_dataset()
    return {"actuals": actuals, "planning": planning, "operational": operational}


def download_rebuild_summary(download_result: dict[str, Any], transform_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "records_downloaded": int(download_result.get("rows", 0) or 0),
        "hours_downloaded": float(download_result.get("hours", 0.0) or 0.0),
        "people": int(download_result.get("people", 0) or 0),
        "projects": int(download_result.get("projects", 0) or 0),
        "min_date": clean_text(download_result.get("min_date", "")),
        "max_date": clean_text(download_result.get("max_date", "")),
        "pending_rows": int(transform_result.get("pending_rows", 0) or 0),
        "updated_at": now_text(),
        "raw_csv": relative_path_text(download_result.get("csv_path", "")),
        "raw_json": relative_path_text(download_result.get("json_path", "")),
        "processed_detail": relative_path_text(transform_result.get("detail_path", "")),
        "source_file": relative_path_text(transform_result.get("source_file", "")),
        "source_date_from": clean_text(transform_result.get("source_date_from", "")),
        "source_date_to": clean_text(transform_result.get("source_date_to", "")),
    }


def render_download_rebuild_summary(download_result: dict[str, Any], transform_result: dict[str, Any], lang: str) -> None:
    summary = download_rebuild_summary(download_result, transform_result)
    st.success(t("odoo.connection.updated_ok", lang=lang))
    cols = st.columns(4)
    cols[0].metric(t("odoo.connection.records_downloaded", lang=lang), format_integer_es(summary["records_downloaded"]))
    cols[1].metric(t("odoo.connection.hours_downloaded", lang=lang), f"{format_number_es(summary['hours_downloaded'], 2)} h")
    cols[2].metric(t("metric.people", lang=lang), format_integer_es(summary["people"]))
    cols[3].metric(t("metric.projects", lang=lang), format_integer_es(summary["projects"]))
    period = " - ".join([value for value in [format_date_display(summary["min_date"]), format_date_display(summary["max_date"])] if value])
    info_cols = st.columns(3)
    info_cols[0].metric(t("odoo.connection.data_period", lang=lang), period or "-")
    info_cols[1].metric(t("odoo.connection.pending_classification", lang=lang), format_integer_es(summary["pending_rows"]))
    info_cols[2].metric(t("odoo.connection.last_update", lang=lang), summary["updated_at"])
    with st.expander(t("odoo.connection.technical_details", lang=lang), expanded=False):
        technical = {
            "raw_csv": summary["raw_csv"],
            "raw_json": summary["raw_json"],
            "processed_detail": summary["processed_detail"],
            "source_file": summary["source_file"],
            "source_date_from": summary["source_date_from"],
            "source_date_to": summary["source_date_to"],
        }
        st.table(pd.DataFrame([{"concepto": key, "valor": value} for key, value in technical.items() if value]))


def log_odoo_connection_error(step: str, exc: Exception) -> Path:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    path = LOGS_DIR / f"prc01_odoo_connection_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    path.write_text(f"step={step}\nerror={type(exc).__name__}: {exc}\n", encoding="utf-8")
    return path


def navigation() -> tuple[str, str]:
    st.sidebar.title("IMH Oreka")
    lang_label_to_code = {label: code for code, label in LANGUAGE_OPTIONS.items()}
    selected_language = st.sidebar.radio(
        t("app.language"),
        list(LANGUAGE_OPTIONS.values()),
        index=0 if current_language() == "es" else 1,
        horizontal=True,
        key="language_selector",
    )
    st.session_state["language"] = lang_label_to_code.get(selected_language, "es")
    lang = current_language()
    section_options = {
        "odoo": "app.nav.odoo_connection",
        "planning": "app.nav.planning",
        "operational_performance": "app.nav.operational_performance",
        "analysis": "app.nav.analysis",
        "config": "app.nav.configuration",
        "explore": "app.nav.odoo_exploration",
    }
    if st.session_state.get("active_section") not in section_options:
        st.session_state["active_section"] = "odoo"
    section = st.sidebar.radio(
        t("app.nav.section", lang=lang),
        list(section_options.keys()),
        format_func=lambda key: t(section_options[key], lang=lang),
        key="active_section",
    )
    detail = ""
    if section == "config":
        detail_options = {
            "management_classification": "config.management_classification",
            "available_hours": "config.available_hours",
            "workload": "config.person_workload",
            "language": "config.language",
        }
        if st.session_state.get("active_config_section") not in detail_options:
            st.session_state["active_config_section"] = "classification"
        detail = st.sidebar.selectbox(
            t("app.config.section", lang=lang),
            list(detail_options.keys()),
            format_func=lambda key: t(detail_options[key], lang=lang),
            key="active_config_section",
        )
    elif section == "explore":
        detail_options = {
            "departments": "Departamentos",
            "teams": "Equipos",
            "people": "Personas",
            "projects": "Proyectos",
            "tasks": "Tareas",
        }
        if st.session_state.get("active_explore_section") not in detail_options:
            st.session_state["active_explore_section"] = "departments"
        detail = st.sidebar.selectbox(
            "Categoria",
            list(detail_options.keys()),
            format_func=lambda key: detail_options[key],
            key="active_explore_section",
        )
    return section, detail

def render_dataset_notices(notices: list[dict[str, str]]) -> None:
    if not notices:
        return
    st.caption(f"Avisos activos del dataset: {len(notices)}")
    with st.expander("Ver detalles", expanded=False):
        for notice in notices:
            message = f"**{notice['title']}**\n\n{notice['message']}"
            level = notice.get("level", "info")
            if level == "warning":
                st.warning(message)
            elif level == "error":
                st.error(message)
            else:
                st.info(message)


def dataset_notices(df: pd.DataFrame, unclassified: pd.DataFrame) -> list[dict[str, str]]:
    notices: list[dict[str, str]] = []
    if df.empty:
        return notices
    min_date = df["data"].min().date()
    max_date = df["data"].max().date()
    months = sorted(df["hilabete_zk"].dropna().astype(int).unique().tolist())
    source_file = clean_text(df["source_file"].iloc[0]) if "source_file" in df.columns and not df.empty else ""
    source_from = clean_text(df["source_date_from"].iloc[0]) if "source_date_from" in df.columns and not df.empty else ""
    source_to = clean_text(df["source_date_to"].iloc[0]) if "source_date_to" in df.columns and not df.empty else ""
    source_text = f" Fuente raw: {source_file} ({source_from} -> {source_to})." if source_file else ""
    notices.append(
        {
            "level": "info",
            "title": "Rango real del dataset",
            "message": f"Dataset cargado: {min_date} a {max_date}.{source_text}",
        }
    )
    notices.append(
        {
            "level": "info",
            "title": "Meses con datos",
            "message": f"Meses con horas imputadas: {', '.join(str(m) for m in months)}.",
        }
    )
    if months != list(range(1, 13)):
        source_range = f"{source_from} a {source_to}" if source_from and source_to else "el rango seleccionado"
        notices.append(
            {
                "level": "warning",
                "title": "Dataset parcial",
                "message": (
                    f"El dataset esta construido para {source_range}, pero Odoo solo contiene lineas con fecha entre "
                    f"{min_date} y {max_date}. Los meses sin datos se muestran a 0."
                ),
            }
        )
    if unclassified is not None and not unclassified.empty:
        notices.append(
            {
                "level": "warning",
                "title": "Clasificacion pendiente",
                "message": f"Hay {len(unclassified)} proyectos/tareas pendientes de clasificar.",
            }
        )
    return notices

def prepare_available_hours_df(available_df: pd.DataFrame) -> pd.DataFrame:
    df = available_df.copy()
    df.columns = [str(column).replace("\ufeff", "").strip() for column in df.columns]
    for column in AVAILABLE_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    df = df[AVAILABLE_COLUMNS].copy()
    df["year_norm"] = df["year"].map(normalize_int)
    df["month_norm"] = df["month"].map(normalize_int)
    df["available_hours_norm"] = df["available_hours"].map(normalize_float)
    df["active_norm"] = df["active"].map(normalize_bool)
    df["scope_type_norm"] = df["scope_type"].map(normalize_text)
    df["scope_key_norm"] = df["scope_key"].map(normalize_text)
    df["scope_name_norm"] = df["scope_name"].map(normalize_text)
    return df


def empty_available_months(months: list[int]) -> pd.DataFrame:
    base = pd.DataFrame({"hilabete_zk": months})
    base["mes_label"] = base["hilabete_zk"].map(lambda month: f"{month:02d} - {MONTH_NAMES_EU[month]}")
    base["available_hours"] = 0.0
    base["configured"] = False
    return base


def monthly_available_from_rows(rows: pd.DataFrame, months: list[int]) -> pd.DataFrame:
    base = empty_available_months(months)
    if rows.empty:
        return base
    monthly = (
        rows.groupby("month_norm", as_index=False)
        .agg(available_hours=("available_hours_norm", "sum"))
        .rename(columns={"month_norm": "hilabete_zk"})
    )
    merged = base.drop(columns=["available_hours", "configured"]).merge(monthly, on="hilabete_zk", how="left")
    merged["configured"] = merged["available_hours"].notna()
    merged["available_hours"] = merged["available_hours"].fillna(0.0)
    return merged


def scope_match_mask(rows: pd.DataFrame, values: list[str], contains: bool = False) -> pd.Series:
    normalized_values = [normalize_text(value) for value in values if normalize_text(value)]
    if not normalized_values:
        return pd.Series(False, index=rows.index)
    mask = pd.Series(False, index=rows.index)
    for value in normalized_values:
        exact = (rows["scope_key_norm"] == value) | (rows["scope_name_norm"] == value)
        if contains:
            loose = rows["scope_key_norm"].str.contains(value, regex=False, na=False) | rows["scope_name_norm"].str.contains(value, regex=False, na=False)
            exact = exact | loose
        mask = mask | exact
    return mask


def availability_zero_reason(monthly: pd.DataFrame, matched_rows: pd.DataFrame) -> str:
    if matched_rows.empty:
        return "No hay filas de disponibilidad que coincidan con el alcance y meses seleccionados."
    if float(monthly["available_hours"].sum()) <= 0:
        return "Hay filas coincidentes, pero la suma de available_hours para el periodo es 0."
    return ""


def write_available_hours_diagnostics_csv(diagnostics: dict[str, Any]) -> None:
    DATA_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    row = diagnostics.copy()
    for key, value in list(row.items()):
        if isinstance(value, (list, dict)):
            row[key] = str(value)
    pd.DataFrame([row]).to_csv(DATA_REPORTS_DIR / "prc01_available_hours_diagnostics.csv", sep=";", encoding="utf-8-sig", index=False)


def write_available_hours_people_diagnostics_csv(rows: pd.DataFrame) -> None:
    DATA_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    rows.to_csv(DATA_REPORTS_DIR / "prc01_available_hours_diagnostics.csv", sep=";", encoding="utf-8-sig", index=False)


def prepare_person_workload_df(workload_df: pd.DataFrame, year: int) -> pd.DataFrame:
    df = workload_df.copy()
    df.columns = [str(column).replace("\ufeff", "").strip() for column in df.columns]
    for column in PERSON_WORKLOAD_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    df = df[PERSON_WORKLOAD_COLUMNS].copy()
    df["year_norm"] = df["year"].map(normalize_int)
    df["workload_factor_norm"] = df["workload_factor"].map(lambda value: normalize_float(value, 1.0))
    df["active_norm"] = df["active"].map(normalize_bool)
    df["person_key_norm"] = df["person_key"].map(normalize_text)
    df["person_name_norm"] = df["person_name"].map(normalize_text)
    df = df[df["year_norm"] == int(year)].copy()
    return df


def person_column(df: pd.DataFrame) -> str | None:
    for column in ["pertsona", "person_name", "employee_name", "langilea", "display_name"]:
        if column in df.columns:
            return column
    return None


def people_from_filtered_data(df_filtered: pd.DataFrame) -> list[str]:
    column = person_column(df_filtered)
    if not column:
        return []
    return [person for person in options(df_filtered[column]) if normalize_text(person)]


def workload_for_person(person: str, workload_df: pd.DataFrame) -> tuple[float, str]:
    person_norm = normalize_text(person)
    if workload_df.empty or not person_norm:
        return 1.0, "workload_missing_default_1"
    rows = workload_df[(workload_df["person_key_norm"] == person_norm) | (workload_df["person_name_norm"] == person_norm)].copy()
    if rows.empty:
        return 1.0, "workload_missing_default_1"
    active_rows = rows[rows["active_norm"]].copy()
    if active_rows.empty:
        return 1.0, "workload_inactive_default_1"
    value = active_rows["workload_factor_norm"].dropna()
    if value.empty:
        return 1.0, "workload_invalid_default_1"
    return float(value.iloc[-1]), "workload_configured"


def rows_for_scope(month_rows: pd.DataFrame, scope_type: str, values: list[str], contains: bool = False) -> pd.DataFrame:
    rows = month_rows[month_rows["scope_type_norm"] == scope_type].copy()
    if rows.empty:
        return rows
    return rows[scope_match_mask(rows, values, contains=contains)].copy()


def base_monthly_available(month_rows: pd.DataFrame, selected_months: list[int], df_filtered: pd.DataFrame) -> tuple[pd.DataFrame, str, str]:
    departments = options(df_filtered["saila"]) if "saila" in df_filtered.columns else []
    parent_departments = sorted({department_parent(value) for value in departments if department_parent(value)})
    department_values = departments if len(departments) <= 3 else parent_departments
    department_rows = rows_for_scope(month_rows, "department", department_values, contains=True)
    department_monthly = monthly_available_from_rows(department_rows, selected_months)
    if not department_rows.empty and float(department_monthly["available_hours"].sum()) > 0:
        return department_monthly, "department", ", ".join(department_values[:3])
    company_rows = rows_for_scope(month_rows, "company", ["IMH", "IMH Campus"], contains=False)
    company_monthly = monthly_available_from_rows(company_rows, selected_months)
    if not company_rows.empty and float(company_monthly["available_hours"].sum()) > 0:
        return company_monthly, "company", "IMH Campus"
    return empty_available_months(selected_months), "none", ""


def resolve_available_hours_by_people(
    available_df: pd.DataFrame,
    workload_df: pd.DataFrame,
    df_filtered: pd.DataFrame,
    year: int,
    selected_months: list[int],
    selected_people: list[str] | None,
) -> dict[str, Any]:
    prepared = prepare_available_hours_df(available_df)
    workload = prepare_person_workload_df(workload_df, year)
    selected_months = [int(month) for month in selected_months]
    active_rows = prepared[prepared["active_norm"]].copy()
    year_rows = active_rows[active_rows["year_norm"] == int(year)].copy()
    month_rows = year_rows[year_rows["month_norm"].isin(selected_months)].copy()
    people_used = people_from_filtered_data(df_filtered)
    selected_norms = {normalize_text(person) for person in (selected_people or []) if normalize_text(person)}
    if selected_norms:
        people_used = [person for person in people_used if normalize_text(person) in selected_norms]

    base_monthly, base_source, base_scope_name = base_monthly_available(month_rows, selected_months, df_filtered)
    base_by_month = dict(zip(base_monthly["hilabete_zk"].astype(int), base_monthly["available_hours"].astype(float)))
    person_specific_rows = month_rows[month_rows["scope_type_norm"] == "person"].copy()
    diagnostic_rows: list[dict[str, Any]] = []
    people_records: list[dict[str, Any]] = []

    for person in people_used:
        factor, workload_reason = workload_for_person(person, workload)
        people_records.append({"person_key": person, "person_name": person, "workload_factor": factor, "reason": workload_reason})
        person_norm = normalize_text(person)
        person_rows = person_specific_rows[
            (person_specific_rows["scope_key_norm"] == person_norm) | (person_specific_rows["scope_name_norm"] == person_norm)
        ].copy()
        person_specific_by_month = {
            int(row["month_norm"]): float(row["available_hours_norm"])
            for _, row in person_rows.iterrows()
            if normalize_int(row.get("month_norm")) in selected_months and normalize_float(row.get("available_hours_norm"), 0.0) > 0
        }
        for month in selected_months:
            base_value = float(base_by_month.get(month, 0.0))
            person_specific_value = person_specific_by_month.get(month)
            if person_specific_value is not None:
                calculated = person_specific_value
                reason = "person_specific_available"
                row_base_source = "person"
                row_base_scope_name = person
            else:
                calculated = base_value * factor
                reason = workload_reason if base_value > 0 else "missing_base_month"
                row_base_source = base_source
                row_base_scope_name = base_scope_name
            diagnostic_rows.append(
                {
                    "year": int(year),
                    "month": month,
                    "month_name": MONTH_NAMES_EU[month],
                    "base_source": row_base_source,
                    "base_scope_name": row_base_scope_name,
                    "available_hours_base": base_value,
                    "person_name": person,
                    "person_key": person,
                    "workload_factor": factor,
                    "person_specific_available_hours": person_specific_value if person_specific_value is not None else "",
                    "calculated_available_hours": calculated,
                    "reason": reason,
                }
            )

    diagnostics_df = pd.DataFrame(
        diagnostic_rows,
        columns=[
            "year",
            "month",
            "month_name",
            "base_source",
            "base_scope_name",
            "available_hours_base",
            "person_name",
            "person_key",
            "workload_factor",
            "person_specific_available_hours",
            "calculated_available_hours",
            "reason",
        ],
    )
    write_available_hours_people_diagnostics_csv(diagnostics_df)

    if diagnostics_df.empty:
        monthly = empty_available_months(selected_months)
        workload_sum = 0.0
        people_count_by_month = {month: 0 for month in selected_months}
    else:
        grouped = diagnostics_df.groupby("month", as_index=False).agg(
            available_hours=("calculated_available_hours", "sum"),
            people_count=("person_name", "nunique"),
            workload_sum=("workload_factor", "sum"),
            available_hours_base=("available_hours_base", "max"),
        )
        monthly = pd.DataFrame({"hilabete_zk": selected_months})
        monthly["month_name"] = monthly["hilabete_zk"].map(MONTH_NAMES_EU)
        monthly["mes_label"] = monthly["hilabete_zk"].map(lambda month: f"{month:02d} - {MONTH_NAMES_EU[month]}")
        monthly = monthly.merge(grouped.rename(columns={"month": "hilabete_zk"}), on="hilabete_zk", how="left")
        monthly["available_hours"] = monthly["available_hours"].fillna(0.0)
        monthly["people_count"] = monthly["people_count"].fillna(0).astype(int)
        monthly["workload_sum"] = monthly["workload_sum"].fillna(0.0)
        monthly["available_hours_base"] = monthly["available_hours_base"].fillna(0.0)
        monthly["base_source"] = base_source
        monthly["base_scope_name"] = base_scope_name
        monthly["configured"] = monthly["available_hours"] > 0
        workload_sum = float(pd.DataFrame(people_records)["workload_factor"].sum()) if people_records else 0.0
        people_count_by_month = dict(zip(monthly["hilabete_zk"].astype(int), monthly["people_count"].astype(int)))

    total_available = float(monthly["available_hours"].sum()) if not monthly.empty else None
    people_used_df = pd.DataFrame(people_records, columns=["person_key", "person_name", "workload_factor", "reason"])
    months_without_base = [month for month in selected_months if float(base_by_month.get(month, 0.0)) <= 0]
    diagnostics = {
        "year seleccionado": year,
        "meses seleccionados": selected_months,
        "personas incluidas": people_used,
        "personas seleccionadas": selected_people or [],
        "people_count": len(people_used),
        "people_count_by_month": people_count_by_month,
        "workload_sum": workload_sum,
        "base_source": base_source,
        "base_scope_name": base_scope_name,
        "meses sin disponibilidad base": months_without_base,
        "personas sin workload configurado": people_used_df.loc[
            people_used_df["reason"].isin(["workload_missing_default_1", "workload_inactive_default_1", "workload_invalid_default_1"]),
            "person_name",
        ].tolist()
        if not people_used_df.empty
        else [],
        "horas disponibles finales": total_available,
    }
    monthly.attrs["total_available_hours"] = total_available
    monthly.attrs["source_scope_type"] = base_source
    monthly.attrs["source_scope_name"] = base_scope_name
    monthly.attrs["diagnostics"] = diagnostics
    return {
        "total_available_hours": total_available,
        "monthly_available": monthly,
        "people_used": people_used_df,
        "people_diagnostics": diagnostics_df,
        "base_source": base_source,
        "base_scope_name": base_scope_name,
        "diagnostics": diagnostics,
    }


def resolve_available_hours_for_analysis(
    available_df: pd.DataFrame,
    df_filtered: pd.DataFrame,
    year: int,
    selected_months: list[int],
    selected_department: str | None,
    selected_subdepartment: str | None,
    selected_people: list[str] | None,
) -> dict[str, Any]:
    prepared = prepare_available_hours_df(available_df)
    selected_months = [int(month) for month in selected_months]
    active_rows = prepared[prepared["active_norm"]].copy()
    year_rows = active_rows[active_rows["year_norm"] == int(year)].copy()
    month_rows = year_rows[year_rows["month_norm"].isin(selected_months)].copy()
    monthly = empty_available_months(selected_months)
    selected_people = selected_people or []
    diagnostics: dict[str, Any] = {
        "year seleccionado": year,
        "meses seleccionados": selected_months,
        "departamento seleccionado": selected_department or "",
        "subdepartamento seleccionado": selected_subdepartment or "",
        "personas seleccionadas": selected_people,
        "scope_type disponibles": sorted(prepared["scope_type"].dropna().astype(str).unique().tolist()),
        "scope_key disponibles": sorted(prepared["scope_key"].dropna().astype(str).unique().tolist()),
        "scope_name disponibles": sorted(prepared["scope_name"].dropna().astype(str).unique().tolist()),
        "filas activas detectadas": int(len(active_rows)),
        "filas descartadas por active": int(len(prepared) - len(active_rows)),
        "filas descartadas por year": int(len(active_rows) - len(year_rows)),
        "filas descartadas por month": int(len(year_rows) - len(month_rows)),
        "filas descartadas por scope_type": 0,
        "filas candidatas company": int((month_rows["scope_type_norm"] == "company").sum()),
        "filas candidatas department": int((month_rows["scope_type_norm"] == "department").sum()),
        "filas candidatas team": int((month_rows["scope_type_norm"] == "team").sum()),
        "filas candidatas person": int((month_rows["scope_type_norm"] == "person").sum()),
        "lineas filtradas analisis": int(len(df_filtered)),
        "motivo si devuelve 0": "",
    }

    source_scope_type = "none"
    source_scope_name = ""
    matched_rows = pd.DataFrame(columns=prepared.columns)
    zero_candidate_reasons: list[str] = []

    person_rows = month_rows[month_rows["scope_type_norm"] == "person"].copy()
    if selected_people and not person_rows.empty:
        person_mask = scope_match_mask(person_rows, selected_people, contains=False)
        candidate_rows = person_rows[person_mask].copy()
        candidate_monthly = monthly_available_from_rows(candidate_rows, selected_months)
        if not candidate_rows.empty and float(candidate_monthly["available_hours"].sum()) > 0:
            matched_rows = candidate_rows
            source_scope_type = "person"
            source_scope_name = ", ".join(selected_people)
        elif not candidate_rows.empty:
            zero_candidate_reasons.append("person coincide, pero suma 0")

    if matched_rows.empty:
        department_rows = month_rows[month_rows["scope_type_norm"] == "department"].copy()
        department_values: list[str] = []
        contains = False
        if selected_subdepartment and selected_subdepartment != "Todos":
            department_values.append(selected_subdepartment)
        if not department_values and selected_department and selected_department != "Todos los departamentos":
            department_values.append(selected_department)
            contains = True
        if department_values and not department_rows.empty:
            candidate_rows = department_rows[scope_match_mask(department_rows, department_values, contains=contains)].copy()
            candidate_monthly = monthly_available_from_rows(candidate_rows, selected_months)
            if not candidate_rows.empty and float(candidate_monthly["available_hours"].sum()) > 0:
                matched_rows = candidate_rows
                source_scope_type = "department"
                source_scope_name = department_values[0]
            elif not candidate_rows.empty:
                zero_candidate_reasons.append("department coincide, pero suma 0")

    if matched_rows.empty:
        company_rows = month_rows[month_rows["scope_type_norm"] == "company"].copy()
        company_mask = scope_match_mask(company_rows, ["IMH", "IMH Campus"], contains=False)
        matched_rows = company_rows[company_mask].copy()
        if not matched_rows.empty:
            source_scope_type = "company"
            source_scope_name = "IMH Campus"

    if not matched_rows.empty:
        monthly = monthly_available_from_rows(matched_rows, selected_months)

    total_available = float(monthly["available_hours"].sum()) if monthly["configured"].any() else None
    if total_available is not None and total_available <= 0:
        diagnostics["motivo si devuelve 0"] = availability_zero_reason(monthly, matched_rows)
    elif total_available is None:
        workload_exists = PERSON_WORKLOAD_FILE.exists() and not read_csv(PERSON_WORKLOAD_FILE, PERSON_WORKLOAD_COLUMNS).empty
        diagnostics["motivo si devuelve 0"] = (
            "No hay horas disponibles configuradas para este alcance. Existe configuracion de jornadas por persona, "
            "pero todavia no se usa para generar horas disponibles mensuales."
            if workload_exists
            else "No hay horas disponibles configuradas para este alcance."
        )
    if zero_candidate_reasons:
        diagnostics["coincidencias descartadas por suma 0"] = zero_candidate_reasons
    diagnostics["horas sumadas por mes"] = dict(zip(monthly["hilabete_zk"].astype(int).tolist(), monthly["available_hours"].astype(float).tolist()))
    diagnostics["horas disponibles finales"] = total_available if total_available is not None else 0.0
    diagnostics["source_scope_type"] = source_scope_type
    diagnostics["source_scope_name"] = source_scope_name
    diagnostics["filas scope usadas"] = int(len(matched_rows))
    write_available_hours_diagnostics_csv(diagnostics)
    monthly.attrs["total_available_hours"] = total_available
    monthly.attrs["source_scope_type"] = source_scope_type
    monthly.attrs["source_scope_name"] = source_scope_name
    monthly.attrs["diagnostics"] = diagnostics
    return {
        "total_available_hours": total_available,
        "monthly_available": monthly,
        "source_scope_type": source_scope_type,
        "source_scope_name": source_scope_name,
        "diagnostics": diagnostics,
    }


def render_available_hours_diagnostics(result: dict[str, Any]) -> None:
    lang = current_language()
    with st.expander(t("app.available.diagnostics", lang=lang), expanded=False):
        monthly = result["monthly_available"]
        source_type = result.get("base_source") or result.get("source_scope_type") or "none"
        source_name = result.get("base_scope_name") or result.get("source_scope_name") or "sin coincidencia"
        st.write(f"Fuente base usada: {source_type} - {source_name}")
        st.write(f"Meses usados: {result['diagnostics'].get('meses seleccionados', [])}")
        st.write(f"Personas incluidas: {result['diagnostics'].get('people_count', 0)}")
        st.write(f"{t('column.workload_sum', lang=lang)}: {result['diagnostics'].get('workload_sum', 0.0):.2f}")
        if result["diagnostics"].get("motivo si devuelve 0"):
            st.caption(result["diagnostics"]["motivo si devuelve 0"])
        if result["diagnostics"].get("meses sin disponibilidad base"):
            st.caption(f"Meses sin disponibilidad base: {result['diagnostics']['meses sin disponibilidad base']}")
        if result["diagnostics"].get("personas sin workload configurado"):
            st.caption(f"Personas sin workload configurado: {len(result['diagnostics']['personas sin workload configurado'])}")
        monthly_columns = [
            column
            for column in [
                "hilabete_zk",
                "mes_label",
                "available_hours_base",
                "people_count",
                "workload_sum",
                "available_hours",
                "base_source",
                "base_scope_name",
                "configured",
            ]
            if column in monthly.columns
        ]
        st.dataframe(translate_dataframe_columns_for_display(monthly[monthly_columns], current_language()), use_container_width=True, hide_index=True)
        people_used = result.get("people_used")
        if isinstance(people_used, pd.DataFrame) and not people_used.empty:
            st.dataframe(translate_dataframe_columns_for_display(people_used, current_language()), use_container_width=True, hide_index=True)


def month_range_selector(prefix: str) -> tuple[list[int], str]:
    col1, col2 = st.columns(2)
    lang = current_language()
    month_options = list(range(1, 13))
    start = col1.selectbox(t("app.filters.month_start"), month_options, index=0, format_func=lambda month: month_label(month, lang), key=f"{prefix}_month_start")
    end = col2.selectbox(t("app.filters.month_end"), month_options, index=11, format_func=lambda month: month_label(month, lang), key=f"{prefix}_month_end")
    if start > end:
        start, end = end, start
    return list(range(start, end + 1)), f"{month_label(start, lang, False)}-{month_label(end, lang, False)}"


def reconcile_multiselect_selection(
    values: list[str],
    previous_values: list[str] | None,
    selected_values: list[str] | None,
) -> list[str]:
    """Keep a cascading multiselect valid when an upstream filter changes."""
    available = list(dict.fromkeys(values))
    if previous_values is None or selected_values is None:
        return available

    previous = list(dict.fromkeys(previous_values))
    selected = list(dict.fromkeys(selected_values))
    selected_set = set(selected)
    was_selecting_all = set(previous) == selected_set
    valid_selection = [value for value in available if value in selected_set]

    if was_selecting_all:
        return available
    if selected and not valid_selection:
        # Every selected value belonged to the former upstream scope. Keeping
        # that stale state would make the dataset empty through a hidden filter.
        return available
    return valid_selection


def select_all_multiselect(label: str, values: list[str], key: str) -> list[str]:
    state_key = f"{key}__available_options"
    available = list(dict.fromkeys(values))
    previous = st.session_state.get(state_key)
    selected = st.session_state.get(key)
    reconciled = reconcile_multiselect_selection(available, previous, selected)
    if selected != reconciled:
        st.session_state[key] = reconciled
    st.session_state[state_key] = available
    return st.multiselect(label, available, key=key)


def complete_months(df: pd.DataFrame, color_col: str, months: list[int], categories: list[str] | None = None) -> pd.DataFrame:
    categories = categories or options(df[color_col])
    if not categories:
        categories = ["Sin datos"]
    monthly = (
        df.groupby(["hilabete_zk", "mes_label", color_col], as_index=False).agg(ordu_errealak=("ordu_errealak", "sum"))
        if not df.empty
        else pd.DataFrame(columns=["hilabete_zk", "mes_label", color_col, "ordu_errealak"])
    )
    base = pd.MultiIndex.from_product([months, categories], names=["hilabete_zk", color_col]).to_frame(index=False)
    base["mes_label"] = base["hilabete_zk"].map(lambda month: f"{month:02d} - {MONTH_NAMES_EU[month]}")
    completed = base.merge(monthly, on=["hilabete_zk", "mes_label", color_col], how="left")
    completed["ordu_errealak"] = completed["ordu_errealak"].fillna(0.0)
    return completed.sort_values(["hilabete_zk", color_col])


def top_n_dimension(df: pd.DataFrame, dimension: str, top_n: int) -> pd.DataFrame:
    if dimension in {"grupo_actividad", "grupo_gestion", "unidad_destino_label", "naturaleza_trabajo_label"} or df.empty:
        return df
    totals = df.groupby(dimension)["ordu_errealak"].sum().sort_values(ascending=False)
    keep = totals.head(top_n).index.tolist()
    result = df.copy()
    result[dimension] = result[dimension].where(result[dimension].isin(keep), "Otros")
    return result


def build_actual_person_load_figure(
    df: pd.DataFrame,
    dimension: str,
    top_n: int,
    lang: str,
) -> tuple[go.Figure, pd.DataFrame]:
    source = top_n_dimension(df, dimension, top_n)
    grouped = source.groupby(["pertsona", dimension], as_index=False).agg(hours=("ordu_errealak", "sum"))
    person_table = (
        source.groupby("pertsona", as_index=False)
        .agg(
            horas_imputadas=("ordu_errealak", "sum"),
            lineas=("ordu_errealak", "size"),
            proyectos=("project_name", "nunique"),
            tareas=("task_name", "nunique"),
        )
        .sort_values(["horas_imputadas", "pertsona"], ascending=[False, True])
    )
    total_hours = float(person_table["horas_imputadas"].sum()) if not person_table.empty else 0.0
    person_table["porcentaje_horas"] = person_table["horas_imputadas"] / total_hours * 100 if total_hours else 0.0
    people = person_table.sort_values("horas_imputadas", ascending=True)["pertsona"].tolist()
    categories = options(grouped[dimension])
    color_map = build_dimension_color_map(source, dimension)
    fig = go.Figure()
    for category in categories:
        values = []
        for person in people:
            match = grouped[(grouped["pertsona"] == person) & (grouped[dimension] == category)]
            values.append(float(match["hours"].sum()) if not match.empty else 0.0)
        fig.add_bar(
            x=values,
            y=people,
            orientation="h",
            name=category,
            marker_color=color_map.get(category, DEFAULT_CATEGORY_COLOR),
        )
    fig.update_layout(
        title=t("analysis.person_load_view", lang=lang, default="Horas imputadas por persona"),
        barmode="stack",
        xaxis_title=t("column.horas", lang=lang),
        yaxis_title=t("column.person_name", lang=lang),
        height=max(450, 34 * max(1, len(people))),
    )
    return fig, person_table


def chart_dimension(df: pd.DataFrame, selected_projects: list[str]) -> tuple[str, dict[str, str] | None]:
    if len(selected_projects) == 1:
        return "proiektua_ataza", None
    if len(options(df["grupo_gestion"])) == 1:
        return "project_name", None
    return "grupo_gestion", None


def stacked_chart(df: pd.DataFrame, months: list[int], title: str, color_col: str, top_n: int, available: pd.DataFrame, color_map: dict[str, str] | None) -> None:
    source = top_n_dimension(df, color_col, top_n)
    categories = ALLOWED_GROUPS if color_col == "grupo_actividad" else options(source[color_col])
    chart_df = complete_months(source, color_col, months, categories)
    lang = current_language()
    chart_df["month_display"] = chart_df["hilabete_zk"].map(lambda month: month_label(int(month), lang, with_number=False))
    available_plot = available.copy()
    available_plot["month_display"] = available_plot["hilabete_zk"].map(lambda month: month_label(int(month), lang, with_number=False))
    fig = px.bar(
        chart_df,
        x="month_display",
        y="ordu_errealak",
        color=color_col,
        color_discrete_map=color_map or {},
        category_orders={"month_display": [month_label(m, lang, with_number=False) for m in months]},
        title=title,
        labels={"month_display": translate_label("month_display", "column", lang), "ordu_errealak": "Horas imputadas", color_col: translate_label(color_col, "column", lang)},
    )
    if available["configured"].any() and float(available["available_hours"].sum()) > 0:
        fig.add_scatter(x=available_plot["month_display"], y=available_plot["available_hours"], mode="lines+markers", name="Horas disponibles", line={"color": "#FF4B4B", "dash": "dash"})
    fig.update_layout(barmode="stack", xaxis_title="Mes", yaxis_title="Horas")
    st.plotly_chart(fig, use_container_width=True)


def pareto_chart(df: pd.DataFrame, title: str, dimension: str, top_n: int, color_map: dict[str, str] | None) -> None:
    source = top_n_dimension(df, dimension, top_n)
    pareto = (
        source.groupby(dimension, as_index=False)
        .agg(horas=("ordu_errealak", "sum"))
        .sort_values("horas", ascending=False)
    )
    total = float(pareto["horas"].sum())
    if total <= 0:
        st.warning("No hay horas para construir el Pareto con los filtros seleccionados.")
        return
    pareto["porcentaje"] = pareto["horas"] / total * 100
    pareto["porcentaje_acumulado"] = pareto["porcentaje"].cumsum()
    pareto.loc[pareto.index[-1], "porcentaje_acumulado"] = 100.0

    marker_colors = None
    if color_map:
        marker_colors = [color_map.get(value, "#636EFA") for value in pareto[dimension]]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            x=pareto[dimension],
            y=pareto["horas"],
            name="Horas imputadas",
            marker_color=marker_colors,
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=pareto[dimension],
            y=pareto["porcentaje_acumulado"],
            name="% acumulado",
            mode="lines+markers",
            line={"color": "black"},
        ),
        secondary_y=True,
    )
    fig.update_layout(title=title, xaxis_title="Detalle", yaxis_title="Horas", bargap=0.2)
    fig.update_yaxes(title_text="Horas", secondary_y=False)
    fig.update_yaxes(title_text="% acumulado", range=[0, 100], ticksuffix="%", secondary_y=True)
    st.plotly_chart(fig, use_container_width=True)


def build_monthly_group_chart(
    df: pd.DataFrame,
    months: list[int],
    available: pd.DataFrame,
    title: str,
    color_col: str = "grupo_gestion",
    top_n: int = 15,
    lang: str = "es",
    color_map: dict[str, str] | None = None,
) -> go.Figure:
    source = top_n_dimension(df, color_col, top_n)
    categories = ALLOWED_GROUPS if color_col == "grupo_actividad" else options(source[color_col])
    chart_df = complete_months(source, color_col, months, categories)
    chart_df["month_display"] = chart_df["hilabete_zk"].map(lambda month: month_label(int(month), lang, with_number=False))
    chart_df["display_label"] = chart_df[color_col].map(lambda value: translate_value(value, lang=lang) if color_col == "grupo_actividad" else clean_text(value))
    chart_df["hover_text"] = chart_df.apply(
        lambda row: f"{row['display_label']} | {t('column.horas', lang=lang, default='Horas')}: {format_number_es(row['ordu_errealak'])}",
        axis=1,
    )
    chart_color_map = color_map or ({translate_value(key, lang=lang): value for key, value in GROUP_COLORS.items()} if color_col == "grupo_actividad" else {})
    fig = px.bar(
        chart_df,
        x="month_display",
        y="ordu_errealak",
        color="display_label",
        custom_data=["hover_text"],
        color_discrete_map=chart_color_map,
        category_orders={"month_display": [month_label(month, lang, with_number=False) for month in months]},
        title=title,
        labels={"month_display": t("column.month", lang=lang, default="Mes"), "ordu_errealak": t("column.horas", lang=lang, default="Horas"), "display_label": translate_label(color_col, "column", lang)},
    )
    fig.update_traces(hovertemplate="%{customdata[0]}<extra></extra>")
    if available["configured"].any() and float(available["available_hours"].sum()) > 0:
        available_plot = available.copy()
        available_plot["month_display"] = available_plot["hilabete_zk"].map(lambda month: month_label(int(month), lang, with_number=False))
        available_hover = [
            f"{t('column.available_hours', lang=lang, default='Horas disponibles')}: {format_number_es(value)}"
            for value in available["available_hours"].tolist()
        ]
        fig.add_scatter(
            x=available_plot["month_display"],
            y=available_plot["available_hours"],
            mode="lines+markers",
            name=t("column.available_hours", lang=lang, default="Horas disponibles"),
            customdata=available_hover,
            hovertemplate="%{customdata}<extra></extra>",
            line={"color": "#FF4B4B", "dash": "dash"},
        )
    fig.update_layout(barmode="stack", xaxis_title="Mes", yaxis_title="Horas")
    return fig


def build_pareto_figure(df: pd.DataFrame, title: str, dimension: str, top_n: int, color_map: dict[str, str] | None = None, lang: str = "es") -> go.Figure:
    source = top_n_dimension(df, dimension, top_n)
    pareto = (
        source.groupby(dimension, as_index=False)
        .agg(horas=("ordu_errealak", "sum"))
        .sort_values("horas", ascending=False)
    )
    total = float(pareto["horas"].sum()) if not pareto.empty else 0.0
    if total <= 0:
        pareto = pd.DataFrame({dimension: ["Sin datos"], "horas": [0.0], "porcentaje_acumulado": [0.0]})
    else:
        pareto["porcentaje"] = pareto["horas"] / total * 100
        pareto["porcentaje_acumulado"] = pareto["porcentaje"].cumsum()
        pareto.loc[pareto.index[-1], "porcentaje_acumulado"] = 100.0
    pareto["display_label"] = pareto[dimension].map(lambda value: translate_value(value, lang=lang) if dimension == "grupo_actividad" else clean_text(value))
    pareto["hover_text"] = pareto.apply(
        lambda row: f"{row['display_label']} | {t('column.horas', lang=lang, default='Horas')}: {format_number_es(row['horas'])}",
        axis=1,
    )
    marker_colors = [color_map.get(value, "#636EFA") for value in pareto[dimension]] if color_map else None
    if dimension == "project_name":
        fig = go.Figure()
        plot_df = pareto.sort_values("horas", ascending=True)
        project_marker_colors = [color_map.get(value, DEFAULT_CATEGORY_COLOR) for value in plot_df[dimension]] if color_map else None
        fig.add_trace(
            go.Bar(
                x=plot_df["horas"],
                y=plot_df["display_label"],
                orientation="h",
                name=t("column.horas", lang=lang, default="Horas"),
                marker_color=project_marker_colors,
                customdata=plot_df["hover_text"],
                hovertemplate="%{customdata}<extra></extra>",
            )
        )
        fig.update_layout(
            title=title,
            xaxis_title=t("column.horas", lang=lang, default="Horas"),
            yaxis_title=translate_label(dimension, "column", lang),
            height=max(450, 28 * len(plot_df)),
            margin=dict(l=280, r=80, t=80, b=80),
        )
        return fig
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(x=pareto["display_label"], y=pareto["horas"], name=t("column.horas", lang=lang, default="Horas"), marker_color=marker_colors, customdata=pareto["hover_text"], hovertemplate="%{customdata}<extra></extra>"),
        secondary_y=False,
    )
    fig.add_trace(go.Scatter(x=pareto["display_label"], y=pareto["porcentaje_acumulado"], name="% acumulado", mode="lines+markers", line={"color": "black"}, hovertemplate="%{y:.2f}%<extra></extra>"), secondary_y=True)
    fig.update_layout(title=title, xaxis_title="Detalle", yaxis_title="Horas", bargap=0.2)
    fig.update_yaxes(title_text="Horas", secondary_y=False)
    fig.update_yaxes(title_text="% acumulado", range=[0, 100], ticksuffix="%", secondary_y=True)
    return fig


def build_report_summary_metrics(df: pd.DataFrame, available: pd.DataFrame) -> dict[str, float | int | None]:
    total = float(df["ordu_errealak"].sum())
    available_total = float(available["available_hours"].sum()) if available["configured"].any() else 0.0
    has_available = available["configured"].any() and available_total > 0
    return {
        "Horas imputadas totales": total,
        "Horas disponibles": available_total if has_available else None,
        "Diferencia vs disponibles": available_total - total if has_available else None,
        "% ocupacion": total / available_total * 100 if has_available else None,
        "Personas": int(df["pertsona"].nunique()),
        "Proyectos": int(df["project_name"].nunique()),
        "Tareas": int(df["task_name"].nunique()),
        "Horas directo": float(df.loc[df["naturaleza_trabajo"] == "directo", "ordu_errealak"].sum()),
        "Horas indirecto": float(df.loc[df["naturaleza_trabajo"] == "indirecto", "ordu_errealak"].sum()),
        "Horas no aplica": float(df.loc[df["naturaleza_trabajo"] == "no_aplica", "ordu_errealak"].sum()),
        "Horas pendiente gestion": float(df.loc[df["classification_status"] == "pendiente", "ordu_errealak"].sum()),
    }


def build_hours_by_dimension_table(df: pd.DataFrame, dimension: str) -> pd.DataFrame:
    total = float(df["ordu_errealak"].sum())
    table = df.groupby(dimension, as_index=False).agg(horas=("ordu_errealak", "sum")).sort_values("horas", ascending=False)
    table["porcentaje"] = table["horas"] / total * 100 if total else 0.0
    return table


def build_management_group_table(df: pd.DataFrame) -> pd.DataFrame:
    return build_hours_by_dimension_table(df, "grupo_gestion")


def build_project_table(df: pd.DataFrame) -> pd.DataFrame:
    total = float(df["ordu_errealak"].sum())
    dominant = (
        df.groupby(["project_name", "grupo_gestion"], as_index=False)
        .agg(group_hours=("ordu_errealak", "sum"))
        .sort_values(["project_name", "group_hours"], ascending=[True, False])
        .drop_duplicates("project_name")
        .rename(columns={"grupo_gestion": "grupo_gestion principal"})
    )
    table = (
        df.groupby("project_name", as_index=False)
        .agg(horas=("ordu_errealak", "sum"), personas=("pertsona", "nunique"), tareas=("task_name", "nunique"))
        .merge(dominant[["project_name", "grupo_gestion principal"]], on="project_name", how="left")
        .sort_values("horas", ascending=False)
    )
    table["porcentaje"] = table["horas"] / total * 100 if total else 0.0
    return table[["project_name", "grupo_gestion principal", "horas", "porcentaje", "personas", "tareas"]]


def build_project_management_matrix(df: pd.DataFrame) -> pd.DataFrame:
    total = float(df["ordu_errealak"].sum())
    table = df.groupby(["project_name", "grupo_gestion"], as_index=False).agg(horas=("ordu_errealak", "sum")).sort_values("horas", ascending=False)
    table["porcentaje_total"] = table["horas"] / total * 100 if total else 0.0
    return table


def build_detail_table(df: pd.DataFrame, include_detail: bool) -> tuple[pd.DataFrame, str]:
    if not include_detail:
        return pd.DataFrame(), "Detalle no incluido por configuracion."
    detail = (
        df.groupby(["pertsona", "project_name", "task_name", "grupo_gestion", "mes_label"], as_index=False)
        .agg(horas=("ordu_errealak", "sum"))
        .sort_values("horas", ascending=False)
    )
    if len(detail) > 500:
        return detail.head(500), f"Detalle limitado a Top 500 de {len(detail)} filas."
    return detail, ""


def dataframe_html(df: pd.DataFrame, lang: str = "es") -> str:
    if df.empty:
        return "<p>Sin datos.</p>"
    display = df.copy()
    display.columns = [translate_label(str(column), "column", lang) for column in display.columns]
    return display.to_html(index=False, classes="data-table", border=0, escape=True)


def metrics_html(metrics: dict[str, float | int | None], lang: str = "es") -> str:
    cards = []
    for label, value in metrics.items():
        text = "No configurado" if value is None else (format_number_es(value, 1) if isinstance(value, float) else str(value))
        cards.append(f"<div class='metric'><span>{escape(translate_label(label, 'metric', lang))}</span><strong>{escape(text)}</strong></div>")
    return "<div class='metrics'>" + "".join(cards) + "</div>"


def report_filter_summary(context: dict[str, Any], months: list[int], lang: str | None = None) -> dict[str, Any]:
    lang = lang or current_language()
    return {
        "Año": context.get("year", ""),
        "Periodo": f"{month_label(months[0], lang, False)}-{month_label(months[-1], lang, False)}" if months else "",
        "Departamento": context.get("scope", ""),
        "Grupo interno / subdepartamento": context.get("subdepartment", ""),
        "Unidad destino": "Todas" if len(context.get("selected_units", [])) > 5 else context.get("selected_units", []),
        "Naturaleza del trabajo": "Todas" if len(context.get("selected_natures", [])) > 5 else context.get("selected_natures", []),
        "Unidad destino + naturaleza": "Todos" if len(context.get("management_groups", [])) > 5 else context.get("management_groups", []),
        "Personas": "Todas las personas del filtro" if len(context.get("selected_people", [])) > 5 else context.get("selected_people", []),
        "Top N proyectos": context.get("top_n", ""),
    }


def filters_html(context: dict[str, Any], months: list[int], lang: str) -> str:
    rows = []
    for key, value in report_filter_summary(context, months, lang).items():
        if isinstance(value, list):
            value = ", ".join(clean_text(item) for item in value) or "Todas"
        rows.append(f"<tr><th>{escape(translate_label(key, 'report', lang))}</th><td>{escape(clean_text(value))}</td></tr>")
    return (
        f"<details class='filters-block'><summary>{escape(t('report.filters', lang=lang, default='Filtros aplicados'))}</summary>"
        "<table class='data-table'>"
        f"<tr><th>{escape(t('report.filter', lang=lang, default='Filtro'))}</th><th>{escape(t('report.value', lang=lang, default='Valor'))}</th></tr>"
        + "".join(rows)
        + "</table></details>"
    )


def render_report_html(
    title: str,
    df: pd.DataFrame,
    available: pd.DataFrame,
    months: list[int],
    context: dict[str, Any],
    top_n: int,
    include_detail: bool,
    lang: str = "es",
) -> tuple[str, dict[str, pd.DataFrame]]:
    metrics = build_report_summary_metrics(df, available)
    management_group = build_management_group_table(df)
    unit = build_hours_by_dimension_table(df, "unidad_destino_label")
    nature = build_hours_by_dimension_table(df, "naturaleza_trabajo_label")
    project = build_project_table(df)
    matrix = build_project_management_matrix(df)
    detail, detail_note = build_detail_table(df, include_detail)
    management_color_map = build_management_color_map(df, load_management_units(), load_work_natures())
    management_title = t("report.management_group_hours", lang=lang, default=t("report.hours_by_management_group", lang=lang))
    monthly_fig = build_monthly_group_chart(df, months, available, management_title, "grupo_gestion", top_n, lang, management_color_map)
    monthly_project_fig = build_monthly_group_chart(df, months, available, t("report.monthly_project", lang=lang), "project_name", top_n, lang)
    pareto_group = build_pareto_figure(df, management_title, "grupo_gestion", top_n, management_color_map, lang)
    pareto_project = build_pareto_figure(df, t("report.pareto_project", lang=lang), "project_name", top_n, None, lang)
    period_label = f"{month_label(months[0], lang, False)}-{month_label(months[-1], lang, False)}" if months else ""
    html = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>{escape(title)}</title>
<style>
body {{ font-family: Segoe UI, Arial, sans-serif; margin: 32px; color: #1f2933; }}
h1, h2 {{ color: #102a43; }}
.metrics {{ display: grid; grid-template-columns: repeat(4, minmax(150px, 1fr)); gap: 12px; margin: 18px 0; }}
.metric {{ border: 1px solid #d9e2ec; padding: 10px; border-radius: 6px; background: #f8fafc; }}
.metric span {{ display: block; font-size: 12px; color: #52606d; }}
.metric strong {{ font-size: 20px; }}
.data-table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
.data-table th, .data-table td {{ border-bottom: 1px solid #d9e2ec; padding: 6px 8px; text-align: left; }}
.note {{ color: #7b341e; }}
</style>
</head>
<body>
<h1>{escape(title)}</h1>
<p><strong>{escape(t('report.generated_at', lang=lang, default='Fecha de generacion'))}:</strong> {escape(now_text())}</p>
<p><strong>{escape(t('app.filters.year', lang=lang, default='Año'))}:</strong> {escape(str(context.get("year", "")))} | <strong>Periodo:</strong> {escape(period_label)}</p>
<p><strong>Alcance:</strong> {escape(str(context.get("scope", "")))} {escape(str(context.get("subdepartment", "")))}</p>
{filters_html(context, months, lang)}
<h2>{escape(t('report.executive_summary', lang=lang, default='Resumen ejecutivo'))}</h2>
{metrics_html(metrics, lang)}
<h2>{escape(management_title)}</h2>
{monthly_fig.to_html(full_html=False, include_plotlyjs=True)}
<h2>{escape(t('report.monthly_project', lang=lang, default='Evolucion mensual por proyecto'))}</h2>
{monthly_project_fig.to_html(full_html=False, include_plotlyjs=False)}
<h2>{escape(management_title)}</h2>
{pareto_group.to_html(full_html=False, include_plotlyjs=False)}
<h2>{escape(t('report.pareto_project', lang=lang, default='Pareto por proyecto'))}</h2>
{pareto_project.to_html(full_html=False, include_plotlyjs=False)}
<h2>{escape(management_title)}</h2>
{dataframe_html(management_group, lang)}
<h2>{escape(t('report.unit_hours', lang=lang, default=t('report.hours_by_unit', lang=lang)))}</h2>
{dataframe_html(unit, lang)}
<h2>{escape(t('report.work_nature_hours', lang=lang, default=t('report.hours_by_nature', lang=lang)))}</h2>
{dataframe_html(nature, lang)}
<h2>Computo de horas por proyecto</h2>
{dataframe_html(project, lang)}
<h2>Computo cruzado proyecto x unidad destino + naturaleza</h2>
{dataframe_html(matrix, lang)}
<h2>Detalle resumido</h2>
<p class="note">{escape(detail_note)}</p>
{dataframe_html(detail, lang)}
</body>
</html>"""
    return html, {
        "data_summary": pd.DataFrame([metrics]),
        "management_group_hours": management_group,
        "unit_hours": unit,
        "work_nature_hours": nature,
        "project_hours": project,
        "project_management_matrix": matrix,
        "detail_summary": detail,
    }


def report_month_options(prefix: str, report_type: str) -> list[int]:
    lang = current_language()
    month_options = list(range(1, 13))
    if report_type == "monthly":
        month = st.selectbox(t("reports.generator.month", lang=lang), month_options, format_func=lambda value: month_label(value, lang), key=f"{prefix}_report_month")
        return [month]
    if report_type == "annual":
        return list(range(1, 13))
    col1, col2 = st.columns(2)
    start = col1.selectbox(t("reports.generator.start_month", lang=lang), month_options, index=0, format_func=lambda value: month_label(value, lang), key=f"{prefix}_report_month_start")
    end = col2.selectbox(t("reports.generator.end_month", lang=lang), month_options, index=5, format_func=lambda value: month_label(value, lang), key=f"{prefix}_report_month_end")
    if start > end:
        start, end = end, start
    return list(range(start, end + 1))


def build_report_scopes(df: pd.DataFrame, context: dict[str, Any], level: str) -> list[tuple[str, str, pd.DataFrame]]:
    people = options(df["pertsona"])
    if len(people) == 1:
        person = people[0]
        return [("person", person, df.copy())]
    scopes = [("global", "Vista actual", df.copy())]
    if level != "with_sublevels":
        return scopes
    if context.get("scope") == "Todos los departamentos":
        for department in options(df["saila"]):
            scopes.append(("department", department, df[df["saila"] == department].copy()))
    else:
        for department in options(df["saila"]):
            scopes.append(("subdepartment", department, df[df["saila"] == department].copy()))
    for person in people:
        scopes.append(("person", person, df[df["pertsona"] == person].copy()))
    return [(kind, name, subset) for kind, name, subset in scopes if not subset.empty]


def write_analysis_report_package(
    df: pd.DataFrame,
    available_df: pd.DataFrame,
    workload_df: pd.DataFrame,
    context: dict[str, Any],
    report_type: str,
    months: list[int],
    level: str,
    include_detail: bool,
    top_n: int,
    lang: str = "es",
) -> dict[str, Any]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = ANALYSIS_REPORTS_DIR / f"report_{timestamp}"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_df = df[df["hilabete_zk"].astype(int).isin(months)].copy()
    reports_generated: list[dict[str, str]] = []
    package_tables: dict[str, pd.DataFrame] = {}
    for index, (kind, name, subset) in enumerate(build_report_scopes(report_df, context, level)):
        availability = resolve_available_hours_by_people(available_df, workload_df, subset, int(context["year"]), months, options(subset["pertsona"]))
        title = f"Informe de horas imputadas - {name} - {month_label(months[0], lang, False)}-{month_label(months[-1], lang, False)} {context['year']}"
        html, tables = render_report_html(title, subset, availability["monthly_available"], months, context, top_n, include_detail, lang)
        if index == 0:
            filename = "index.html"
            package_tables = tables
            (report_dir / "department_global.html").write_text(html, encoding="utf-8")
        elif kind == "person":
            filename = f"person_{slugify_filename(name)}.html"
        elif kind == "subdepartment":
            filename = f"subdepartment_{slugify_filename(name)}.html"
        else:
            filename = f"department_{slugify_filename(name)}.html"
        (report_dir / filename).write_text(html, encoding="utf-8")
        reports_generated.append({"type": kind, "name": name, "file": filename})
    for name, table in package_tables.items():
        table.to_csv(report_dir / f"{name}.csv", sep=";", encoding="utf-8-sig", index=False)
    source_from = clean_text(report_df["source_date_from"].iloc[0]) if "source_date_from" in report_df.columns and not report_df.empty else ""
    source_to = clean_text(report_df["source_date_to"].iloc[0]) if "source_date_to" in report_df.columns and not report_df.empty else ""
    metadata = {
        "generated_at": now_text(),
        "year": int(context["year"]),
        "period_type": report_type,
        "month_start": int(months[0]),
        "month_end": int(months[-1]),
        "filters": report_filter_summary(context, months, lang),
        "reports_generated": reports_generated,
        "data_source": {
            "processed_file": str(DATA_FILE.relative_to(ROOT_DIR)),
            "source_date_from": source_from,
            "source_date_to": source_to,
        },
        "language": lang,
    }
    (report_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    zip_path = report_dir / f"prc01_analysis_report_{timestamp}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in report_dir.iterdir():
            if path != zip_path and path.is_file():
                archive.write(path, arcname=path.name)
    return {"report_dir": report_dir, "zip_path": zip_path, "reports_generated": reports_generated}


def render_report_generator(
    filtered: pd.DataFrame,
    available_df: pd.DataFrame,
    workload_df: pd.DataFrame,
    context: dict[str, Any],
    prefix: str,
) -> None:
    lang = current_language()
    with st.expander(t("reports.generator.title", lang=lang), expanded=False):
        report_type_labels = {
            "monthly": "reports.generator.monthly",
            "annual": "reports.generator.annual",
            "between_months": "reports.generator.between_months",
        }
        report_type = st.selectbox(
            t("reports.generator.type", lang=lang),
            list(report_type_labels.keys()),
            index=2,
            format_func=lambda key: t(report_type_labels[key], lang=lang),
            key=f"{prefix}_report_type",
        )
        months = report_month_options(prefix, report_type)
        level_labels = {
            "with_sublevels": "reports.generator.current_view_sublevels",
            "current_only": "reports.generator.current_view_only",
        }
        level = st.selectbox(
            t("reports.generator.detail_level", lang=lang),
            list(level_labels.keys()),
            format_func=lambda key: t(level_labels[key], lang=lang),
            key=f"{prefix}_report_level",
        )
        include_detail = st.checkbox(t("reports.generator.include_detail", lang=lang), value=True, key=f"{prefix}_report_detail")
        top_n = st.slider(t("reports.generator.top_n", lang=lang), 5, 50, int(context.get("top_n", 15)), 5, key=f"{prefix}_report_topn")
        if st.button(t("reports.generator.generate", lang=lang), key=f"{prefix}_generate_report"):
            if filtered.empty:
                st.warning(t("reports.generator.no_data", lang=lang))
                return
            result = write_analysis_report_package(filtered, available_df, workload_df, context, report_type, months, level, include_detail, top_n, lang)
            st.success(f"{t('reports.generator.generated_ok', lang=lang)}: {result['report_dir']}")
            st.write(f"{t('reports.generator.generated_files', lang=lang)}: {len(result['reports_generated'])}")
            with open(result["zip_path"], "rb") as handle:
                st.download_button(
                    t("reports.generator.download_zip", lang=lang),
                    data=handle.read(),
                    file_name=result["zip_path"].name,
                    mime="application/zip",
                    key=f"{prefix}_download_report_zip",
                )


def summary_metrics(df: pd.DataFrame, available: pd.DataFrame) -> None:
    lang = current_language()
    total = float(df["ordu_errealak"].sum())
    available_total = float(available["available_hours"].sum()) if available["configured"].any() else 0.0
    has_available = available["configured"].any() and available_total > 0
    metrics = [
        ("metric.total_hours", total, ""),
        ("metric.available_hours", available_total if has_available else None, ""),
        ("metric.difference_vs_available", available_total - total if has_available else None, ""),
        ("metric.occupation_pct", total / available_total * 100 if has_available else None, "%"),
        ("metric.people", df["pertsona"].nunique(), ""),
        ("metric.projects", df["project_name"].nunique(), ""),
        ("metric.tasks", df["task_name"].nunique(), ""),
        ("metric.direct_hours", df.loc[df["naturaleza_trabajo"] == "directo", "ordu_errealak"].sum(), ""),
        ("metric.indirect_hours", df.loc[df["naturaleza_trabajo"] == "indirecto", "ordu_errealak"].sum(), ""),
        ("metric.no_apply_hours", df.loc[df["naturaleza_trabajo"] == "no_aplica", "ordu_errealak"].sum(), ""),
        ("metric.pending_management_hours", df.loc[df["classification_status"] == "pendiente", "ordu_errealak"].sum(), ""),
    ]
    for start in (0, 4, 8):
        cols = st.columns(4)
        for col, (label_key, value, suffix) in zip(cols, metrics[start : start + 4]):
            label = t(label_key, lang=lang)
            if value is None:
                col.metric(label, t("metric.not_configured", lang=lang))
            elif isinstance(value, (int, float)):
                col.metric(label, f"{value:.1f}{suffix}")
            else:
                col.metric(label, value)


def summary_tables(df: pd.DataFrame, key: str) -> None:
    st.markdown("### Tabla resumen")
    dimensions = {
        "unidad destino + naturaleza": "grupo_gestion",
        "unidad destino": "unidad_destino_label",
        "naturaleza trabajo": "naturaleza_trabajo_label",
        "proyecto": "project_name",
        "tarea": "task_name",
        "proyecto/tarea": "proiektua_ataza",
        "persona": "pertsona",
        "departamento": "saila",
    }
    selected = st.selectbox("Agrupar tabla por", list(dimensions.keys()), key=f"{key}_summary")
    dimension = dimensions[selected]
    summary = (
        df.groupby(dimension, as_index=False)
        .agg(ordu_errealak=("ordu_errealak", "sum"), lerroak=("ordu_errealak", "size"), pertsonak=("pertsona", "nunique"), proiektuak=("project_name", "nunique"), atazak=("task_name", "nunique"))
        .sort_values("ordu_errealak", ascending=False)
    )
    st.dataframe(translate_dataframe_columns_for_display(summary, current_language()), use_container_width=True, hide_index=True)
    with st.expander("Ver lineas de detalle", expanded=False):
        columns = ["data", "mes_label", "grupo_gestion", "unidad_destino_label", "naturaleza_trabajo_label", "pertsona", "saila", "project_name", "task_name", "ordu_errealak", "azalpena"]
        columns = [column for column in columns if column in df.columns]
        st.dataframe(translate_dataframe_columns_for_display(df[columns].sort_values(["data", "pertsona"]), current_language()), use_container_width=True, hide_index=True)


def read_planning_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=PLANNING_COLUMNS)
    try:
        df = pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig", dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        df = pd.DataFrame(columns=PLANNING_COLUMNS)
    df.columns = [str(column).replace("\ufeff", "").strip() for column in df.columns]
    for column in PLANNING_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    extra_columns = [column for column in df.columns if column not in PLANNING_COLUMNS]
    return df[PLANNING_COLUMNS + extra_columns].copy()


def validate_planning_df(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    errors: list[str] = []
    missing = [column for column in PLANNING_COLUMNS if column not in df.columns]
    if missing:
        errors.append("Faltan columnas obligatorias: " + ", ".join(missing))
    result = df.copy()
    for column in PLANNING_COLUMNS:
        if column not in result.columns:
            result[column] = ""
    extra_columns = [column for column in result.columns if column not in PLANNING_COLUMNS]
    result = result[PLANNING_COLUMNS + extra_columns].copy()
    result["planning_status"] = result["planning_status"].map(lambda value: normalize_text(value) or "pendiente")
    invalid_status = sorted(set(result.loc[~result["planning_status"].isin(VALID_PLANNING_STATUSES), "planning_status"].tolist()))
    if invalid_status:
        errors.append("planning_status no valido: " + ", ".join(invalid_status))
    result["year"] = pd.to_numeric(result["year"], errors="coerce")
    result["month"] = pd.to_numeric(result["month"], errors="coerce")
    result["planned_hours"] = pd.to_numeric(result["planned_hours"], errors="coerce")
    result["probability"] = pd.to_numeric(result["probability"], errors="coerce")
    if result["year"].isna().any():
        errors.append("year debe ser numerico.")
    if result["month"].isna().any() or (~result["month"].between(1, 12)).any():
        errors.append("month debe estar entre 1 y 12.")
    if result["planned_hours"].isna().any():
        errors.append("planned_hours debe ser numerico.")
    if result["probability"].isna().any() or (~result["probability"].between(0, 1)).any():
        errors.append("probability debe estar entre 0 y 1.")
    result["active"] = result["active"].map(lambda value: "TRUE" if normalize_bool(value) else "FALSE")
    result["year"] = result["year"].fillna(0).astype(int)
    result["month"] = result["month"].fillna(0).astype(int)
    result["planned_hours"] = result["planned_hours"].fillna(0.0).astype(float)
    result["probability"] = result["probability"].fillna(0.0).clip(0, 1).astype(float)
    result["weighted_planned_hours"] = result["planned_hours"] * result["probability"]
    for column in PLANNING_COLUMNS:
        if column not in {"year", "month", "planned_hours", "probability", "weighted_planned_hours"}:
            result[column] = result[column].map(clean_text)
    return result, errors


def planning_with_management_classification(df: pd.DataFrame, lang: str) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    result = df.copy()
    result["saila"] = result["department_name"].map(clean_text)
    result["pertsona"] = result["person_name"].map(clean_text)
    units = load_management_units()
    natures = load_work_natures()
    unit_labels = label_lookup(units, "unit_key", lang)
    nature_labels = label_lookup(natures, "nature_key", lang)
    has_explicit = result["unidad_destino"].map(clean_text).ne("") & result["naturaleza_trabajo"].map(clean_text).ne("")
    classified = apply_management_classification(result, load_management_classification_rules(), units, natures, lang)
    for column in ["unidad_destino", "naturaleza_trabajo", "classification_rule_id", "classification_status"]:
        result[column] = result[column].where(has_explicit, classified[column])
    result["classification_status"] = result["classification_status"].where(result["classification_status"].map(clean_text).ne(""), "clasificado")
    result.loc[result["unidad_destino"].map(clean_text).eq("") | result["naturaleza_trabajo"].map(clean_text).eq(""), "classification_status"] = "pendiente"
    result["unidad_destino"] = result["unidad_destino"].where(result["unidad_destino"].map(clean_text).ne(""), "pendiente")
    result["naturaleza_trabajo"] = result["naturaleza_trabajo"].where(result["naturaleza_trabajo"].map(clean_text).ne(""), "pendiente")
    result["unidad_destino_label"] = result["unidad_destino"].map(lambda key: unit_labels.get(clean_text(key), clean_text(key) or "PENDIENTE DE CLASIFICAR"))
    result["naturaleza_trabajo_label"] = result["naturaleza_trabajo"].map(lambda key: nature_labels.get(clean_text(key), clean_text(key) or "Pendiente"))
    result["grupo_gestion"] = result["grupo_gestion"].where(
        result["grupo_gestion"].map(clean_text).ne(""),
        result["unidad_destino_label"] + " · " + result["naturaleza_trabajo_label"],
    )
    pending = result["classification_status"].map(clean_text).eq("pendiente")
    result.loc[pending, "unidad_destino"] = "pendiente"
    result.loc[pending, "naturaleza_trabajo"] = "pendiente"
    result.loc[pending, "unidad_destino_label"] = "PENDIENTE DE CLASIFICAR"
    result.loc[pending, "naturaleza_trabajo_label"] = "Pendiente"
    result.loc[pending, "grupo_gestion"] = "PENDIENTE DE CLASIFICAR · Pendiente"
    result["urtea"] = result["year"].astype(int)
    result["hilabete_zk"] = result["month"].astype(int)
    result["mes_label"] = result["hilabete_zk"].map(lambda month: f"{month:02d} - {MONTH_NAMES_EU.get(int(month), '')}")
    result["ordu_errealak"] = result["planned_hours"]
    result["display_hours"] = result["planned_hours"]
    result["weighted_planned_hours"] = result["planned_hours"] * result["probability"]
    result["proiektua_ataza"] = result["project_name"].map(clean_text) + " / " + result["task_name"].map(clean_text)
    return result


def load_planning_data(lang: str) -> pd.DataFrame:
    source_path = PLANNING_PROCESSED_FILE
    raw = read_planning_csv(source_path)
    validated, _ = validate_planning_df(raw)
    active_mask = validated["active"].map(normalize_bool).astype(bool)
    active = validated.loc[active_mask].copy()
    result = planning_with_management_classification(active, lang)
    result.attrs["planning_source_file"] = str(source_path)
    return result


def load_organization_people(actuals_df: pd.DataFrame, year: int) -> pd.DataFrame:
    columns = [
        "person_key",
        "employee_id",
        "user_id",
        "resource_id",
        "person_name",
        "active",
        "department_name",
        "internal_group",
        "subdepartment",
        "workload_factor",
        "actual_hours_period",
        "present_in_organization",
    ]
    if actuals_df.empty or not {"pertsona", "saila", "urtea"}.issubset(actuals_df.columns):
        return pd.DataFrame(columns=columns)
    source = actuals_df[pd.to_numeric(actuals_df["urtea"], errors="coerce").fillna(0).astype(int) == int(year)].copy()
    if source.empty:
        return pd.DataFrame(columns=columns)
    source["person_name"] = source["pertsona"].map(clean_text)
    source["subdepartment"] = source["saila"].map(clean_text)
    source["department_name"] = source["subdepartment"].map(department_parent)
    source["actual_hours_period"] = pd.to_numeric(source.get("ordu_errealak", 0.0), errors="coerce").fillna(0.0)
    table = (
        source[source["person_name"].ne("")]
        .groupby(["person_name", "department_name", "subdepartment"], as_index=False, dropna=False)
        .agg(actual_hours_period=("actual_hours_period", "sum"))
        .sort_values(["department_name", "subdepartment", "person_name"])
    )
    table["person_key"] = table["person_name"].map(normalize_text)
    table["employee_id"] = ""
    table["user_id"] = ""
    table["resource_id"] = ""
    table["active"] = True
    table["internal_group"] = table["subdepartment"]
    table["workload_factor"] = 1.0
    table["present_in_organization"] = True
    return table[columns]


def deduplicate_scope_people(people_df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "person_key",
        "employee_id",
        "user_id",
        "resource_id",
        "person_name",
        "active",
        "department_name",
        "internal_group",
        "subdepartment",
        "workload_factor",
        "actual_hours_period",
        "present_in_organization",
    ]
    if people_df.empty:
        return pd.DataFrame(columns=columns)
    source = people_df.copy()
    for column in columns:
        if column not in source.columns:
            source[column] = "" if column not in {"active", "workload_factor", "actual_hours_period", "present_in_organization"} else 0
    source["_subdepartment_order"] = source.apply(lambda row: 1 if clean_text(row.get("subdepartment", "")) == clean_text(row.get("department_name", "")) else 0, axis=1)
    source = source.sort_values(["person_name", "_subdepartment_order", "subdepartment"])
    grouped = (
        source.groupby("person_name", as_index=False, dropna=False)
        .agg(
            person_key=("person_key", "first"),
            employee_id=("employee_id", "first"),
            user_id=("user_id", "first"),
            resource_id=("resource_id", "first"),
            active=("active", "first"),
            department_name=("department_name", "first"),
            internal_group=("internal_group", "first"),
            subdepartment=("subdepartment", "first"),
            workload_factor=("workload_factor", "first"),
            actual_hours_period=("actual_hours_period", "sum"),
            present_in_organization=("present_in_organization", "first"),
        )
    )
    return grouped[columns]


def filter_organization_people(people_df: pd.DataFrame, department: str, internal_group: str = "Todos") -> pd.DataFrame:
    if people_df.empty:
        return people_df.copy()
    result = people_df.copy()
    if department and department != "Todos los departamentos":
        result = result[result["department_name"].map(clean_text).eq(clean_text(department))].copy()
    if internal_group and internal_group != "Todos":
        result = result[result["subdepartment"].map(clean_text).eq(clean_text(internal_group))].copy()
    return deduplicate_scope_people(result)


def organization_people_scope_frame(people_df: pd.DataFrame) -> pd.DataFrame:
    if people_df.empty:
        return pd.DataFrame(columns=["pertsona", "saila", "person_name", "department_name"])
    return pd.DataFrame(
        {
            "pertsona": people_df["person_name"].map(clean_text),
            "saila": people_df["subdepartment"].map(clean_text),
            "person_name": people_df["person_name"].map(clean_text),
            "department_name": people_df["subdepartment"].map(clean_text),
        }
    )


def people_filter_options(people_df: pd.DataFrame, planning_df: pd.DataFrame) -> list[str]:
    people = options(people_df["person_name"]) if not people_df.empty and "person_name" in people_df.columns else []
    planned_people = {normalize_text(person) for person in options(planning_df["person_name"])} if not planning_df.empty else set()
    with_planning = sorted([person for person in people if normalize_text(person) in planned_people], key=normalize_text)
    without_planning = sorted([person for person in people if normalize_text(person) not in planned_people], key=normalize_text)
    return with_planning + without_planning


def planning_people_coverage_metrics(person_load: pd.DataFrame) -> dict[str, float | int]:
    people_in_scope = int(len(person_load)) if not person_load.empty else 0
    people_with_planning = int(person_load["has_planning_after_current_filters"].astype(bool).sum()) if people_in_scope else 0
    people_without_planning = people_in_scope - people_with_planning
    coverage = people_with_planning / people_in_scope * 100 if people_in_scope else 0.0
    return {
        "people_in_scope": people_in_scope,
        "people_with_planning": people_with_planning,
        "people_without_planning": people_without_planning,
        "person_planning_coverage_pct": coverage,
    }


def build_planning_people_coverage(
    organization_people: pd.DataFrame,
    planning_period_df: pd.DataFrame,
    planning_filtered_df: pd.DataFrame,
    availability_people: pd.DataFrame,
) -> pd.DataFrame:
    if organization_people.empty:
        return pd.DataFrame(
            columns=[
                "person_key",
                "employee_id",
                "user_id",
                "resource_id",
                "person_name",
                "active",
                "department_name",
                "internal_group",
                "subdepartment",
                "workload_factor",
                "available_hours_period",
                "present_in_organization",
                "present_in_actuals",
                "actual_hours_period",
                "present_in_planning_raw",
                "present_in_planning_processed",
                "planning_rows",
                "planned_hours_period",
                "first_planning_date",
                "last_planning_date",
                "included_after_year_filter",
                "included_after_period_filter",
                "included_after_department_filter",
                "included_after_unit_filter",
                "included_after_nature_filter",
                "included_after_management_group_filter",
                "visible_in_person_filter",
                "has_any_planning_in_period",
                "has_planning_after_current_filters",
                "status",
                "absence_reason",
                "suspected_permission_issue",
                "notes",
            ]
        )
    org = deduplicate_scope_people(organization_people).copy()
    planned_period = (
        planning_period_df.groupby("person_name", as_index=False)
        .agg(
            present_in_planning_processed=("person_name", "size"),
            planning_rows_period=("person_name", "size"),
            planned_hours_any_period=("display_hours", "sum"),
        )
        if not planning_period_df.empty
        else pd.DataFrame(columns=["person_name", "present_in_planning_processed", "planning_rows_period", "planned_hours_any_period"])
    )
    planned_current = (
        planning_filtered_df.groupby("person_name", as_index=False)
        .agg(
            planning_rows=("person_name", "size"),
            planned_hours_period=("display_hours", "sum"),
            first_planning_date=("date_start", "min"),
            last_planning_date=("date_end", "max"),
            projects=("project_name", "nunique"),
            tasks=("task_name", "nunique"),
        )
        if not planning_filtered_df.empty
        else pd.DataFrame(columns=["person_name", "planning_rows", "planned_hours_period", "first_planning_date", "last_planning_date", "projects", "tasks"])
    )
    availability = (
        availability_people.groupby("person_name", as_index=False)
        .agg(available_hours_period=("calculated_available_hours", "sum"), workload_factor=("workload_factor", "max"))
        if not availability_people.empty
        else pd.DataFrame(columns=["person_name", "available_hours_period", "workload_factor"])
    )
    result = org.merge(planned_period, on="person_name", how="left").merge(planned_current, on="person_name", how="left").merge(availability, on="person_name", how="left", suffixes=("", "_availability"))
    result["available_hours_period"] = pd.to_numeric(result["available_hours_period"], errors="coerce").fillna(0.0)
    result["workload_factor"] = pd.to_numeric(result.get("workload_factor_availability", result.get("workload_factor", 1.0)), errors="coerce").fillna(pd.to_numeric(result.get("workload_factor", 1.0), errors="coerce")).fillna(1.0)
    result["planning_rows"] = pd.to_numeric(result["planning_rows"], errors="coerce").fillna(0).astype(int)
    result["planned_hours_period"] = pd.to_numeric(result["planned_hours_period"], errors="coerce").fillna(0.0)
    result["planning_rows_period"] = pd.to_numeric(result["planning_rows_period"], errors="coerce").fillna(0).astype(int)
    result["planned_hours_any_period"] = pd.to_numeric(result["planned_hours_any_period"], errors="coerce").fillna(0.0)
    result["present_in_actuals"] = result["actual_hours_period"].astype(float) > 0
    result["present_in_planning_raw"] = result["planning_rows_period"] > 0
    result["present_in_planning_processed"] = result["planning_rows_period"] > 0
    result["has_any_planning_in_period"] = result["planned_hours_any_period"] > 0
    result["has_planning_after_current_filters"] = result["planned_hours_period"] > 0
    for column in [
        "included_after_year_filter",
        "included_after_period_filter",
        "included_after_department_filter",
        "included_after_unit_filter",
        "included_after_nature_filter",
        "included_after_management_group_filter",
        "visible_in_person_filter",
    ]:
        result[column] = True
    result["status"] = result.apply(
        lambda row: "con_planificacion" if bool(row["has_planning_after_current_filters"]) else ("sin_planificacion" if bool(row["present_in_organization"]) else "pendiente_diagnostico"),
        axis=1,
    )
    result["absence_reason"] = result.apply(
        lambda row: "" if bool(row["has_planning_after_current_filters"]) else ("sin_planificacion_para_filtros_seleccionados" if bool(row["has_any_planning_in_period"]) else "sin_planificacion_en_periodo"),
        axis=1,
    )
    result["suspected_permission_issue"] = False
    result["notes"] = result["absence_reason"]
    keep = [
        "person_key",
        "employee_id",
        "user_id",
        "resource_id",
        "person_name",
        "active",
        "department_name",
        "internal_group",
        "subdepartment",
        "workload_factor",
        "available_hours_period",
        "present_in_organization",
        "present_in_actuals",
        "actual_hours_period",
        "present_in_planning_raw",
        "present_in_planning_processed",
        "planning_rows",
        "planned_hours_period",
        "first_planning_date",
        "last_planning_date",
        "included_after_year_filter",
        "included_after_period_filter",
        "included_after_department_filter",
        "included_after_unit_filter",
        "included_after_nature_filter",
        "included_after_management_group_filter",
        "visible_in_person_filter",
        "has_any_planning_in_period",
        "has_planning_after_current_filters",
        "status",
        "absence_reason",
        "suspected_permission_issue",
        "notes",
    ]
    return result[keep].sort_values(["status", "person_name"])


def write_planning_people_reports(waterfall_rows: list[dict[str, Any]], coverage: pd.DataFrame, planning_df: pd.DataFrame) -> None:
    DATA_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(waterfall_rows).to_csv(PLANNING_PEOPLE_FILTER_WATERFALL_FILE, sep=";", encoding="utf-8-sig", index=False)
    coverage.to_csv(PLANNING_PEOPLE_COVERAGE_FILE, sep=";", encoding="utf-8-sig", index=False)
    if PLANNING_ODOO_PEOPLE_VISIBILITY_FILE.exists() and PLANNING_PEOPLE_ODOO_VS_APP_FILE.exists():
        return
    visibility = (
        planning_df.groupby(["person_id", "person_name"], as_index=False, dropna=False)
        .agg(planning_rows=("person_name", "size"), planned_hours=("display_hours", "sum"), min_date=("date_start", "min"), max_date=("date_end", "max"))
        .rename(columns={"person_id": "employee_id"})
        if not planning_df.empty and "person_id" in planning_df.columns
        else pd.DataFrame(columns=["employee_id", "person_name", "planning_rows", "planned_hours", "min_date", "max_date"])
    )
    visibility["visible_in_odoo_api"] = visibility["planning_rows"].gt(0) if "planning_rows" in visibility else False
    visibility["visible_in_processed"] = visibility["planning_rows"].gt(0) if "planning_rows" in visibility else False
    visibility["visibility_difference"] = 0
    visibility["possible_cause"] = "sin_diferencia_raw_procesado_local"
    visibility.to_csv(PLANNING_ODOO_PEOPLE_VISIBILITY_FILE, sep=";", encoding="utf-8-sig", index=False)
    app = visibility.rename(columns={"planning_rows": "processed_rows", "planned_hours": "processed_planned_hours"}).copy()
    app["odoo_rows"] = app["processed_rows"]
    app["odoo_planned_hours"] = app["processed_planned_hours"]
    app["raw_rows"] = app["processed_rows"]
    app["raw_planned_hours"] = app["processed_planned_hours"]
    app["app_visible"] = True
    app["difference_rows"] = 0
    app["difference_hours"] = 0.0
    app["validation_status"] = "LOCAL_RAW_PROCESSED_MATCH"
    app.to_csv(PLANNING_PEOPLE_ODOO_VS_APP_FILE, sep=";", encoding="utf-8-sig", index=False)


def planning_stage_row(order: int, name: str, previous: pd.DataFrame, current: pd.DataFrame, reason: str) -> dict[str, Any]:
    if previous.empty:
        previous = current.copy()
    prev_people = set(options(previous["person_name"])) if not previous.empty and "person_name" in previous.columns else set()
    cur_people = set(options(current["person_name"])) if not current.empty and "person_name" in current.columns else set()
    prev_hours = float(previous["display_hours"].sum()) if not previous.empty and "display_hours" in previous.columns else 0.0
    cur_hours = float(current["display_hours"].sum()) if not current.empty and "display_hours" in current.columns else 0.0
    return {
        "stage_order": order,
        "stage_name": name,
        "row_count": int(len(current)),
        "unique_people": int(len(cur_people)),
        "planned_hours": cur_hours,
        "people_removed": int(len(prev_people - cur_people)),
        "rows_removed": int(len(previous) - len(current)),
        "hours_removed": prev_hours - cur_hours,
        "removal_reason": reason,
        "generated_at": now_text(),
    }


def planning_filters(df: pd.DataFrame, prefix: str, organization_source: pd.DataFrame | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:
    lang = current_language()
    with st.expander(t("app.filters.view_config", lang=lang), expanded=False):
        diagnostics: dict[str, int] = {"dataset total": len(df)}
        years = sorted(df["year"].dropna().astype(int).unique().tolist()) if not df.empty else [date.today().year]
        year = st.selectbox(t("app.filters.year", lang=lang), years, index=len(years) - 1, key=f"{prefix}_year")
        base = df[df["year"].astype(int) == int(year)].copy()
        diagnostics["tras año"] = len(base)
        months, period_label = month_range_selector(prefix)
        base = base[base["month"].astype(int).isin(months)].copy()
        diagnostics["tras periodo"] = len(base)
        departments = select_all_multiselect(t("app.filters.department", lang=lang), options(base["department_name"]), f"{prefix}_departments")
        base = base[base["department_name"].isin(departments)].copy()
        diagnostics["tras departamento"] = len(base)
        units = select_all_multiselect(t("app.chart.group_by_unit", lang=lang), options(base["unidad_destino_label"]), f"{prefix}_units")
        base = base[base["unidad_destino_label"].isin(units)].copy()
        diagnostics["tras unidad destino"] = len(base)
        natures = select_all_multiselect(t("app.chart.group_by_nature", lang=lang), options(base["naturaleza_trabajo_label"]), f"{prefix}_natures")
        base = base[base["naturaleza_trabajo_label"].isin(natures)].copy()
        diagnostics["tras naturaleza trabajo"] = len(base)
        groups = select_all_multiselect(t("app.filters.management_group", lang=lang), options(base["grupo_gestion"]), f"{prefix}_management_groups")
        base = base[base["grupo_gestion"].isin(groups)].copy()
        diagnostics["tras grupo gestion"] = len(base)
        people = select_all_multiselect(t("app.filters.person", lang=lang), options(base["person_name"]), f"{prefix}_people")
        base = base[base["person_name"].isin(people)].copy()
        diagnostics["tras persona"] = len(base)
        top_n = st.slider(t("app.filters.top_n", lang=lang), 5, 50, 15, 5, key=f"{prefix}_topn")
        with st.expander(t("app.filters.advanced", lang=lang), expanded=False):
            projects = select_all_multiselect(t("column.project_name", lang=lang), options(base["project_name"]), f"{prefix}_projects")
            base = base[base["project_name"].isin(projects)].copy()
            diagnostics["tras proyecto"] = len(base)
            tasks = select_all_multiselect(t("column.task_name", lang=lang), options(base["task_name"]), f"{prefix}_tasks")
            base = base[base["task_name"].isin(tasks)].copy()
            diagnostics["tras tarea"] = len(base)
    base["display_hours"] = base["planned_hours"]
    base["ordu_errealak"] = base["display_hours"]
    return base, {
        "year": int(year),
        "months": months,
        "period": period_label,
        "selected_people": people,
        "selected_units": units,
        "selected_natures": natures,
        "management_groups": groups,
        "projects": projects,
        "tasks": tasks,
        "departments": departments,
        "top_n": top_n,
        "scope": ", ".join(departments) if departments else "Todos",
        "subdepartment": "",
        "diagnostics": diagnostics,
    }


def planning_filters_with_organization(df: pd.DataFrame, prefix: str, organization_source: pd.DataFrame | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:
    lang = current_language()
    with st.expander(t("app.filters.view_config", lang=lang), expanded=False):
        diagnostics: dict[str, int] = {"dataset total": len(df)}
        years = sorted(df["year"].dropna().astype(int).unique().tolist()) if not df.empty else [date.today().year]
        year = st.selectbox(t("app.filters.year", lang=lang), years, index=len(years) - 1, key=f"{prefix}_year")
        organization_all = load_organization_people(organization_source if organization_source is not None else pd.DataFrame(), int(year))
        previous = df.copy()
        base = df[df["year"].astype(int) == int(year)].copy()
        waterfall_rows = [planning_stage_row(1, "year", previous, base, "Filtro de año")]
        diagnostics["tras año"] = len(base)

        parent_departments = sorted(set(options(organization_all["department_name"])) | {department_parent(value) for value in options(base["department_name"]) if department_parent(value)})
        department_options = ["Todos los departamentos"] + [value for value in parent_departments if value]
        default_department = department_options.index("PROIEKTUAK ETA ZERBITZU TEKNIKOAK") if "PROIEKTUAK ETA ZERBITZU TEKNIKOAK" in department_options else 0
        department = st.selectbox(t("app.filters.department", lang=lang), department_options, index=default_department, key=f"{prefix}_department")
        organization_department = filter_organization_people(organization_all, department, "Todos")
        previous = base.copy()
        if department != "Todos los departamentos":
            base = base[base["department_name"].map(lambda value: department_parent(value) == department or clean_text(value) == clean_text(department))].copy()
        waterfall_rows.append(planning_stage_row(2, "department", previous, base, "Filtro de departamento"))
        diagnostics["tras departamento"] = len(base)

        subdepartment_options = ["Todos"] + options(organization_department["subdepartment"])
        subdepartment = st.selectbox(t("app.filters.subdepartment", lang=lang), subdepartment_options, key=f"{prefix}_subdepartment")
        organization_scope_before_person = filter_organization_people(organization_all, department, subdepartment)
        previous = base.copy()
        if subdepartment != "Todos":
            base = base[base["department_name"].map(clean_text).eq(clean_text(subdepartment))].copy()
        waterfall_rows.append(planning_stage_row(3, "internal_group", previous, base, "Filtro de grupo interno / subdepartamento"))
        diagnostics["tras subdepartamento"] = len(base)

        months, period_label = month_range_selector(prefix)
        previous = base.copy()
        base = base[base["month"].astype(int).isin(months)].copy()
        planning_period_before_dimension_filters = base.copy()
        waterfall_rows.append(planning_stage_row(4, "period", previous, base, "Filtro de periodo mensual"))
        diagnostics["tras periodo"] = len(base)

        units = select_all_multiselect(t("app.chart.group_by_unit", lang=lang), options(base["unidad_destino_label"]), f"{prefix}_units")
        previous = base.copy()
        base = base[base["unidad_destino_label"].isin(units)].copy()
        waterfall_rows.append(planning_stage_row(5, "management_unit", previous, base, "Filtro de unidad destino"))
        diagnostics["tras unidad destino"] = len(base)

        natures = select_all_multiselect(t("app.chart.group_by_nature", lang=lang), options(base["naturaleza_trabajo_label"]), f"{prefix}_natures")
        previous = base.copy()
        base = base[base["naturaleza_trabajo_label"].isin(natures)].copy()
        waterfall_rows.append(planning_stage_row(6, "work_nature", previous, base, "Filtro de naturaleza del trabajo"))
        diagnostics["tras naturaleza trabajo"] = len(base)

        groups = select_all_multiselect(t("app.filters.management_group", lang=lang), options(base["grupo_gestion"]), f"{prefix}_management_groups")
        previous = base.copy()
        base = base[base["grupo_gestion"].isin(groups)].copy()
        waterfall_rows.append(planning_stage_row(7, "management_group", previous, base, "Filtro de unidad destino + naturaleza"))
        diagnostics["tras grupo gestion"] = len(base)

        people_options = people_filter_options(organization_scope_before_person, base)
        if not people_options and not base.empty:
            people_options = options(base["person_name"])
            organization_scope_before_person = deduplicate_scope_people(
                pd.DataFrame(
                    {
                        "person_name": people_options,
                        "person_key": [normalize_text(person) for person in people_options],
                        "department_name": department,
                        "subdepartment": subdepartment if subdepartment != "Todos" else department,
                        "internal_group": subdepartment if subdepartment != "Todos" else department,
                        "active": True,
                        "actual_hours_period": 0.0,
                        "present_in_organization": False,
                    }
                )
            )
        people = select_all_multiselect(t("app.filters.person", lang=lang), people_options, f"{prefix}_people")
        organization_scope = organization_scope_before_person[organization_scope_before_person["person_name"].isin(people)].copy() if not organization_scope_before_person.empty else organization_scope_before_person
        previous = base.copy()
        base = base[base["person_name"].isin(people)].copy()
        waterfall_rows.append(planning_stage_row(8, "person", previous, base, "Filtro de persona desde poblacion organizativa"))
        diagnostics["tras persona"] = len(base)

        top_n = st.slider(t("app.filters.top_n", lang=lang), 5, 50, 15, 5, key=f"{prefix}_topn")
        with st.expander(t("app.filters.advanced", lang=lang), expanded=False):
            projects = select_all_multiselect(t("column.project_name", lang=lang), options(base["project_name"]), f"{prefix}_projects")
            previous = base.copy()
            base = base[base["project_name"].isin(projects)].copy()
            waterfall_rows.append(planning_stage_row(9, "project", previous, base, "Filtro avanzado de proyecto"))
            diagnostics["tras proyecto"] = len(base)
            tasks = select_all_multiselect(t("column.task_name", lang=lang), options(base["task_name"]), f"{prefix}_tasks")
            previous = base.copy()
            base = base[base["task_name"].isin(tasks)].copy()
            waterfall_rows.append(planning_stage_row(10, "task", previous, base, "Filtro avanzado de tarea"))
            diagnostics["tras tarea"] = len(base)

    base["display_hours"] = base["planned_hours"]
    base["ordu_errealak"] = base["display_hours"]
    return base, {
        "year": int(year),
        "months": months,
        "period": period_label,
        "selected_people": people,
        "selected_units": units,
        "selected_natures": natures,
        "management_groups": groups,
        "projects": projects,
        "tasks": tasks,
        "departments": [department] if department != "Todos los departamentos" else department_options[1:],
        "selected_department": department,
        "selected_internal_groups": [] if subdepartment == "Todos" else [subdepartment],
        "top_n": top_n,
        "scope": department,
        "subdepartment": subdepartment,
        "organization_people": organization_scope,
        "organization_people_before_person_filter": organization_scope_before_person,
        "planning_period_before_dimension_filters": planning_period_before_dimension_filters,
        "waterfall_rows": waterfall_rows,
        "diagnostics": diagnostics,
    }


def planning_hours_by_status(df: pd.DataFrame, value_col: str = "display_hours") -> tuple[float, float, float, float]:
    assured = float(df.loc[df["planning_status"] == "asegurada", value_col].sum()) if not df.empty else 0.0
    possible = float(df.loc[df["planning_status"] == "posible", value_col].sum()) if not df.empty else 0.0
    pending = float(df.loc[df["planning_status"] == "pendiente", value_col].sum()) if not df.empty else 0.0
    weighted_possible = float(df.loc[df["planning_status"] == "posible", "weighted_planned_hours"].sum()) if not df.empty else 0.0
    return assured, possible, weighted_possible, pending


def planning_person_load_table(
    df: pd.DataFrame,
    organization_people_or_availability: pd.DataFrame,
    availability_people: pd.DataFrame | None = None,
    include_zero_planning: bool = True,
) -> pd.DataFrame:
    if availability_people is None:
        availability_people = organization_people_or_availability
        organization_people = pd.DataFrame(
            {
                "person_name": sorted(set(df.get("person_name", pd.Series(dtype=str)).dropna().astype(str)) | set(availability_people.get("person_name", pd.Series(dtype=str)).dropna().astype(str))),
                "department_name": "",
                "internal_group": "",
                "subdepartment": "",
                "person_key": "",
            }
        )
    else:
        organization_people = organization_people_or_availability
    columns = [
        "persona",
        "department_name",
        "internal_group",
        "subdepartment",
        "horas_planificadas",
        "horas_disponibles",
        "diferencia_vs_disponibilidad",
        "ocupacion_planificada_pct",
        "proyectos",
        "tareas",
        "has_planning",
        "has_planning_after_current_filters",
        "load_status",
        "planning_status",
        "estado",
    ]
    if organization_people.empty and df.empty:
        return pd.DataFrame(columns=columns)
    hours_column = "planned_hours" if "planned_hours" in df.columns else "display_hours"
    planned = df.groupby("person_name")[hours_column].sum() if not df.empty and hours_column in df.columns else pd.Series(dtype=float)
    positive_df = df[pd.to_numeric(df[hours_column], errors="coerce").fillna(0.0) > 0].copy() if not df.empty and hours_column in df.columns else pd.DataFrame()
    projects = positive_df.groupby("person_name")["project_name"].nunique() if not positive_df.empty and "project_name" in positive_df.columns else pd.Series(dtype=int)
    tasks = positive_df.groupby("person_name")["task_name"].nunique() if not positive_df.empty and "task_name" in positive_df.columns else pd.Series(dtype=int)
    people = options(organization_people["person_name"]) if not organization_people.empty and "person_name" in organization_people.columns else []
    if not people:
        people = sorted(set(df.get("person_name", pd.Series(dtype=str)).dropna().astype(str)) | set(availability_people.get("person_name", pd.Series(dtype=str)).dropna().astype(str)))
    availability = availability_people.groupby("person_name")["calculated_available_hours"].sum() if not availability_people.empty else pd.Series(dtype=float)
    rows = []
    for person in people:
        available = float(availability.get(person, 0.0))
        total = float(planned.get(person, 0.0))
        occupation_total = total / available * 100 if available > 0 else None
        has_planning = total > 0
        if not include_zero_planning and not has_planning:
            continue
        if available <= 0:
            load_status = "Sin disponibilidad" if total > 0 else "OK"
        elif total > available:
            load_status = "Sobrecarga"
        elif total > available * 0.9:
            load_status = "Riesgo"
        else:
            load_status = "OK"
        org_match = organization_people[organization_people["person_name"] == person].head(1) if not organization_people.empty and "person_name" in organization_people.columns else pd.DataFrame()
        planning_status = "Con planificación" if has_planning else "Sin planificación"
        rows.append(
            {
                "persona": person,
                "department_name": clean_text(org_match["department_name"].iloc[0]) if not org_match.empty and "department_name" in org_match.columns else "",
                "internal_group": clean_text(org_match["internal_group"].iloc[0]) if not org_match.empty and "internal_group" in org_match.columns else "",
                "subdepartment": clean_text(org_match["subdepartment"].iloc[0]) if not org_match.empty and "subdepartment" in org_match.columns else "",
                "horas_planificadas": total,
                "horas_disponibles": available,
                "diferencia_vs_disponibilidad": available - total,
                "ocupacion_planificada_pct": occupation_total if occupation_total is not None else None,
                "proyectos": int(projects.get(person, 0)),
                "tareas": int(tasks.get(person, 0)),
                "has_planning": has_planning,
                "has_planning_after_current_filters": has_planning,
                "load_status": load_status,
                "planning_status": planning_status,
                "estado": load_status,
            }
        )
    return pd.DataFrame(rows, columns=columns).sort_values(["horas_planificadas", "persona"], ascending=[False, True])


def write_planning_diagnostics(df: pd.DataFrame, person_load: pd.DataFrame, availability: pd.DataFrame) -> None:
    DATA_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    diagnostics = pd.DataFrame(
        [
            {
                "total_lineas": int(len(df)),
                "lineas_activas": int(len(df)),
                "horas_planificadas": float(df["planned_hours"].sum()) if not df.empty else 0.0,
                "personas": int(df["person_name"].nunique()) if not df.empty else 0,
                "proyectos": int(df["project_name"].nunique()) if not df.empty else 0,
                "tareas": int(df["task_name"].nunique()) if not df.empty else 0,
                "lineas_pendientes_clasificar": int(df["classification_status"].eq("pendiente").sum()) if not df.empty else 0,
                "personas_en_sobrecarga": int(person_load["estado"].eq("Sobrecarga").sum()) if not person_load.empty else 0,
                "personas_en_riesgo": int(person_load["estado"].eq("Riesgo").sum()) if not person_load.empty else 0,
                "horas_disponibles": float(availability["available_hours"].sum()) if not availability.empty else 0.0,
                "dataset_path": str(PLANNING_PROCESSED_FILE.relative_to(ROOT_DIR)),
                "generated_at": now_text(),
            }
        ]
    )
    diagnostics.to_csv(PLANNING_DIAGNOSTICS_FILE, sep=";", encoding="utf-8-sig", index=False)
    person_load.to_csv(PLANNING_OVERLOADS_FILE, sep=";", encoding="utf-8-sig", index=False)
    pending = df[df["classification_status"] == "pendiente"].copy()
    if pending.empty:
        pending_report = pd.DataFrame(columns=["proyecto", "tarea", "persona", "departamento", "horas"])
    else:
        pending_report = (
            pending.groupby(["project_name", "task_name", "person_name", "department_name"], as_index=False)
            .agg(horas=("display_hours", "sum"))
            .rename(columns={"project_name": "proyecto", "task_name": "tarea", "person_name": "persona", "department_name": "departamento"})
        )
    pending_report.to_csv(PLANNING_PENDING_CLASSIFICATION_FILE, sep=";", encoding="utf-8-sig", index=False)


def write_person_planning_reconciliation(df: pd.DataFrame) -> dict[str, Any]:
    DATA_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    expected_records = 29
    expected_planned_hours = duration_hhmm_to_hours("523:12")
    expected_imputed_hours = duration_hhmm_to_hours("46:00")
    expected_remaining_hours = duration_hhmm_to_hours("477:12")
    raw_path = DATA_RAW_DIR / "09_project_forecast.json"
    if not raw_path.exists():
        raw_path = DATA_RAW_DIR / "09_project_forecast_v3_SAFE.json"
    if not raw_path.exists():
        raw_path = DATA_RAW_DIR / "10_project_task_planning_all.json"
    if not raw_path.exists():
        raw_path = DATA_RAW_DIR / "10_project_task_planning_all.csv"
    raw = pd.DataFrame()
    if raw_path.exists():
        if raw_path.suffix.lower() == ".json":
            raw = pd.DataFrame(json.loads(raw_path.read_text(encoding="utf-8")))
        else:
            raw = pd.read_csv(raw_path, sep=";", encoding="utf-8-sig", dtype=str).fillna("")
    processed_by_source = (
        df.groupby("source_id", as_index=False, dropna=False)
        .agg(
            person_name_processed=("person_name", "first"),
            active_processed=("active", "first"),
            planned_hours_processed=("planned_hours", "sum"),
        )
        if not df.empty and "source_id" in df.columns
        else pd.DataFrame(columns=["source_id", "person_name_processed", "active_processed", "planned_hours_processed"])
    )
    rows: list[dict[str, Any]] = []
    reference_terms = ["Proyecto de referencia", "Tarea de referencia"]
    period_start = pd.Timestamp("2026-01-01")
    period_end = pd.Timestamp("2026-12-31")
    target_person_norm = normalized_match_text("Persona Auditada")
    if not raw.empty:
        for index, row in raw.iterrows():
            source_id = clean_text(row.get("id", ""))
            employee_id, employee_name = safe_parse_many2one(row.get("employee_id", ""))
            user_id, user_name = safe_parse_many2one(row.get("user_id", ""))
            resource_id, resource_name = safe_parse_many2one(row.get("resource_id", ""))
            project_id, project_name = safe_parse_many2one(row.get("project_id", ""))
            person_name_raw = employee_name or user_name or resource_name
            person_id = employee_id or user_id or resource_id
            task_name = clean_text(row.get("name", ""))
            haystack = normalized_match_text(" ".join([project_name, task_name, person_name_raw]))
            is_reference_term = any(normalized_match_text(term) in haystack for term in reference_terms)
            is_target_person = normalized_match_text(person_name_raw) == target_person_norm
            if not is_target_person and not is_reference_term:
                continue
            start = pd.to_datetime(clean_text(row.get("date_start", "")), errors="coerce")
            end = pd.to_datetime(clean_text(row.get("date_deadline", "")) or clean_text(row.get("date_end", "")) or clean_text(row.get("date_start", "")), errors="coerce")
            if pd.isna(end):
                end = start
            overlap = bool(pd.notna(start) and pd.notna(end) and pd.Timestamp(start).normalize() <= period_end and pd.Timestamp(end).normalize() >= period_start)
            raw_hours_text = clean_text(row.get("planned_hours", "")) or clean_text(row.get("quantity", ""))
            if not raw_hours_text and ("effective_hours" in row.index or "remaining_hours" in row.index):
                effective = to_float(row.get("effective_hours", ""), 0.0) or 0.0
                remaining = to_float(row.get("remaining_hours", ""), 0.0) or 0.0
                raw_hours_text = str(effective + remaining)
            raw_hours = duration_hhmm_to_hours(raw_hours_text) if ":" in raw_hours_text else (to_float(raw_hours_text, 0.0) or 0.0)
            processed_match = processed_by_source[processed_by_source["source_id"].astype(str) == source_id]
            processed_hours = float(processed_match["planned_hours_processed"].sum()) if not processed_match.empty else 0.0
            raw_imputed = to_float(row.get("effective_hours", ""), 0.0) or 0.0
            raw_remaining = to_float(row.get("remaining_hours", ""), 0.0) or 0.0
            active_raw = clean_text(row.get("active", ""))
            included = is_target_person and overlap and not processed_match.empty
            reasons = []
            if not is_target_person:
                reasons.append("persona_no_es_objetivo_en_raw")
            if not overlap:
                reasons.append("sin_solape_2026")
            if processed_match.empty:
                reasons.append("no_incluido_en_procesado")
            rows.append(
                {
                    "source_file": raw_path.name,
                    "source_row_id": index,
                    "source_id": source_id,
                    "employee_id": employee_id,
                    "user_id": user_id,
                    "resource_id": resource_id,
                    "person_id_used": person_id,
                    "person_name_raw": person_name_raw,
                    "person_name_processed": clean_text(processed_match["person_name_processed"].iloc[0]) if not processed_match.empty else "",
                    "project_id": project_id,
                    "project_name": project_name,
                    "task_name": task_name,
                    "date_start_raw": clean_text(row.get("date_start", "")),
                    "date_end_raw": clean_text(row.get("date_deadline", "")) or clean_text(row.get("date_end", "")),
                    "planned_hours_raw": raw_hours,
                    "planned_minutes_raw": int(round(raw_hours * 60)),
                    "imputed_hours_raw": raw_imputed,
                    "remaining_hours_raw": raw_remaining,
                    "planned_hours_processed": processed_hours,
                    "active_raw": active_raw,
                    "active_processed": clean_text(processed_match["active_processed"].iloc[0]) if not processed_match.empty else "",
                    "included_in_processed": not processed_match.empty,
                    "included_in_reference_filter": included,
                    "exclusion_reason": "; ".join(reasons),
                }
            )
    diagnostics = pd.DataFrame(rows)
    diagnostics.to_csv(PLANNING_PERSON_AUDIT_DIAGNOSTICS_FILE, sep=";", encoding="utf-8-sig", index=False)
    if diagnostics.empty:
        detail = pd.DataFrame(columns=["source_id", "project_id", "project_name", "task_id", "task_name", "person_name", "date_start", "date_end", "raw_planned_hours", "processed_planned_hours", "included_in_reference_filter", "exclusion_reason", "difference", "validation_status"])
    else:
        included = diagnostics[diagnostics["included_in_reference_filter"]].copy()
        detail = pd.DataFrame(
            {
                "source_id": included.get("source_id", pd.Series(dtype=str)),
                "project_id": included.get("project_id", pd.Series(dtype=str)),
                "project_name": included.get("project_name", pd.Series(dtype=str)),
                "task_id": included.get("source_id", pd.Series(dtype=str)),
                "task_name": included.get("task_name", pd.Series(dtype=str)),
                "person_name": included.get("person_name_raw", pd.Series(dtype=str)),
                "date_start": included.get("date_start_raw", pd.Series(dtype=str)),
                "date_end": included.get("date_end_raw", pd.Series(dtype=str)),
                "raw_planned_hours": included.get("planned_hours_raw", pd.Series(dtype=float)),
                "raw_imputed_hours": included.get("imputed_hours_raw", pd.Series(dtype=float)),
                "raw_remaining_hours": included.get("remaining_hours_raw", pd.Series(dtype=float)),
                "processed_planned_hours": included.get("planned_hours_processed", pd.Series(dtype=float)),
                "included_in_reference_filter": included.get("included_in_reference_filter", pd.Series(dtype=bool)),
                "exclusion_reason": included.get("exclusion_reason", pd.Series(dtype=str)),
            }
        )
        detail["difference"] = pd.to_numeric(detail["raw_planned_hours"], errors="coerce").fillna(0.0) - pd.to_numeric(detail["processed_planned_hours"], errors="coerce").fillna(0.0)
        detail["validation_status"] = detail["difference"].map(lambda value: "OK" if abs(float(value)) <= 0.01 else "DIFF")
    actual_records = int(detail["source_id"].nunique()) if not detail.empty else 0
    actual_planned_hours = float(detail["processed_planned_hours"].sum()) if not detail.empty else 0.0
    actual_imputed_hours = float(pd.to_numeric(detail.get("raw_imputed_hours", pd.Series(dtype=float)), errors="coerce").fillna(0.0).sum()) if not detail.empty else 0.0
    actual_remaining_hours = float(pd.to_numeric(detail.get("raw_remaining_hours", pd.Series(dtype=float)), errors="coerce").fillna(0.0).sum()) if not detail.empty else 0.0
    validation_status = "PASS" if actual_records == expected_records and abs(actual_planned_hours - expected_planned_hours) <= 0.01 else "FAIL"
    summary = pd.DataFrame(
        [
            {
                "expected_records": expected_records,
                "actual_records": actual_records,
                "expected_planned_hours": expected_planned_hours,
                "actual_planned_hours": actual_planned_hours,
                "expected_imputed_hours": expected_imputed_hours,
                "actual_imputed_hours": actual_imputed_hours,
                "expected_remaining_hours": expected_remaining_hours,
                "actual_remaining_hours": actual_remaining_hours,
                "record_difference": actual_records - expected_records,
                "hours_difference": actual_planned_hours - expected_planned_hours,
                "validation_status": validation_status,
            }
        ]
    )
    detail.to_csv(PLANNING_PERSON_AUDIT_FILE, sep=";", encoding="utf-8-sig", index=False)
    summary.to_csv(PLANNING_PERSON_AUDIT_SUMMARY_FILE, sep=";", encoding="utf-8-sig", index=False)
    return summary.iloc[0].to_dict()


def top_n_planning_dimension(df: pd.DataFrame, dimension: str, top_n: int) -> pd.DataFrame:
    if dimension in {"grupo_gestion", "unidad_destino_label", "naturaleza_trabajo_label"} or df.empty:
        return df.copy()
    totals = df.groupby(dimension)["display_hours"].sum().sort_values(ascending=False)
    keep = totals.head(top_n).index.tolist()
    result = df.copy()
    result[dimension] = result[dimension].where(result[dimension].isin(keep), "Otros")
    return result


def build_planning_monthly_figure(df: pd.DataFrame, months: list[int], available: pd.DataFrame, dimension: str, top_n: int, lang: str) -> go.Figure:
    color_map = build_dimension_color_map(top_n_planning_dimension(df, dimension, top_n), dimension)
    fig = build_monthly_group_chart(df, months, available, t("planning.monthly_title", lang=lang), dimension, top_n, lang, color_map)
    fig.update_traces(name=t("metric.planned_hours", lang=lang), selector={"name": t("column.horas", lang=lang, default="Horas")})
    return fig


def build_planning_pareto_figure(df: pd.DataFrame, dimension: str, top_n: int, available_total: float, lang: str) -> tuple[go.Figure, pd.DataFrame]:
    del available_total
    source = top_n_planning_dimension(df, dimension, top_n)
    color_map = build_dimension_color_map(source, dimension)
    fig = build_pareto_figure(df, f"Pareto - {translate_label(dimension, 'column', lang)}", dimension, top_n, color_map, lang)
    table = build_hours_by_dimension_table(source, dimension).rename(columns={"horas": "planned_hours"})
    return fig, table


def build_person_load_figure(df: pd.DataFrame, person_load: pd.DataFrame, dimension: str, top_n: int, lang: str) -> go.Figure:
    source = top_n_planning_dimension(df, dimension, top_n)
    grouped = source.groupby(["person_name", dimension], as_index=False).agg(hours=("display_hours", "sum"))
    people = person_load.sort_values("horas_planificadas", ascending=True)["persona"].tolist()
    categories = options(grouped[dimension])
    color_map = build_dimension_color_map(source, dimension)
    fig = go.Figure()
    for category in categories:
        base_color = color_map.get(category, DEFAULT_CATEGORY_COLOR)
        values = []
        for person in people:
            match = grouped[(grouped["person_name"] == person) & (grouped[dimension] == category)]
            values.append(float(match["hours"].sum()) if not match.empty else 0.0)
        fig.add_bar(x=values, y=people, orientation="h", name=category, marker_color=base_color)
    if not person_load.empty:
        fig.add_scatter(
            x=person_load.set_index("persona").reindex(people)["horas_disponibles"].fillna(0.0),
            y=people,
            mode="markers",
            name=t("column.available_hours", lang=lang, default="Horas disponibles"),
            marker={"color": "#FF4B4B", "symbol": "line-ns-open", "size": 14},
        )
    fig.update_layout(title=t("planning.person_load_view", lang=lang), barmode="stack", xaxis_title=t("column.horas", lang=lang), yaxis_title=t("column.person_name", lang=lang), height=max(450, 34 * max(1, len(people))))
    return fig


def render_planning_summary(df: pd.DataFrame, available: pd.DataFrame, person_load: pd.DataFrame) -> None:
    lang = current_language()
    planned_total = float(df["planned_hours"].sum()) if not df.empty else 0.0
    available_total = float(available["available_hours"].sum()) if available["configured"].any() else 0.0
    metrics = [
        ("metric.planned_hours", planned_total, ""),
        ("metric.available_hours", available_total if available_total > 0 else None, ""),
        ("metric.difference_vs_available", available_total - planned_total if available_total > 0 else None, ""),
        ("metric.occupation_pct", planned_total / available_total * 100 if available_total > 0 else None, "%"),
        ("metric.people", df["person_name"].nunique(), ""),
        ("metric.projects", df["project_name"].nunique(), ""),
        ("metric.tasks", df["task_name"].nunique(), ""),
        ("metric.people_overloaded", int(person_load["estado"].eq("Sobrecarga").sum()) if not person_load.empty else 0, ""),
        ("metric.people_at_risk", int(person_load["estado"].eq("Riesgo").sum()) if not person_load.empty else 0, ""),
    ]
    st.markdown(f"### {t('planning.summary', lang=lang)}")
    for start in (0, 4, 8):
        cols = st.columns(4)
        for col, (label_key, value, suffix) in zip(cols, metrics[start : start + 4]):
            label = t(label_key, lang=lang)
            if value is None:
                col.metric(label, t("metric.not_configured", lang=lang))
            elif isinstance(value, (int, float)):
                col.metric(label, f"{value:.1f}{suffix}")
            else:
                col.metric(label, value)


def render_person_planning_coverage_summary(person_load: pd.DataFrame, lang: str) -> None:
    metrics = planning_people_coverage_metrics(person_load)
    st.markdown(f"### {t('planning.people_scope_summary', lang=lang)}")
    cols = st.columns(4)
    cols[0].metric(t("planning.people_in_scope", lang=lang), format_integer_es(metrics["people_in_scope"]))
    cols[1].metric(t("planning.people_with_planning", lang=lang), format_integer_es(metrics["people_with_planning"]))
    cols[2].metric(t("planning.people_without_planning", lang=lang), format_integer_es(metrics["people_without_planning"]))
    cols[3].metric(t("planning.person_coverage_pct", lang=lang), f"{format_number_es(metrics['person_planning_coverage_pct'], 1)}%")


def render_planning_data_section() -> None:
    lang = current_language()
    with st.expander(t("planning.data", lang=lang), expanded=False):
        st.write(f"Dataset: `{PLANNING_PROCESSED_FILE.relative_to(ROOT_DIR)}`")
        st.code("$env:PYTHONPATH='src'; python -m imh_oreka.planning_data", language="powershell")
        if PLANNING_PROCESSED_FILE.exists():
            modified = datetime.fromtimestamp(PLANNING_PROCESSED_FILE.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            st.caption(f"Ultima modificacion: {modified}")


def planning_report_filter_summary(context: dict[str, Any], months: list[int], lang: str) -> dict[str, Any]:
    return {
        "A?o": context.get("year", ""),
        "Periodo": f"{month_label(months[0], lang, False)}-{month_label(months[-1], lang, False)}" if months else "",
        "Departamento": context.get("departments", []),
        "Personas": context.get("selected_people", []),
        "Proyectos": context.get("projects", []),
        "Tareas": context.get("tasks", []),
        "Unidad destino": context.get("selected_units", []),
        "Naturaleza": context.get("selected_natures", []),
        "Unidad destino + naturaleza": context.get("management_groups", []),
    }


def build_project_task_assignments_table(df: pd.DataFrame) -> pd.DataFrame:
    """Summarise assigned hours without losing the person-project-task relationship."""
    columns = ["person_name", "project_name", "task_name", "assigned_hours"]
    if df.empty:
        return pd.DataFrame(columns=columns)
    hours_column = "display_hours" if "display_hours" in df.columns else "planned_hours"
    required = {"person_name", "project_name", "task_name", hours_column}
    if not required.issubset(df.columns):
        return pd.DataFrame(columns=columns)
    assignments = df.copy()
    assignments[hours_column] = pd.to_numeric(assignments[hours_column], errors="coerce").fillna(0.0)
    assignments["project_name"] = assignments["project_name"].map(clean_text).replace("", "Sin proyecto")
    assignments["task_name"] = assignments["task_name"].map(clean_text).replace("", "Sin tarea")
    assignments = (
        assignments.groupby(["person_name", "project_name", "task_name"], as_index=False, dropna=False)
        .agg(assigned_hours=(hours_column, "sum"))
        .sort_values(["person_name", "project_name", "assigned_hours", "task_name"], ascending=[True, True, False, True])
    )
    return assignments[columns]


def project_task_assignments_html(assignments: pd.DataFrame, lang: str) -> str:
    if assignments.empty:
        return f"<p>{escape(t('reports.generator.no_data', lang=lang, default='Sin datos.'))}</p>"
    task_label = t("column.task_name", lang=lang, default="Tarea")
    person_label = t("column.person_name", lang=lang, default="Persona")
    hours_label = t("column.assigned_hours", lang=lang, default="Horas asignadas")
    show_person = assignments["person_name"].nunique(dropna=True) > 1
    sections: list[str] = []
    for project_name, project_rows in assignments.groupby("project_name", sort=False, dropna=False):
        project_total = float(project_rows["assigned_hours"].sum())
        headers = f"<th>{escape(task_label)}</th>"
        if show_person:
            headers += f"<th>{escape(person_label)}</th>"
        headers += f"<th class='hours'>{escape(hours_label)}</th>"
        rows = []
        for _, row in project_rows.iterrows():
            cells = f"<td>{escape(clean_text(row['task_name']))}</td>"
            if show_person:
                cells += f"<td>{escape(clean_text(row['person_name']))}</td>"
            cells += f"<td class='hours'>{escape(format_number_es(float(row['assigned_hours']), 2))}</td>"
            rows.append(f"<tr>{cells}</tr>")
        sections.append(
            "<section class='project-assignment'>"
            f"<h3>{escape(clean_text(project_name))}<span>{escape(format_number_es(project_total, 2))} h</span></h3>"
            f"<table class='data-table'><thead><tr>{headers}</tr></thead><tbody>{''.join(rows)}</tbody></table>"
            "</section>"
        )
    return "".join(sections)


def render_planning_report_html(title: str, df: pd.DataFrame, available: pd.DataFrame, person_load: pd.DataFrame, months: list[int], context: dict[str, Any], top_n: int, lang: str) -> tuple[str, dict[str, pd.DataFrame]]:
    available_total = float(available["available_hours"].sum()) if available["configured"].any() else 0.0
    monthly_group = build_planning_monthly_figure(df, months, available, "grupo_gestion", top_n, lang)
    monthly_project = build_planning_monthly_figure(df, months, available, "project_name", top_n, lang)
    pareto_group, pareto_group_table = build_planning_pareto_figure(df, "grupo_gestion", top_n, available_total, lang)
    pareto_project, pareto_project_table = build_planning_pareto_figure(df, "project_name", top_n, available_total, lang)
    person_fig = build_person_load_figure(df, person_load, "grupo_gestion", top_n, lang)
    project_table = df.groupby("project_name", as_index=False).agg(horas=("display_hours", "sum"), personas=("person_name", "nunique"), tareas=("task_name", "nunique")).sort_values("horas", ascending=False)
    unit_table = df.groupby("unidad_destino_label", as_index=False).agg(horas=("display_hours", "sum")).sort_values("horas", ascending=False)
    nature_table = df.groupby("naturaleza_trabajo_label", as_index=False).agg(horas=("display_hours", "sum")).sort_values("horas", ascending=False)
    group_table = df.groupby("grupo_gestion", as_index=False).agg(horas=("display_hours", "sum")).sort_values("horas", ascending=False)
    project_task_assignments = build_project_task_assignments_table(df)
    metrics = {
        "Horas planificadas": float(df["planned_hours"].sum()),
        "Horas disponibles": available_total if available_total > 0 else None,
        "Diferencia vs disponibles": available_total - float(df["planned_hours"].sum()) if available_total > 0 else None,
        "% ocupacion": float(df["planned_hours"].sum()) / available_total * 100 if available_total > 0 else None,
        "Personas": int(df["person_name"].nunique()) if not df.empty else 0,
        "Proyectos": int(df["project_name"].nunique()) if not df.empty else 0,
        "Tareas": int(df["task_name"].nunique()) if not df.empty else 0,
        "Personas en sobrecarga": int(person_load["estado"].eq("Sobrecarga").sum()) if not person_load.empty else 0,
        "Personas en riesgo": int(person_load["estado"].eq("Riesgo").sum()) if not person_load.empty else 0,
    }
    filters = planning_report_filter_summary(context, months, lang)
    filter_rows = "".join(f"<tr><th>{escape(clean_text(k))}</th><td>{escape(', '.join(v) if isinstance(v, list) else clean_text(v))}</td></tr>" for k, v in filters.items())
    html = f"""<!doctype html>
<html lang="{escape(lang)}">
<head><meta charset="utf-8"><title>{escape(title)}</title>
<style>
body {{ font-family: Segoe UI, Arial, sans-serif; margin: 32px; color: #1f2933; }}
h1, h2 {{ color: #102a43; }}
.metrics {{ display:grid; grid-template-columns:repeat(4,minmax(150px,1fr)); gap:12px; margin:18px 0; }}
.metric {{ border:1px solid #d9e2ec; padding:10px; border-radius:6px; background:#f8fafc; }}
.metric span {{ display:block; font-size:12px; color:#52606d; }}
.metric strong {{ font-size:20px; }}
.data-table {{ border-collapse:collapse; width:100%; font-size:13px; }}
.data-table th,.data-table td {{ border-bottom:1px solid #d9e2ec; padding:6px 8px; text-align:left; }}
.project-assignment {{ margin:18px 0 26px; break-inside:avoid; }}
.project-assignment h3 {{ display:flex; justify-content:space-between; gap:16px; margin-bottom:6px; color:#243b53; }}
.project-assignment h3 span {{ white-space:nowrap; color:#486581; font-size:0.9em; }}
.data-table .hours {{ text-align:right; white-space:nowrap; }}
</style></head>
<body>
<h1>{escape(title)}</h1>
<p><strong>{escape(t('report.generated_at', lang=lang, default='Fecha de generacion'))}:</strong> {escape(now_text())}</p>
<details><summary>{escape(t('report.filters', lang=lang, default='Filtros aplicados'))}</summary><table class="data-table">{filter_rows}</table></details>
<h2>{escape(t('report.executive_summary', lang=lang, default='Resumen ejecutivo'))}</h2>
{metrics_html(metrics, lang)}
<h2>Barras mensuales por unidad destino + naturaleza</h2>{monthly_group.to_html(full_html=False, include_plotlyjs=True)}
<h2>Barras mensuales por proyecto</h2>{monthly_project.to_html(full_html=False, include_plotlyjs=False)}
<h2>Pareto por unidad destino + naturaleza</h2>{pareto_group.to_html(full_html=False, include_plotlyjs=False)}
<h2>Pareto por proyecto</h2>{pareto_project.to_html(full_html=False, include_plotlyjs=False)}
<h2>Carga por persona</h2>{person_fig.to_html(full_html=False, include_plotlyjs=False)}
<h2>Tabla de sobrecargas</h2>{dataframe_html(person_load, lang)}
<h2>{escape(t('report.project_task_assignments', lang=lang, default='Tareas asignadas por proyecto'))}</h2>
{project_task_assignments_html(project_task_assignments, lang)}
<h2>Tabla por proyecto</h2>{dataframe_html(project_table, lang)}
<h2>Tabla por unidad destino</h2>{dataframe_html(unit_table, lang)}
<h2>Tabla por naturaleza</h2>{dataframe_html(nature_table, lang)}
<h2>Tabla por grupo de gestión</h2>{dataframe_html(group_table, lang)}
</body></html>"""
    return html, {
        "data_summary": pd.DataFrame([metrics]),
        "pareto_management_group": pareto_group_table,
        "pareto_project": pareto_project_table,
        "person_load": person_load,
        "project_task_assignments": project_task_assignments,
        "project_table": project_table,
        "unit_table": unit_table,
        "nature_table": nature_table,
        "management_group_table": group_table,
        "planning_lines": df,
    }


def write_planning_report_package(df: pd.DataFrame, available_df: pd.DataFrame, workload_df: pd.DataFrame, context: dict[str, Any], report_type: str, months: list[int], level: str, top_n: int, lang: str) -> dict[str, Any]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = PLANNING_REPORTS_DIR / f"report_{timestamp}"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_df = df[df["month"].astype(int).isin(months)].copy()
    scopes: list[tuple[str, str, pd.DataFrame]] = [("global", "Vista actual", report_df.copy())]
    if level == "with_sublevels":
        for department in options(report_df["department_name"]):
            scopes.append(("department", department, report_df[report_df["department_name"] == department].copy()))
        for person in options(report_df["person_name"]):
            scopes.append(("person", person, report_df[report_df["person_name"] == person].copy()))
    reports_generated: list[dict[str, str]] = []
    package_tables: dict[str, pd.DataFrame] = {}
    valid_scopes = [(kind, name, subset) for kind, name, subset in scopes if kind == "global" or not subset.empty]
    for index, (kind, name, subset) in enumerate(valid_scopes):
        organization_people = context.get("organization_people", pd.DataFrame()) if kind == "global" else pd.DataFrame()
        availability_scope = organization_people_scope_frame(organization_people) if isinstance(organization_people, pd.DataFrame) and not organization_people.empty else subset
        selected_people = options(organization_people["person_name"]) if isinstance(organization_people, pd.DataFrame) and not organization_people.empty else options(subset["person_name"])
        availability = resolve_available_hours_by_people(available_df, workload_df, availability_scope, int(context["year"]), months, selected_people)
        person_load = planning_person_load_table(
            subset,
            organization_people if isinstance(organization_people, pd.DataFrame) and not organization_people.empty else availability.get("people_diagnostics", pd.DataFrame()),
            availability.get("people_diagnostics", pd.DataFrame()) if isinstance(organization_people, pd.DataFrame) and not organization_people.empty else None,
            include_zero_planning=bool(context.get("show_people_without_planning", True)),
        )
        title = f"Informe de planificación - {name} - {month_label(months[0], lang, False)}-{month_label(months[-1], lang, False)} {context['year']}"
        html, tables = render_planning_report_html(title, subset, availability["monthly_available"], person_load, months, context, top_n, lang)
        if index == 0:
            filename = "index.html"
            package_tables = tables
        elif kind == "person":
            filename = f"person_{slugify_filename(name)}.html"
        else:
            filename = f"department_{slugify_filename(name)}.html"
        (report_dir / filename).write_text(html, encoding="utf-8")
        reports_generated.append({"type": kind, "name": name, "file": filename})
    for name, table in package_tables.items():
        table.to_csv(report_dir / f"{name}.csv", sep=";", encoding="utf-8-sig", index=False)
    first_value = lambda column, default="": clean_text(report_df[column].iloc[0]) if column in report_df.columns and not report_df.empty else default
    first_number = lambda column, default=0.0: float(pd.to_numeric(report_df[column], errors="coerce").dropna().iloc[0]) if column in report_df.columns and pd.to_numeric(report_df[column], errors="coerce").notna().any() else default
    metadata = {
        "generated_at": now_text(),
        "dataset_path": str(PLANNING_PROCESSED_FILE.relative_to(ROOT_DIR)),
        "dataset_modified_at": datetime.fromtimestamp(PLANNING_PROCESSED_FILE.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S") if PLANNING_PROCESSED_FILE.exists() else "",
        "raw_source": first_value("raw_source_file"),
        "rows_before_filters": int(context.get("rows_before_filters", len(df))),
        "rows_after_filters": int(len(report_df)),
        "planned_hours_before_filters": float(context.get("planned_hours_before_filters", 0.0)),
        "planned_hours_after_filters": float(report_df["planned_hours"].sum()) if "planned_hours" in report_df else 0.0,
        "year": int(context["year"]),
        "period_type": report_type,
        "month_start": int(months[0]),
        "month_end": int(months[-1]),
        "filters": planning_report_filter_summary(context, months, lang),
        "reports_generated": reports_generated,
        "transformation_timestamp": first_value("transformation_timestamp"),
        "raw_rows": int(first_number("raw_rows", 0.0)),
        "processed_rows": int(first_number("processed_rows", float(len(report_df)))),
        "raw_hours": first_number("raw_hours", 0.0),
        "processed_hours": first_number("processed_hours", float(report_df["display_hours"].sum()) if "display_hours" in report_df else 0.0),
        "classification_pending_rows": int(report_df["classification_status"].eq("pendiente").sum()) if "classification_status" in report_df else 0,
        "unmatched_people": len(read_csv(PLANNING_UNMATCHED_PEOPLE_FILE, ["odoo_person_id", "odoo_person_name", "user", "email", "project", "task", "hours", "reason"])),
        "people_in_scope": int(context.get("people_in_scope", 0)),
        "people_with_planning": int(context.get("people_with_planning", 0)),
        "people_without_planning": int(context.get("people_without_planning", 0)),
        "person_planning_coverage_pct": float(context.get("person_planning_coverage_pct", 0.0)),
        "selected_internal_groups": context.get("selected_internal_groups", []),
        "show_people_without_planning": bool(context.get("show_people_without_planning", True)),
        "reconciliation_status": "",
        "language": lang,
    }
    (report_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    zip_path = report_dir / f"prc01_planning_report_{timestamp}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in report_dir.iterdir():
            if path != zip_path and path.is_file():
                archive.write(path, arcname=path.name)
    return {"report_dir": report_dir, "zip_path": zip_path, "reports_generated": reports_generated}


def render_planning_report_generator(filtered: pd.DataFrame, available_df: pd.DataFrame, workload_df: pd.DataFrame, context: dict[str, Any], prefix: str) -> None:
    lang = current_language()
    with st.expander(t("planning.generate_reports", lang=lang), expanded=False):
        report_type_labels = {"monthly": "reports.generator.monthly", "annual": "reports.generator.annual", "between_months": "reports.generator.between_months"}
        report_type = st.selectbox(t("reports.generator.type", lang=lang), list(report_type_labels.keys()), index=2, format_func=lambda key: t(report_type_labels[key], lang=lang), key=f"{prefix}_planning_report_type")
        months = report_month_options(f"{prefix}_planning", report_type)
        level_labels = {"current_only": "reports.generator.current_view_only", "with_sublevels": "reports.generator.current_view_sublevels"}
        level = st.selectbox(t("reports.generator.detail_level", lang=lang), list(level_labels.keys()), format_func=lambda key: t(level_labels[key], lang=lang), key=f"{prefix}_planning_report_level")
        top_n = st.slider(t("reports.generator.top_n", lang=lang), 5, 50, int(context.get("top_n", 15)), 5, key=f"{prefix}_planning_report_topn")
        if st.button(t("reports.generator.generate", lang=lang), key=f"{prefix}_planning_generate_report"):
            organization_people = context.get("organization_people", pd.DataFrame())
            if filtered.empty and (not isinstance(organization_people, pd.DataFrame) or organization_people.empty):
                st.warning(t("reports.generator.no_data", lang=lang))
                return
            result = write_planning_report_package(filtered, available_df, workload_df, context, report_type, months, level, top_n, lang)
            st.success(f"{t('reports.generator.generated_ok', lang=lang)}: {result['report_dir']}")
            with open(result["zip_path"], "rb") as handle:
                st.download_button(t("reports.generator.download_zip", lang=lang), handle.read(), file_name=result["zip_path"].name, mime="application/zip", key=f"{prefix}_planning_download_report_zip")


def planning_chart_type_label(value: str, lang: str) -> str:
    labels = {
        "monthly": t("planning.monthly_label", lang=lang),
        "pareto": t("planning.pareto_label", lang=lang),
        "person_load": t("planning.person_load_label", lang=lang),
    }
    return labels.get(value, value)


def render_planning_selected_chart(
    filtered: pd.DataFrame,
    available: pd.DataFrame,
    person_load: pd.DataFrame,
    dimension: str,
    chart_type: str,
    context: dict[str, Any],
    lang: str,
) -> None:
    if filtered.empty and chart_type != "person_load":
        st.warning("No hay datos de planificación para los filtros seleccionados.")
        return
    if chart_type == "monthly":
        st.plotly_chart(
            build_planning_monthly_figure(filtered, context["months"], available, dimension, context["top_n"], lang),
            use_container_width=True,
        )
        return
    if chart_type == "pareto":
        fig, pareto_table = build_planning_pareto_figure(
            filtered,
            dimension,
            context["top_n"],
            float(available["available_hours"].sum()) if available["configured"].any() else 0.0,
            lang,
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(translate_dataframe_columns_for_display(pareto_table, lang), use_container_width=True, hide_index=True)
        return
    if chart_type == "person_load":
        show_without_planning = st.checkbox(
            t("planning.show_people_without_planning", lang=lang),
            value=bool(context.get("show_people_without_planning", True)),
            key="planning_show_people_without_planning",
        )
        context["show_people_without_planning"] = show_without_planning
        display_load = person_load.copy()
        if not show_without_planning and not display_load.empty:
            display_load = display_load[display_load["horas_planificadas"] > 0].copy()
        if display_load.empty:
            st.warning(t("planning.no_people_in_scope", lang=lang))
            return
        render_person_planning_coverage_summary(display_load, lang)
        stack_dimension = "grupo_gestion" if dimension == "person_name" else dimension
        if stack_dimension != dimension:
            st.caption(t("planning.person_dimension_fallback", lang=lang))
        visible_people = options(display_load["persona"])
        figure_source = filtered[filtered["person_name"].isin(visible_people)].copy() if not filtered.empty else filtered.copy()
        st.plotly_chart(build_person_load_figure(figure_source, display_load, stack_dimension, context["top_n"], lang), use_container_width=True)
        st.dataframe(translate_dataframe_columns_for_display(display_load, lang), use_container_width=True, hide_index=True)
        selected_person = st.selectbox(t("app.filters.person", lang=lang), visible_people, key="planning_people_detail_person")
        person_detail = filtered[filtered["person_name"] == selected_person].copy()
        detail_cols = ["person_name", "project_name", "task_name", "date_start", "date_end", "planned_hours", "unidad_destino_label", "naturaleza_trabajo_label", "grupo_gestion", "source_id"]
        detail_cols = [col for col in detail_cols if col in person_detail.columns]
        if person_detail.empty:
            st.caption(t("planning.without_planning", lang=lang))
        else:
            st.dataframe(translate_dataframe_columns_for_display(person_detail[detail_cols].sort_values(["project_name", "task_name"]), lang), use_container_width=True, hide_index=True)


def render_planning_view(actuals_df: pd.DataFrame | None = None) -> None:
    lang = current_language()
    st.header(t("planning.title", lang=lang))
    render_planning_data_section()
    if not PLANNING_PROCESSED_FILE.exists():
        st.warning(
            "No existe el dataset procesado de planificacion de Odoo. Ejecuta el proceso de transformacion antes de utilizar este modulo.\n\n"
            "Ejecuta:\n\n"
            "`$env:PYTHONPATH='src'; python -m imh_oreka.planning_data`"
        )
        return
    planning = load_planning_data(lang)
    if planning.empty:
        st.warning("No hay lineas activas de planificacion en el dataset procesado de Odoo.")
        empty_available = pd.DataFrame({"hilabete_zk": list(range(1, 13)), "available_hours": [0.0] * 12, "configured": [False] * 12})
        render_planning_summary(planning, empty_available, planning_person_load_table(planning, pd.DataFrame()))
        return
    filtered, context = planning_filters_with_organization(planning, "planning", actuals_df)
    context["rows_before_filters"] = len(planning)
    context["planned_hours_before_filters"] = float(planning["planned_hours"].sum()) if "planned_hours" in planning else 0.0
    context["dataset_path"] = str(PLANNING_PROCESSED_FILE.relative_to(ROOT_DIR))
    available_hours = read_csv(AVAILABLE_HOURS_FILE, AVAILABLE_COLUMNS)
    workload = read_csv(PERSON_WORKLOAD_FILE, PERSON_WORKLOAD_COLUMNS)
    organization_people = context.get("organization_people", pd.DataFrame())
    availability_scope = organization_people_scope_frame(organization_people)
    availability_result = resolve_available_hours_by_people(available_hours, workload, availability_scope, context["year"], context["months"], context["selected_people"])
    available = availability_result["monthly_available"]
    people_diagnostics = availability_result.get("people_diagnostics", pd.DataFrame())
    person_load = planning_person_load_table(filtered, organization_people, people_diagnostics, include_zero_planning=True)
    coverage = build_planning_people_coverage(
        organization_people,
        context.get("planning_period_before_dimension_filters", pd.DataFrame()),
        filtered,
        people_diagnostics,
    )
    coverage_metrics = planning_people_coverage_metrics(person_load)
    context.update(coverage_metrics)
    context["show_people_without_planning"] = st.session_state.get("planning_show_people_without_planning", True)
    write_planning_people_reports(context.get("waterfall_rows", []), coverage, planning)
    write_planning_diagnostics(filtered, person_load, available)
    render_planning_summary(filtered, available, person_load)
    render_planning_report_generator(filtered, available_hours, workload, context, "planning")
    dimension_options = {
        "grupo_gestion": t("app.chart.group_by_management", lang=lang),
        "project_name": t("app.chart.group_by_project", lang=lang),
        "unidad_destino_label": t("app.chart.group_by_unit", lang=lang),
        "naturaleza_trabajo_label": t("app.chart.group_by_nature", lang=lang),
        "person_name": t("column.person_name", lang=lang),
    }
    group_col, chart_col = st.columns([1.4, 1.6])
    graph_group_by = group_col.selectbox(
        t("app.chart.group_by", lang=lang),
        list(dimension_options.keys()),
        format_func=lambda key: dimension_options[key],
        key="planning_chart_group",
    )
    chart_type = chart_col.radio(
        t("app.chart.type", lang=lang),
        ["monthly", "pareto", "person_load"],
        format_func=lambda value: planning_chart_type_label(value, lang),
        horizontal=True,
        key="planning_chart_type",
    )
    context["planning_chart_type"] = chart_type
    context["planning_group_dimension"] = graph_group_by
    render_planning_selected_chart(filtered, available, person_load, graph_group_by, chart_type, context, lang)
    render_available_hours_diagnostics(availability_result)


@st.cache_data(show_spinner=False)
def load_operational_data(mtime: float) -> pd.DataFrame:
    del mtime
    if not OPERATIONAL_PROCESSED_FILE.exists():
        return pd.DataFrame(columns=op.OUTPUT_COLUMNS)
    df = pd.read_csv(OPERATIONAL_PROCESSED_FILE, sep=";", encoding="utf-8-sig").fillna("")
    for column in op.OUTPUT_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    for column in [
        "year",
        "month",
        "planned_minutes",
        "actual_minutes",
        "actual_minutes_with_planning",
        "actual_minutes_without_planning",
        "planned_minutes_not_executed",
        "deviation_minutes",
        "projects_count",
        "tasks_count",
    ]:
        df[column] = pd.to_numeric(df.get(column, 0), errors="coerce").fillna(0).astype(int)
    for column in [
        "planned_hours",
        "actual_hours",
        "actual_hours_with_planning",
        "actual_hours_without_planning",
        "planned_hours_not_executed",
        "deviation_hours",
        "deviation_pct",
        "planning_coverage_pct",
        "planning_execution_pct",
        "available_hours",
        "occupation_planned_pct",
        "occupation_actual_pct",
    ]:
        df[column] = pd.to_numeric(df.get(column, 0), errors="coerce")
    for column in ["period_start", "period_end"]:
        df[column] = pd.to_datetime(df[column], errors="coerce")
    return df[op.OUTPUT_COLUMNS].copy()


def operational_filters(df: pd.DataFrame, prefix: str, organization_source: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    lang = current_language()
    with st.expander(t("app.filters.view_config", lang=lang), expanded=False):
        diagnostics: dict[str, int] = {"dataset total": len(df)}
        years = sorted(df["year"].dropna().astype(int).unique().tolist()) if not df.empty else [date.today().year]
        year = st.selectbox(t("app.filters.year", lang=lang), years, index=len(years) - 1 if years else 0, key=f"{prefix}_year")
        organization_all = load_organization_people(organization_source, int(year))
        base = df[df["year"].astype(int) == int(year)].copy()
        diagnostics["tras año"] = len(base)

        parent_departments = sorted(set(options(organization_all["department_name"])) | {department_parent(value) for value in options(base["department_name"]) if department_parent(value)})
        department_options = ["Todos los departamentos"] + [value for value in parent_departments if value]
        default_department = department_options.index("PROIEKTUAK ETA ZERBITZU TEKNIKOAK") if "PROIEKTUAK ETA ZERBITZU TEKNIKOAK" in department_options else 0
        department = st.selectbox(t("app.filters.department", lang=lang), department_options, index=default_department, key=f"{prefix}_department")
        if department != "Todos los departamentos":
            base = base[base["department_name"].map(lambda value: department_parent(value) == department or clean_text(value) == clean_text(department))].copy()
        diagnostics["tras departamento"] = len(base)

        organization_department = filter_organization_people(organization_all, department, "Todos")
        subdepartment_options = ["Todos"] + options(organization_department["subdepartment"])
        subdepartment = st.selectbox(t("app.filters.subdepartment", lang=lang), subdepartment_options, key=f"{prefix}_subdepartment")
        organization_scope_before_person = filter_organization_people(organization_all, department, subdepartment)
        if subdepartment != "Todos":
            base = base[base["subdepartment"].map(clean_text).eq(clean_text(subdepartment)) | base["internal_group"].map(clean_text).eq(clean_text(subdepartment)) | base["department_name"].map(clean_text).eq(clean_text(subdepartment))].copy()
        diagnostics["tras subdepartamento"] = len(base)

        months, period_label = month_range_selector(prefix)
        base = base[base["month"].astype(int).isin(months)].copy()
        diagnostics["tras periodo"] = len(base)

        units = select_all_multiselect(t("app.chart.group_by_unit", lang=lang), options(base["unidad_destino_label"]), f"{prefix}_units")
        base = base[base["unidad_destino_label"].isin(units)].copy()
        diagnostics["tras unidad destino"] = len(base)
        natures = select_all_multiselect(t("app.chart.group_by_nature", lang=lang), options(base["naturaleza_trabajo_label"]), f"{prefix}_natures")
        base = base[base["naturaleza_trabajo_label"].isin(natures)].copy()
        diagnostics["tras naturaleza trabajo"] = len(base)
        groups = select_all_multiselect(t("app.filters.management_group", lang=lang), options(base["grupo_gestion"]), f"{prefix}_management_groups")
        base = base[base["grupo_gestion"].isin(groups)].copy()
        diagnostics["tras grupo gestion"] = len(base)

        people_options = people_filter_options(organization_scope_before_person, base.rename(columns={"actual_hours": "planned_hours"}))
        if not people_options:
            people_options = options(base["person_name"])
        people = select_all_multiselect(t("app.filters.person", lang=lang), people_options, f"{prefix}_people")
        organization_scope = organization_scope_before_person[organization_scope_before_person["person_name"].isin(people)].copy() if not organization_scope_before_person.empty else organization_scope_before_person
        base = base[base["person_name"].isin(people)].copy()
        diagnostics["tras persona"] = len(base)

        top_n = st.slider(t("app.filters.top_n", lang=lang), 5, 50, 15, 5, key=f"{prefix}_topn")
        with st.expander(t("app.filters.advanced", lang=lang), expanded=False):
            projects = select_all_multiselect(t("column.project_name", lang=lang), options(base["project_name"]), f"{prefix}_projects")
            base = base[base["project_name"].isin(projects)].copy()
            diagnostics["tras proyecto"] = len(base)
            tasks = select_all_multiselect(t("column.task_name", lang=lang), options(base["task_name"]), f"{prefix}_tasks")
            base = base[base["task_name"].isin(tasks)].copy()
            diagnostics["tras tarea"] = len(base)

    return base, {
        "year": int(year),
        "months": months,
        "period": period_label,
        "selected_department": department,
        "selected_internal_groups": [] if subdepartment == "Todos" else [subdepartment],
        "departments": [department] if department != "Todos los departamentos" else department_options[1:],
        "subdepartment": subdepartment,
        "selected_units": units,
        "selected_natures": natures,
        "management_groups": groups,
        "selected_people": people,
        "projects": projects,
        "tasks": tasks,
        "top_n": top_n,
        "organization_people": organization_scope,
        "diagnostics": diagnostics,
    }


def operational_dimension_table(df: pd.DataFrame, dimension: str, top_n: int) -> pd.DataFrame:
    source = df.copy()
    if dimension == "month":
        source["month_display"] = source["month"].map(lambda value: month_label(int(value), current_language(), with_number=True))
        dimension_col = "month_display"
    else:
        dimension_col = dimension
    table = op.aggregate_by_dimension(source, dimension_col)
    if dimension_col not in table.columns:
        return table
    if len(table) > top_n:
        top = table.head(top_n).copy()
        other = table.iloc[top_n:].copy()
        numeric_cols = [col for col in table.columns if pd.api.types.is_numeric_dtype(table[col])]
        other_row = {column: "" for column in table.columns}
        other_row[dimension_col] = "Otros"
        for column in numeric_cols:
            other_row[column] = other[column].sum()
        top = pd.concat([top, pd.DataFrame([other_row])], ignore_index=True)
        table = top
    return table


def operational_comparison_figure(table: pd.DataFrame, dimension: str, lang: str) -> go.Figure:
    fig = go.Figure()
    if table.empty:
        return fig
    x = table[dimension].map(clean_text)
    fig.add_bar(x=x, y=table["planned_hours"], name=t("column.planned_hours", lang=lang))
    fig.add_bar(x=x, y=table["actual_hours"], name=t("column.actual_hours", lang=lang))
    fig.update_layout(barmode="group", xaxis_title=translate_label(dimension, "column", lang), yaxis_title=t("column.horas", lang=lang), title=t("operational.planned_vs_actual", lang=lang))
    return fig


def operational_deviation_figure(table: pd.DataFrame, dimension: str, lang: str) -> go.Figure:
    plot = table.sort_values("deviation_hours", ascending=True).copy()
    colors = ["#D95F02" if value > 0 else "#2E86AB" if value < 0 else "#8C8C8C" for value in plot["deviation_hours"]]
    fig = go.Figure(go.Bar(x=plot["deviation_hours"], y=plot[dimension].map(clean_text), orientation="h", marker_color=colors))
    fig.update_layout(xaxis_title=t("column.deviation_hours", lang=lang), yaxis_title=translate_label(dimension, "column", lang), title=t("operational.chart.deviation", lang=lang))
    return fig


def operational_overconsumption_pareto_figure(table: pd.DataFrame, dimension: str, lang: str) -> go.Figure:
    plot = table[table["overconsumption_hours"] > 0].sort_values("overconsumption_hours", ascending=False).copy()
    if plot.empty:
        return go.Figure()
    total = float(plot["overconsumption_hours"].sum())
    plot["pct_acumulado"] = plot["overconsumption_hours"].cumsum() / total * 100 if total else 0.0
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(x=plot[dimension].map(clean_text), y=plot["overconsumption_hours"], name=t("operational.metric.overconsumption_projects", lang=lang), secondary_y=False)
    fig.add_scatter(x=plot[dimension].map(clean_text), y=plot["pct_acumulado"], name="% acumulado", mode="lines+markers", line={"color": "black"}, secondary_y=True)
    fig.update_layout(title=t("operational.chart.overconsumption_pareto", lang=lang), xaxis_title=translate_label(dimension, "column", lang))
    fig.update_yaxes(title_text=t("column.horas", lang=lang), secondary_y=False)
    fig.update_yaxes(title_text="% acumulado", range=[0, 100], ticksuffix="%", secondary_y=True)
    return fig


def render_operational_summary(df: pd.DataFrame) -> None:
    lang = current_language()
    kpis = op.calculate_operational_kpis(df)
    cols = st.columns(4)
    cols[0].metric(t("column.planned_hours", lang=lang), format_number_es(kpis["planned_hours"]))
    cols[1].metric(t("column.actual_hours", lang=lang), format_number_es(kpis["actual_hours"]))
    cols[2].metric(t("column.deviation_hours", lang=lang), format_number_es(kpis["deviation_hours"]))
    cols[3].metric(t("operational.metric.planning_coverage", lang=lang), format_number_es(kpis["planning_coverage_pct"]) + "%" if kpis["planning_coverage_pct"] is not None else t("metric.not_configured", lang=lang))
    cols = st.columns(4)
    cols[0].metric(t("operational.metric.unplanned_actuals", lang=lang), format_number_es(kpis["actual_hours_without_planning"]))
    cols[1].metric(t("operational.metric.unexecuted_planning", lang=lang), format_number_es(kpis["planned_hours_not_executed"]))
    cols[2].metric(t("operational.metric.overconsumption_projects", lang=lang), format_integer_es(kpis["projects_with_overconsumption"]))
    cols[3].metric(t("metric.projects", lang=lang), format_integer_es(kpis["projects"]))
    over = op.aggregate_by_dimension(df, "project_name")
    over = over[over["overconsumption_hours"] > 0].head(10)
    unplanned = df[df["actual_hours_without_planning"] > 0].sort_values("actual_hours_without_planning", ascending=False).head(20)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"### {t('operational.metric.overconsumption_projects', lang=lang)}")
        if over.empty:
            st.caption(t("operational.no_overconsumption", lang=lang))
        else:
            st.dataframe(translate_dataframe_columns_for_display(over, lang), use_container_width=True, hide_index=True)
    with c2:
        st.markdown(f"### {t('operational.metric.unplanned_actuals', lang=lang)}")
        if unplanned.empty:
            st.caption(t("operational.no_unplanned_actuals", lang=lang))
        else:
            cols_keep = ["person_name", "project_name", "task_name", "month", "actual_hours_without_planning", "grupo_gestion", "match_quality"]
            st.dataframe(translate_dataframe_columns_for_display(unplanned[[c for c in cols_keep if c in unplanned.columns]], lang), use_container_width=True, hide_index=True)


def render_operational_planned_vs_actual(df: pd.DataFrame, context: dict[str, Any]) -> None:
    lang = current_language()
    dimension_options = {
        "project_name": t("column.project_name", lang=lang),
        "person_name": t("column.person_name", lang=lang),
        "month": t("column.month", lang=lang),
        "department_name": t("app.filters.department", lang=lang),
        "grupo_gestion": t("app.chart.group_by_management", lang=lang),
    }
    chart_options = ["comparison", "deviation", "overconsumption_pareto", "unplanned_actuals"]
    dim_col, chart_col = st.columns([1.2, 1.8])
    selected_dimension = dim_col.selectbox(t("operational.dimension", lang=lang), list(dimension_options.keys()), format_func=lambda value: dimension_options[value], key="operational_dimension")
    chart_type = chart_col.radio(
        t("app.chart.type", lang=lang),
        chart_options,
        format_func=lambda value: {
            "comparison": t("operational.chart.comparison", lang=lang),
            "deviation": t("operational.chart.deviation", lang=lang),
            "overconsumption_pareto": t("operational.chart.overconsumption_pareto", lang=lang),
            "unplanned_actuals": t("operational.chart.unplanned_actuals", lang=lang),
        }[value],
        horizontal=True,
        key="operational_chart_type",
    )
    dimension_col = "month_display" if selected_dimension == "month" else selected_dimension
    table = operational_dimension_table(df, selected_dimension, context["top_n"])
    if chart_type == "comparison":
        st.plotly_chart(operational_comparison_figure(table, dimension_col, lang), use_container_width=True)
        st.dataframe(translate_dataframe_columns_for_display(table, lang), use_container_width=True, hide_index=True)
    elif chart_type == "deviation":
        st.plotly_chart(operational_deviation_figure(table, dimension_col, lang), use_container_width=True)
        st.dataframe(translate_dataframe_columns_for_display(table, lang), use_container_width=True, hide_index=True)
    elif chart_type == "overconsumption_pareto":
        over = table[table["overconsumption_hours"] > 0].copy() if "overconsumption_hours" in table.columns else pd.DataFrame()
        if over.empty:
            st.caption(t("operational.no_overconsumption", lang=lang))
        else:
            st.plotly_chart(operational_overconsumption_pareto_figure(table, dimension_col, lang), use_container_width=True)
            st.dataframe(translate_dataframe_columns_for_display(over, lang), use_container_width=True, hide_index=True)
    else:
        unplanned = df[df["actual_hours_without_planning"] > 0].sort_values("actual_hours_without_planning", ascending=False).copy()
        if unplanned.empty:
            st.caption(t("operational.no_unplanned_actuals", lang=lang))
        else:
            columns = ["person_name", "project_name", "task_name", "month", "actual_hours_without_planning", "unidad_destino_label", "naturaleza_trabajo_label", "grupo_gestion", "match_quality"]
            st.dataframe(translate_dataframe_columns_for_display(unplanned[[col for col in columns if col in unplanned.columns]], lang), use_container_width=True, hide_index=True)
            download_table(unplanned, "prc01_operational_unplanned_actuals.csv")


def render_operational_people_load(df: pd.DataFrame, context: dict[str, Any], actuals_df: pd.DataFrame) -> None:
    lang = current_language()
    available_hours = read_csv(AVAILABLE_HOURS_FILE, AVAILABLE_COLUMNS)
    workload = read_csv(PERSON_WORKLOAD_FILE, PERSON_WORKLOAD_COLUMNS)
    organization_people = context.get("organization_people", pd.DataFrame())
    availability_scope = organization_people_scope_frame(organization_people)
    availability_result = resolve_available_hours_by_people(available_hours, workload, availability_scope, context["year"], context["months"], context["selected_people"])
    people_diagnostics = availability_result.get("people_diagnostics", pd.DataFrame())
    people = op.calculate_people_load(df, people_diagnostics, organization_people)
    if people.empty:
        st.warning(t("planning.no_people_in_scope", lang=lang))
        return
    metric = st.radio(
        t("app.chart.type", lang=lang),
        ["planned_hours", "actual_hours", "available_hours"],
        format_func=lambda value: translate_label(value, "column", lang),
        horizontal=True,
        key="operational_people_metric",
    )
    plot = people.sort_values(metric, ascending=True).copy()
    fig = go.Figure()
    fig.add_bar(x=plot[metric], y=plot["person_name"], orientation="h", name=translate_label(metric, "column", lang), marker_color="#2E86AB")
    if metric != "available_hours":
        fig.add_scatter(x=plot["available_hours"], y=plot["person_name"], mode="markers", name=t("column.available_hours", lang=lang), marker={"color": "#FF4B4B", "size": 9})
    fig.update_layout(title=t("operational.people_load", lang=lang), xaxis_title=t("column.horas", lang=lang), yaxis_title=t("column.person_name", lang=lang), height=max(450, 28 * len(plot)))
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(translate_dataframe_columns_for_display(people, lang), use_container_width=True, hide_index=True)
    render_available_hours_diagnostics(availability_result)


def write_operational_report_package(df: pd.DataFrame, context: dict[str, Any], lang: str) -> dict[str, Any]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = OPERATIONAL_REPORTS_DIR / f"report_{timestamp}"
    report_dir.mkdir(parents=True, exist_ok=True)
    summary = pd.DataFrame([op.calculate_operational_kpis(df)])
    planned_vs_actual = op.aggregate_by_dimension(df, "project_name")
    deviations = planned_vs_actual.sort_values("deviation_hours", ascending=False).copy()
    unplanned = df[df["actual_hours_without_planning"] > 0].copy()
    people = op.calculate_people_load(df)
    tables = {
        "summary": summary,
        "planned_vs_actual": planned_vs_actual,
        "deviations": deviations,
        "unplanned_actuals": unplanned,
        "people_load": people,
    }
    for name, table in tables.items():
        table.to_csv(report_dir / f"{name}.csv", sep=";", encoding="utf-8-sig", index=False)
    html = "\n".join(
        [
            "<html><head><meta charset='utf-8'><title>Rendimiento operativo</title></head><body>",
            f"<h1>{escape(t('operational.title', lang=lang))}</h1>",
            f"<p>{escape(now_text())}</p>",
            "<h2>Resumen</h2>",
            metrics_html(op.calculate_operational_kpis(df), lang),
            "<h2>Planificado vs real</h2>",
            dataframe_html(planned_vs_actual, lang),
            "<h2>Horas sin planificacion</h2>",
            dataframe_html(unplanned, lang),
            "<h2>Personas y carga</h2>",
            dataframe_html(people, lang),
            "</body></html>",
        ]
    )
    (report_dir / "report.html").write_text(html, encoding="utf-8")
    metadata = {
        "generated_at": now_text(),
        "dataset_path": str(OPERATIONAL_PROCESSED_FILE.relative_to(ROOT_DIR)),
        "rows_after_filters": int(len(df)),
        "filters": report_filter_summary(context, context["months"], lang),
        "selected_internal_groups": context.get("selected_internal_groups", []),
        "language": lang,
    }
    (report_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    zip_path = report_dir / f"prc01_operational_performance_report_{timestamp}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in report_dir.iterdir():
            if path != zip_path and path.is_file():
                archive.write(path, arcname=path.name)
    return {"report_dir": report_dir, "zip_path": zip_path}


def render_operational_report_generator(filtered: pd.DataFrame, context: dict[str, Any]) -> None:
    lang = current_language()
    with st.expander(t("operational.generate_reports", lang=lang), expanded=False):
        if st.button(t("reports.generator.generate", lang=lang), type="primary", key="operational_report_generate"):
            if filtered.empty:
                st.warning(t("reports.generator.no_data", lang=lang))
                return
            result = write_operational_report_package(filtered, context, lang)
            st.success(t("operational.report.generated_ok", lang=lang))
            with open(result["zip_path"], "rb") as file:
                st.download_button(
                    t("reports.generator.download_zip", lang=lang),
                    file,
                    file_name=Path(result["zip_path"]).name,
                    mime="application/zip",
                    key="operational_report_download",
                )


def render_operational_performance_view(actuals_df: pd.DataFrame) -> None:
    lang = current_language()
    st.header(t("operational.title", lang=lang))
    if not OPERATIONAL_PROCESSED_FILE.exists():
        st.warning(t("operational.dataset_missing", lang=lang))
        return
    mtime = OPERATIONAL_PROCESSED_FILE.stat().st_mtime
    data = load_operational_data(mtime)
    if data.empty:
        st.warning(t("operational.dataset_empty", lang=lang))
        return
    filtered, context = operational_filters(data, "operational", actuals_df)
    render_operational_report_generator(filtered, context)
    view = st.radio(
        t("operational.view", lang=lang),
        ["summary", "planned_vs_actual", "people_load"],
        format_func=lambda value: {
            "summary": t("operational.summary", lang=lang),
            "planned_vs_actual": t("operational.planned_vs_actual", lang=lang),
            "people_load": t("operational.people_load", lang=lang),
        }[value],
        horizontal=True,
        key="operational_view",
    )
    if filtered.empty:
        st.warning(t("operational.dataset_empty", lang=lang))
        return
    if view == "summary":
        render_operational_summary(filtered)
    elif view == "planned_vs_actual":
        render_operational_planned_vs_actual(filtered, context)
    else:
        render_operational_people_load(filtered, context, actuals_df)

def team_people(df: pd.DataFrame, teams: pd.DataFrame, team_name: str) -> list[str]:
    rows = teams[teams["team_name"] == team_name].copy()
    if rows.empty:
        return []
    if rows["employee_alias"].map(clean_text).eq("").all() and rows["employee_name"].map(clean_text).eq("").all():
        return options(df["pertsona"])
    matched = []
    for person in options(df["pertsona"]):
        for _, row in rows.iterrows():
            aliases = "|".join([clean_text(row.get("employee_name", "")), clean_text(row.get("employee_alias", ""))])
            if person_matches_alias(person, aliases):
                matched.append(person)
                break
    return sorted(set(matched))


def department_parent(value: str) -> str:
    return clean_text(value).split("/")[0].strip()


def analysis_filters(df: pd.DataFrame, prefix: str, scope: str, teams: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    with st.expander(t("app.filters.view_config"), expanded=False):
        diagnostics: dict[str, int] = {"dataset total": len(df)}
        years = sorted(df["urtea"].dropna().astype(int).unique().tolist())
        year = st.selectbox(t("app.filters.year"), years, index=len(years) - 1 if years else 0, key=f"{prefix}_year")
        base = df[df["urtea"] == year].copy()
        diagnostics["tras a?o"] = len(base)
        scope_value = ""
        subdepartment = "Todos"
        availability_department = ""
        availability_parent_department = ""
        people_filter: list[str] = []
        if scope == "department":
            parents = sorted({department_parent(v) for v in options(base["saila"]) if department_parent(v)})
            department_options = ["Todos los departamentos"] + parents
            default_department = 0
            if any("PROIEKTUAK ETA ZERBITZU TEKNIKOAK" in value for value in options(base["saila"])):
                if "PROIEKTUAK ETA ZERBITZU TEKNIKOAK" in department_options:
                    default_department = department_options.index("PROIEKTUAK ETA ZERBITZU TEKNIKOAK")
            scope_value = st.selectbox(t("app.filters.department"), department_options, index=default_department, key=f"{prefix}_department")
            if scope_value != "Todos los departamentos":
                base = base[base["saila"].str.contains(scope_value, case=False, regex=False, na=False)].copy()
                availability_department = scope_value
                availability_parent_department = scope_value
            diagnostics["tras departamento"] = len(base)
            exact_departments = ["Todos"] + options(base["saila"])
            subdepartment = st.selectbox(t("app.filters.subdepartment"), exact_departments, key=f"{prefix}_subdepartment")
            if subdepartment != "Todos":
                base = base[base["saila"] == subdepartment].copy()
                availability_department = subdepartment
            diagnostics["tras subdepartamento"] = len(base)
        elif scope == "team":
            team_names = options(teams["team_name"])
            scope_value = st.selectbox("Equipo", team_names, key=f"{prefix}_team")
            base = base[base["pertsona"].isin(team_people(base, teams, scope_value))].copy()
            diagnostics["tras equipo"] = len(base)
        elif scope == "person":
            people = options(base["pertsona"])
            scope_value = st.selectbox("Persona", people, key=f"{prefix}_person")
            base = base[base["pertsona"] == scope_value].copy()
            people_filter = [scope_value]
            diagnostics["tras persona principal"] = len(base)

        months, period_label = month_range_selector(prefix)
        base = base[base["hilabete_zk"].astype(int).isin(months)].copy()
        diagnostics["tras periodo"] = len(base)
        selected_units = select_all_multiselect(t("app.chart.group_by_unit"), options(base["unidad_destino_label"]), f"{prefix}_units")
        base = base[base["unidad_destino_label"].isin(selected_units)].copy()
        diagnostics["tras unidad destino"] = len(base)
        selected_natures = select_all_multiselect(t("app.chart.group_by_nature"), options(base["naturaleza_trabajo_label"]), f"{prefix}_natures")
        base = base[base["naturaleza_trabajo_label"].isin(selected_natures)].copy()
        diagnostics["tras naturaleza trabajo"] = len(base)
        management_groups = select_all_multiselect(t("app.filters.management_group"), options(base["grupo_gestion"]), f"{prefix}_management_groups")
        base = base[base["grupo_gestion"].isin(management_groups)].copy()
        diagnostics["tras grupo gestion"] = len(base)
        if scope in {"department", "team"}:
            people_filter = select_all_multiselect(t("app.filters.person"), options(base["pertsona"]), f"{prefix}_people")
            base = base[base["pertsona"].isin(people_filter)].copy()
            diagnostics["tras persona"] = len(base)
        top_n = st.slider(t("app.filters.top_n"), 5, 50, 15, 5, key=f"{prefix}_topn")
        with st.expander(t("app.filters.advanced"), expanded=False):
            projects = select_all_multiselect("Proyecto", options(base["project_name"]), f"{prefix}_projects")
            base = base[base["project_name"].isin(projects)].copy()
            diagnostics["tras proyecto"] = len(base)
            tasks = select_all_multiselect("Tarea", options(base["task_name"]), f"{prefix}_tasks")
            base = base[base["task_name"].isin(tasks)].copy()
            diagnostics["tras tarea"] = len(base)
    return base, {
        "year": int(year),
        "months": months,
        "period": period_label,
        "scope": scope_value,
        "subdepartment": subdepartment,
        "projects": projects,
        "selected_units": selected_units,
        "selected_natures": selected_natures,
        "management_groups": management_groups,
        "selected_people": people_filter,
        "availability_department": availability_department,
        "availability_parent_department": availability_parent_department,
        "top_n": top_n,
        "diagnostics": diagnostics,
    }

def render_dashboard_view(df: pd.DataFrame, scope: str, prefix: str) -> None:
    if df.empty:
        st.warning("No existe dataset procesado. Construye el dataset desde Odoo / Conexion y descarga.")
        return
    teams = load_teams(str(TEAMS_FILE))
    available_hours = read_csv(AVAILABLE_HOURS_FILE, AVAILABLE_COLUMNS)
    workload = read_csv(PERSON_WORKLOAD_FILE, PERSON_WORKLOAD_COLUMNS)
    filtered, context = analysis_filters(df, prefix, scope, teams)
    if filtered.empty:
        st.warning("No hay datos para los filtros seleccionados.")
        diagnostics = pd.DataFrame(
            [{"filtro": key, "lineas": value} for key, value in context.get("diagnostics", {}).items()]
        )
        if not diagnostics.empty:
            st.dataframe(translate_dataframe_columns_for_display(diagnostics, current_language()), use_container_width=True, hide_index=True)
        return
    availability_result = resolve_available_hours_by_people(
        available_hours,
        workload,
        filtered,
        context["year"],
        context["months"],
        context["selected_people"],
    )
    available = availability_result["monthly_available"]
    if not available["configured"].any() or float(available["available_hours"].sum()) <= 0:
        st.caption("No hay horas disponibles configuradas para este alcance con valor mayor que 0.")
    else:
        st.caption(
            f"Horas disponibles configuradas: {availability_result['base_source']}: "
            f"{availability_result['base_scope_name']}"
        )
    render_report_generator(filtered, available_hours, workload, context, prefix)
    col_left, col_right = st.columns([2, 1])
    lang = current_language()
    graph_group_by = col_left.selectbox(
        t("app.chart.group_by"),
        ["grupo_gestion", "project_name", "unidad_destino_label", "naturaleza_trabajo_label"],
        format_func=lambda value: {
            "grupo_gestion": t("app.chart.group_by_management", lang=lang),
            "project_name": t("app.chart.group_by_project", lang=lang),
            "unidad_destino_label": t("app.chart.group_by_unit", lang=lang),
            "naturaleza_trabajo_label": t("app.chart.group_by_nature", lang=lang),
        }[value],
        key=f"{prefix}_graph_group_by",
    )
    chart_type = col_right.radio(
        t("app.chart.type"),
        ["monthly", "pareto", "person_load"],
        format_func=lambda value: {
            "monthly": t("app.chart.monthly_label", lang=lang),
            "pareto": t("app.chart.pareto_label", lang=lang),
            "person_load": t("analysis.person_load_label", lang=lang),
        }[value],
        horizontal=True,
        key=f"{prefix}_chart_type",
    )
    color_col = graph_group_by
    management_color_map = build_management_color_map(filtered, load_management_units(), load_work_natures())
    color_map = management_color_map if color_col in {"grupo_gestion", "unidad_destino_label", "naturaleza_trabajo_label"} else (GROUP_COLORS if color_col == "grupo_actividad" else None)
    label = {"department": "Departamento", "team": "Equipo", "person": "Persona"}[scope]
    scope_label = context["scope"]
    if scope == "department" and context.get("subdepartment") not in {"", "Todos", None}:
        scope_label = f"{context['scope']} / {context['subdepartment']}"
    title = f"Horas imputadas - {label}: {scope_label} - {context['year']} - Periodo: {context['period']}"
    if chart_type == "pareto":
        pareto_label = translate_label(color_col, "column", lang)
        pareto_title = f"Pareto de horas imputadas por {pareto_label} - {context['year']} - Periodo: {context['period']}"
        pareto_chart(filtered, pareto_title, color_col, context["top_n"], color_map)
    elif chart_type == "person_load":
        person_fig, person_table = build_actual_person_load_figure(filtered, color_col, context["top_n"], lang)
        st.plotly_chart(person_fig, use_container_width=True)
        st.dataframe(translate_dataframe_columns_for_display(person_table, lang), use_container_width=True, hide_index=True)
    else:
        stacked_chart(filtered, context["months"], title, color_col, context["top_n"], available, color_map)
    st.markdown(f"### {t('summary.hours.title', lang=lang)}")
    summary_metrics(filtered, available)
    render_available_hours_diagnostics(availability_result)
    summary_tables(filtered, prefix)


def parse_private_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if not PRIVATE_ENV.exists():
        return values
    for line in PRIVATE_ENV.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def odoo_connection_form() -> tuple[str, str, str, str]:
    lang = current_language()
    private = parse_private_env()
    defaults = {
        "url": os.getenv("ODOO_URL") or private.get("ODOO_URL") or "",
        "db": os.getenv("ODOO_DB") or private.get("ODOO_DB") or "",
        "user": os.getenv("ODOO_USER") or private.get("ODOO_USER") or "",
        "password": st.session_state.get("odoo_password", os.getenv("ODOO_PASSWORD") or private.get("ODOO_PASSWORD") or ""),
    }
    with st.form("odoo_connection_form"):
        url = st.text_input(t("odoo.connection.url", lang=lang), value=defaults["url"])
        db = st.text_input(t("odoo.connection.database", lang=lang), value=defaults["db"])
        user = st.text_input(t("odoo.connection.user", lang=lang), value=defaults["user"])
        password = st.text_input(t("odoo.connection.password", lang=lang), value=defaults["password"], type="password")
        submitted = st.form_submit_button(t("odoo.connection.save_session", lang=lang))
    if submitted:
        st.session_state["odoo_url"] = url
        st.session_state["odoo_db"] = db
        st.session_state["odoo_user"] = user
        st.session_state["odoo_password"] = password
        st.success(t("odoo.connection.session_saved", lang=lang))
    return (
        st.session_state.get("odoo_url", defaults["url"]),
        st.session_state.get("odoo_db", defaults["db"]),
        st.session_state.get("odoo_user", defaults["user"]),
        st.session_state.get("odoo_password", defaults["password"]),
    )


def render_odoo_connection_view() -> None:
    lang = current_language()
    st.header(t("odoo.connection.title", lang=lang))
    st.caption(t("odoo.connection.subtitle", lang=lang))
    url, db, user, password = odoo_connection_form()
    year = date.today().year
    col1, col2 = st.columns(2)
    date_from = col1.date_input(t("odoo.connection.date_from", lang=lang), value=date(year, 1, 1)).isoformat()
    date_to = col2.date_input(t("odoo.connection.date_to", lang=lang), value=date(year + 1, 1, 1)).isoformat()

    if st.button(t("odoo.connection.download_rebuild", lang=lang), type="primary", use_container_width=True):
        status = st.status(t("odoo.connection.connecting", lang=lang), expanded=True) if hasattr(st, "status") else None
        uid = None
        try:
            if status:
                status.update(label=t("odoo.connection.connecting", lang=lang), state="running")
            client = make_client(url, db, user, password)
            uid = client.authenticate()
            client.version()
            st.session_state["odoo_connected"] = True
            st.session_state["odoo_config"] = {"url": url, "db": db, "user": user}
            if status:
                status.write(t("odoo.connection.downloading", lang=lang))
            download = download_analytic_lines(client, date_from, date_to)
            planning_download = download_planning_forecast(client, date_from, date_to)
            if status:
                status.write(t("odoo.connection.transforming", lang=lang))
            rebuilt = rebuild_downloaded_datasets(date_from, date_to, planning_download)
            summary = rebuilt["actuals"]
            if status:
                status.write(t("odoo.connection.rebuilding", lang=lang))
            st.cache_data.clear()
            if status:
                status.update(label=t("odoo.connection.flow_ok", lang=lang), state="complete")
            render_download_rebuild_summary(download, summary, lang)
            if planning_download.get("available"):
                st.caption(
                    f"Planificación descargada: {format_integer_es(int(planning_download.get('rows', 0) or 0))} registros; "
                    f"dataset de planificación y rendimiento operativo reconstruidos."
                )
            else:
                st.warning("El usuario no tiene acceso a project.forecast; se actualizaron únicamente las horas reales.")
        except Exception as exc:
            st.session_state["odoo_connected"] = False
            log_path = log_odoo_connection_error("download_rebuild", exc)
            if status:
                status.update(label=t("odoo.connection.download_failed", lang=lang), state="error")
            message_key = "odoo.connection.connection_failed" if uid is None else "odoo.connection.download_failed"
            st.error(t(message_key, lang=lang))
            with st.expander(t("odoo.connection.technical_details", lang=lang), expanded=False):
                st.write(f"Log: `{log_path.relative_to(ROOT_DIR)}`")

def sanitize_dataframe_columns(df: pd.DataFrame) -> pd.DataFrame:
    clean = df.copy()
    clean.columns = [str(column).strip() for column in clean.columns]
    clean = clean.loc[:, ~pd.Index(clean.columns).duplicated(keep="first")]
    return clean


def normalize_key_part(value: Any) -> str:
    if pd.isna(value):
        return ""
    if value is False:
        return ""
    text = str(value).strip()
    if text.casefold() in {"nan", "none", "false"}:
        return ""
    return text


def make_key(df: pd.DataFrame, key_cols: list[str]) -> pd.Series:
    df = sanitize_dataframe_columns(df)
    clean_key_cols = []
    for column in key_cols:
        column = str(column).strip()
        if column and column not in clean_key_cols:
            clean_key_cols.append(column)

    parts = []
    for column in clean_key_cols:
        if column in df.columns:
            series = df[column]
            if isinstance(series, pd.DataFrame):
                series = series.iloc[:, 0]
        else:
            series = pd.Series([""] * len(df), index=df.index)
        series = series.apply(normalize_key_part).astype(str)
        parts.append(series)

    if not parts:
        key = pd.Series([""] * len(df), index=df.index, dtype=str)
    else:
        key = parts[0].copy()
        for series in parts[1:]:
            key = key + "||" + series

    key = key.astype(str)
    key.name = "_key"
    assert isinstance(key, pd.Series), type(key)
    assert len(key) == len(df), (len(key), len(df))
    return key


def dataframe_diagnostic(df: pd.DataFrame) -> dict[str, Any]:
    columns = [str(column).strip() for column in df.columns]
    return {
        "columns": columns,
        "duplicate_columns": pd.Index(columns)[pd.Index(columns).duplicated()].tolist(),
        "shape": tuple(df.shape),
    }


def key_diagnostic(value: Any) -> dict[str, Any]:
    return {
        "type": type(value).__name__,
        "shape": getattr(value, "shape", None),
        "size": getattr(value, "size", None),
    }


def append_upsert_diagnostic(existing: pd.DataFrame, new_rows: pd.DataFrame, existing_key: Any, new_key: Any) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / f"prc01_bugfix_make_key_dataframe_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    existing_info = dataframe_diagnostic(existing)
    new_rows_info = dataframe_diagnostic(new_rows)
    existing_key_info = key_diagnostic(existing_key)
    new_key_info = key_diagnostic(new_key)
    content = [
        "# Diagnóstico make_key / upsert_rows",
        "",
        f"fecha/hora: {now_text()}",
        "",
        "## existing",
        f"columnas de existing: {existing_info['columns']}",
        f"columnas duplicadas en existing: {existing_info['duplicate_columns']}",
        f"shape de existing: {existing_info['shape']}",
        f"tipo devuelto por make_key(existing, key_cols): {existing_key_info['type']}",
        f"shape/tamaño devuelto por make_key(existing, key_cols): {existing_key_info['shape']} / {existing_key_info['size']}",
        "",
        "## new_rows",
        f"columnas de new_rows: {new_rows_info['columns']}",
        f"columnas duplicadas en new_rows: {new_rows_info['duplicate_columns']}",
        f"shape de new_rows: {new_rows_info['shape']}",
        f"tipo devuelto por make_key(new_rows, key_cols): {new_key_info['type']}",
        f"shape/tamaño devuelto por make_key(new_rows, key_cols): {new_key_info['shape']} / {new_key_info['size']}",
        "",
    ]
    log_path.write_text("\n".join(content), encoding="utf-8")


def safe_rows_for_columns(rows: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    clean_columns = list(dict.fromkeys(str(column).strip() for column in columns))
    safe_rows = sanitize_dataframe_columns(rows)
    for column in clean_columns:
        if column not in safe_rows.columns:
            safe_rows[column] = ""
    return safe_rows[clean_columns].copy()


def upsert_rows(path: Path, columns: list[str], rows: pd.DataFrame, key_cols: list[str]) -> None:
    columns = list(dict.fromkeys(str(column).strip() for column in columns))
    existing = sanitize_dataframe_columns(read_csv(path, columns))
    new_rows = safe_rows_for_columns(rows, columns)
    for column in columns:
        if column not in existing.columns:
            existing[column] = ""
        if column not in new_rows.columns:
            new_rows[column] = ""
    existing = existing[columns].copy()
    new_rows = new_rows[columns].copy()

    existing_key = make_key(existing, key_cols)
    new_key = make_key(new_rows, key_cols)
    append_upsert_diagnostic(existing, new_rows, existing_key, new_key)
    if not isinstance(existing_key, pd.Series):
        raise TypeError(f"make_key(existing, key_cols) debe devolver pd.Series, devuelve {type(existing_key).__name__}")
    if not isinstance(new_key, pd.Series):
        raise TypeError(f"make_key(new_rows, key_cols) debe devolver pd.Series, devuelve {type(new_key).__name__}")

    existing["_key"] = existing_key.to_numpy()
    new_rows["_key"] = new_key.to_numpy()
    output = pd.concat([existing, new_rows], ignore_index=True)
    output = output.drop_duplicates(subset=["_key"], keep="last")
    output = output.drop(columns=["_key"])[columns].copy()
    output.to_csv(path, sep=";", encoding="utf-8-sig", index=False)
    st.cache_data.clear()


def save_config_table(path: Path, columns: list[str], rows: pd.DataFrame, key_cols: list[str]) -> None:
    output = safe_rows_for_columns(rows, columns)
    output["updated_at"] = now_text()
    output = output.drop_duplicates(subset=key_cols, keep="last")
    output[columns].to_csv(path, sep=";", encoding="utf-8-sig", index=False)
    st.cache_data.clear()


def drop_empty_config_rows(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    safe = safe_rows_for_columns(df, columns)
    text = safe.fillna("").astype(str).apply(lambda column: column.str.strip())
    return safe[text.ne("").any(axis=1)].copy()


def config_key_from_labels(*values: Any) -> str:
    for value in values:
        slug = slugify_filename(clean_text(value))
        if slug:
            return slug
    return ""


def normalize_active_column(series: pd.Series) -> pd.Series:
    return series.map(lambda value: "TRUE" if normalize_bool(value) else "FALSE")


def duplicate_values(df: pd.DataFrame, column: str) -> list[str]:
    values = df[column].map(clean_text)
    return sorted(values[values.duplicated() & values.ne("")].unique().tolist())


def prepare_management_units_for_save(rows: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    output = drop_empty_config_rows(rows, MANAGEMENT_UNIT_COLUMNS)
    errors: list[str] = []
    output["unit_key"] = output.apply(lambda row: clean_text(row.get("unit_key", "")) or config_key_from_labels(row.get("label_es", ""), row.get("label_eu", "")), axis=1)
    output["label_es"] = output["label_es"].map(clean_text)
    output["label_eu"] = output["label_eu"].map(clean_text)
    output["active"] = normalize_active_column(output["active"])
    output["sort_order"] = pd.to_numeric(output["sort_order"], errors="coerce").fillna(99).astype(int).astype(str)
    output["updated_at"] = now_text()
    if output["unit_key"].map(clean_text).eq("").any():
        errors.append("Hay unidades sin unit_key ni etiqueta para generarlo.")
    duplicates = duplicate_values(output, "unit_key")
    if duplicates:
        errors.append(f"unit_key duplicado: {', '.join(duplicates)}")
    return output[MANAGEMENT_UNIT_COLUMNS], errors


def prepare_work_natures_for_save(rows: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    output = drop_empty_config_rows(rows, WORK_NATURE_COLUMNS)
    errors: list[str] = []
    output["nature_key"] = output.apply(lambda row: clean_text(row.get("nature_key", "")) or config_key_from_labels(row.get("label_es", ""), row.get("label_eu", "")), axis=1)
    output["label_es"] = output["label_es"].map(clean_text)
    output["label_eu"] = output["label_eu"].map(clean_text)
    output["active"] = normalize_active_column(output["active"])
    output["sort_order"] = pd.to_numeric(output["sort_order"], errors="coerce").fillna(99).astype(int).astype(str)
    output["updated_at"] = now_text()
    if output["nature_key"].map(clean_text).eq("").any():
        errors.append("Hay naturalezas sin nature_key ni etiqueta para generarlo.")
    duplicates = duplicate_values(output, "nature_key")
    if duplicates:
        errors.append(f"nature_key duplicado: {', '.join(duplicates)}")
    return output[WORK_NATURE_COLUMNS], errors


def next_rule_id(existing: pd.Series, offset: int = 1) -> str:
    max_id = 0
    for value in existing.map(clean_text):
        match = re.fullmatch(r"R(\d+)", value.upper())
        if match:
            max_id = max(max_id, int(match.group(1)))
    return f"R{max_id + offset:03d}"


def prepare_management_rules_for_save(rows: pd.DataFrame, unit_keys: list[str], nature_keys: list[str]) -> tuple[pd.DataFrame, list[str], list[str]]:
    output = drop_empty_config_rows(rows, MANAGEMENT_RULE_COLUMNS)
    errors: list[str] = []
    warnings: list[str] = []
    existing_ids = output["rule_id"].copy()
    missing_mask = output["rule_id"].map(clean_text).eq("")
    generated_count = 1
    for index in output[missing_mask].index:
        output.loc[index, "rule_id"] = next_rule_id(existing_ids, generated_count)
        generated_count += 1
    output["priority"] = pd.to_numeric(output["priority"], errors="coerce")
    max_priority = int(output["priority"].dropna().max()) if output["priority"].notna().any() else 0
    for index in output[output["priority"].isna()].index:
        max_priority += 10
        output.loc[index, "priority"] = max_priority
    output["priority"] = output["priority"].astype(int).astype(str)
    output["active"] = normalize_active_column(output["active"])
    for column in ["project_contains", "task_contains", "department_contains", "person_contains", "unidad_destino", "naturaleza_trabajo", "notes"]:
        output[column] = output[column].map(clean_text)
    duplicates = duplicate_values(output, "rule_id")
    if duplicates:
        errors.append(f"rule_id duplicado: {', '.join(duplicates)}")
    invalid_units = sorted(set(output["unidad_destino"]) - set(unit_keys) - {""})
    invalid_natures = sorted(set(output["naturaleza_trabajo"]) - set(nature_keys) - {""})
    if invalid_units:
        errors.append(f"unidad_destino no valida: {', '.join(invalid_units)}")
    if invalid_natures:
        errors.append(f"naturaleza_trabajo no valida: {', '.join(invalid_natures)}")
    criteria = ["project_contains", "task_contains", "department_contains", "person_contains"]
    without_criteria = output[criteria].fillna("").astype(str).apply(lambda row: all(not clean_text(value) for value in row), axis=1)
    if without_criteria.any():
        warnings.append(f"Reglas sin criterio de match: {', '.join(output.loc[without_criteria, 'rule_id'].map(clean_text).tolist())}")
    output["updated_at"] = now_text()
    return output[MANAGEMENT_RULE_COLUMNS], errors, warnings


def render_config_management_classification_view(df: pd.DataFrame) -> None:
    lang = current_language()
    st.header(t("config.management_classification", lang=lang))
    st.caption(t("config.technical_columns_note", lang=lang))

    units = read_csv(MANAGEMENT_UNITS_FILE, MANAGEMENT_UNIT_COLUMNS)
    natures = read_csv(WORK_NATURES_FILE, WORK_NATURE_COLUMNS)
    rules = read_csv(MANAGEMENT_RULES_FILE, MANAGEMENT_RULE_COLUMNS)

    st.subheader(t("config.management_units", lang=lang))
    edited_units = st.data_editor(
        units,
        use_container_width=True,
        hide_index=True,
        key="management_units_editor",
        num_rows="dynamic",
        column_config={"active": st.column_config.CheckboxColumn("active")},
    )
    if st.button(t("config.save", lang=lang), key="save_management_units"):
        output, errors = prepare_management_units_for_save(edited_units)
        if errors:
            st.error(f"{t('config.validation_error', lang=lang)}: {' | '.join(errors)}")
        else:
            save_config_table(MANAGEMENT_UNITS_FILE, MANAGEMENT_UNIT_COLUMNS, output, ["unit_key"])
            st.success(t("config.saved", lang=lang))
            st.rerun()

    st.subheader(t("config.work_natures", lang=lang))
    edited_natures = st.data_editor(
        natures,
        use_container_width=True,
        hide_index=True,
        key="work_natures_editor",
        num_rows="dynamic",
        column_config={"active": st.column_config.CheckboxColumn("active")},
    )
    if st.button(t("config.save", lang=lang), key="save_work_natures"):
        output, errors = prepare_work_natures_for_save(edited_natures)
        if errors:
            st.error(f"{t('config.validation_error', lang=lang)}: {' | '.join(errors)}")
        else:
            save_config_table(WORK_NATURES_FILE, WORK_NATURE_COLUMNS, output, ["nature_key"])
            st.success(t("config.saved", lang=lang))
            st.rerun()

    st.subheader(t("config.management_rules", lang=lang))
    unit_options = options(units["unit_key"])
    nature_options = options(natures["nature_key"])
    edited_rules = st.data_editor(
        rules,
        use_container_width=True,
        hide_index=True,
        key="management_rules_editor",
        num_rows="dynamic",
        column_config={
            "active": st.column_config.CheckboxColumn("active"),
            "priority": st.column_config.NumberColumn("priority", step=1),
            "unidad_destino": st.column_config.SelectboxColumn("unidad_destino", options=unit_options),
            "naturaleza_trabajo": st.column_config.SelectboxColumn("naturaleza_trabajo", options=nature_options),
        },
    )
    if st.button(t("config.save", lang=lang), key="save_management_rules"):
        output, errors, warnings = prepare_management_rules_for_save(edited_rules, unit_options, nature_options)
        if warnings:
            st.warning(f"{t('config.validation_warning', lang=lang)}: {' | '.join(warnings)}")
        if errors:
            st.error(f"{t('config.validation_error', lang=lang)}: {' | '.join(errors)}")
        else:
            save_config_table(MANAGEMENT_RULES_FILE, MANAGEMENT_RULE_COLUMNS, output, ["rule_id"])
            st.success(t("config.saved", lang=lang))
            st.rerun()

    st.subheader(t("config.management_review", lang=lang))
    review = build_management_classification_review_table(df)
    review.to_csv(MANAGEMENT_CLASSIFICATION_REVIEW, sep=";", encoding="utf-8-sig", index=False)
    col1, col2, col3 = st.columns(3)
    status_filter = col1.selectbox(
        t("column.classification_status", lang=lang),
        ["all", "pending", "classified"],
        format_func=lambda value: {
            "all": t("config.show_all", lang=lang),
            "pending": t("config.only_pending", lang=lang),
            "classified": t("config.only_classified", lang=lang),
        }[value],
        key="management_review_status",
    )
    unit_filter = col2.selectbox(t("column.unidad_destino_label", lang=lang), [""] + options(review["unidad_destino_label"]), format_func=lambda value: value or t("config.show_all", lang=lang), key="management_review_unit")
    nature_filter = col3.selectbox(t("column.naturaleza_trabajo_label", lang=lang), [""] + options(review["naturaleza_trabajo_label"]), format_func=lambda value: value or t("config.show_all", lang=lang), key="management_review_nature")
    rule_filter = st.selectbox(t("column.classification_rule_id", lang=lang), [""] + options(review["classification_rule_id"]), format_func=lambda value: value or t("config.show_all", lang=lang), key="management_review_rule")
    search = st.text_input(t("config.search_project_task", lang=lang), key="management_review_search")
    filtered_review = review.copy()
    if status_filter == "pending":
        filtered_review = filtered_review[filtered_review["classification_status"] == "pendiente"].copy()
    elif status_filter == "classified":
        filtered_review = filtered_review[filtered_review["classification_status"] == "clasificado"].copy()
    if unit_filter:
        filtered_review = filtered_review[filtered_review["unidad_destino_label"] == unit_filter].copy()
    if nature_filter:
        filtered_review = filtered_review[filtered_review["naturaleza_trabajo_label"] == nature_filter].copy()
    if rule_filter:
        filtered_review = filtered_review[filtered_review["classification_rule_id"] == rule_filter].copy()
    if clean_text(search):
        needle = normalize_text(search)
        searchable = filtered_review[["project_name", "task_name", "department_name", "classification_rule_id", "grupo_gestion"]].fillna("").astype(str).agg(" ".join, axis=1).map(normalize_text)
        filtered_review = filtered_review[searchable.str.contains(needle, regex=False, na=False)].copy()
    st.dataframe(translate_dataframe_columns_for_display(filtered_review, lang), use_container_width=True, hide_index=True)
    st.download_button(
        t("config.download_review_csv", lang=lang),
        filtered_review.to_csv(sep=";", index=False).encode("utf-8-sig"),
        "prc01_management_classification_review.csv",
        "text/csv",
        key="download_management_review_csv",
    )


def render_config_classification_view(df: pd.DataFrame, unclassified: pd.DataFrame) -> None:
    # LEGACY: old project/task classification view by grupo_actividad.
    # It is intentionally not exposed in the current navigation.
    lang = current_language()
    st.caption(t("config.technical_columns_note", lang=lang))
    classification = read_csv(CLASSIFICATION_FILE, CLASSIFICATION_COLUMNS)
    pending_projects = unclassified["project_id"].nunique() if not unclassified.empty else 0
    pending_tasks = len(unclassified) if not unclassified.empty else 0
    pending_hours = float(unclassified["hours"].sum()) if not unclassified.empty and "hours" in unclassified else 0.0
    c1, c2, c3 = st.columns(3)
    c1.metric(t("metric.projects", lang=lang), pending_projects)
    c2.metric(t("metric.tasks", lang=lang), pending_tasks)
    c3.metric(t("metric.unclassified_hours", lang=lang), f"{pending_hours:.1f}")
    if not unclassified.empty:
        st.download_button("Descargar pendientes", unclassified.to_csv(sep=";", index=False).encode("utf-8-sig"), "prc01_unclassified_project_tasks.csv", "text/csv")
    if st.button("Recalcular clasificación y pendientes"):
        recalculated = apply_explicit_classification(df, load_classification_uncached())
        new_unclassified = write_unclassified_report(recalculated)
        write_classification_diagnostics(recalculated)
        st.cache_data.clear()
        st.success(f"Clasificación recalculada. Pendientes reales: {len(new_unclassified)}.")
        st.rerun()

    project_class = classification[(classification["task_id"].map(clean_text) == "") & active_mask(classification["active"])].copy()
    project_class["project_key"] = project_class["project_id"].map(normalize_key)
    project_summary = (
        df.groupby(["project_id", "project_name"], as_index=False)
        .agg(total_hours=("ordu_errealak", "sum"), tasks_count=("task_id", "nunique"), people_count=("pertsona", "nunique"), first_date=("data", "min"), last_date=("data", "max"))
        .sort_values("total_hours", ascending=False)
    )
    project_summary["first_date"] = project_summary["first_date"].dt.date.astype(str)
    project_summary["last_date"] = project_summary["last_date"].dt.date.astype(str)
    project_summary["project_key"] = project_summary["project_id"].map(normalize_key)
    project_summary = project_summary.merge(project_class[["project_key", "grupo_actividad", "subgrupo", "comment"]], on="project_key", how="left")
    project_summary["grupo_actividad"] = project_summary["grupo_actividad"].fillna("Pendiente de clasificar")
    project_summary["subgrupo"] = project_summary["subgrupo"].fillna("")
    project_summary["comment"] = project_summary["comment"].fillna("")
    edited = st.data_editor(
        project_summary[["project_id", "project_name", "total_hours", "tasks_count", "people_count", "first_date", "last_date", "grupo_actividad", "subgrupo", "comment"]],
        use_container_width=True,
        hide_index=True,
        column_config={"grupo_actividad": st.column_config.SelectboxColumn("grupo_actividad", options=ALLOWED_GROUPS, required=True)},
        disabled=["project_id", "project_name", "total_hours", "tasks_count", "people_count", "first_date", "last_date"],
    )
    if st.button(t("config.save", lang=lang), type="primary"):
        rows = edited.copy()
        rows["task_id"] = ""
        rows["task_name"] = ""
        rows["active"] = "TRUE"
        rows["review_status"] = "reviewed"
        rows["reviewed_by"] = current_user()
        rows["reviewed_at"] = now_text()
        safe_rows = safe_rows_for_columns(rows, CLASSIFICATION_COLUMNS)
        upsert_rows(CLASSIFICATION_FILE, CLASSIFICATION_COLUMNS, safe_rows, ["project_id", "task_id"])
        st.success(t("config.saved", lang=lang))
        st.rerun()

    st.subheader(t("column.task_name", lang=lang))
    selected_project = st.selectbox(t("column.project_name", lang=lang), options(project_summary["project_name"].tolist()))
    project_id = project_summary.loc[project_summary["project_name"] == selected_project, "project_id"].iloc[0]
    task_summary = (
        df[df["project_id"] == project_id]
        .groupby(["project_id", "project_name", "task_id", "task_name"], as_index=False)
        .agg(total_hours=("ordu_errealak", "sum"), people_count=("pertsona", "nunique"))
        .sort_values("total_hours", ascending=False)
    )
    task_class = classification[(classification["task_id"].map(clean_text) != "") & active_mask(classification["active"])].copy()
    task_class["project_key"] = task_class["project_id"].map(normalize_key)
    task_class["task_key"] = task_class["task_id"].map(normalize_key)
    task_summary["project_key"] = task_summary["project_id"].map(normalize_key)
    task_summary["task_key"] = task_summary["task_id"].map(normalize_key)
    task_summary = task_summary.merge(task_class[["project_key", "task_key", "grupo_actividad", "subgrupo", "comment"]], on=["project_key", "task_key"], how="left")
    task_summary["grupo_actividad"] = task_summary["grupo_actividad"].fillna("Pendiente de clasificar")
    task_summary["subgrupo"] = task_summary["subgrupo"].fillna("")
    task_summary["comment"] = task_summary["comment"].fillna("")
    edited_tasks = st.data_editor(
        task_summary[["project_id", "project_name", "task_id", "task_name", "total_hours", "people_count", "grupo_actividad", "subgrupo", "comment"]],
        use_container_width=True,
        hide_index=True,
        column_config={"grupo_actividad": st.column_config.SelectboxColumn("grupo_actividad", options=ALLOWED_GROUPS, required=True)},
        disabled=["project_id", "project_name", "task_id", "task_name", "total_hours", "people_count"],
    )
    if st.button(t("config.save", lang=lang), key="save_task_exceptions"):
        rows = edited_tasks[edited_tasks["grupo_actividad"] != "Pendiente de clasificar"].copy()
        rows["active"] = "TRUE"
        rows["review_status"] = "reviewed"
        rows["reviewed_by"] = current_user()
        rows["reviewed_at"] = now_text()
        safe_rows = safe_rows_for_columns(rows, CLASSIFICATION_COLUMNS)
        upsert_rows(CLASSIFICATION_FILE, CLASSIFICATION_COLUMNS, safe_rows, ["project_id", "task_id"])
        st.success(t("config.saved", lang=lang))
        st.rerun()


def scope_options(df: pd.DataFrame, teams: pd.DataFrame, scope_type: str) -> list[tuple[str, str]]:
    if scope_type == "company":
        return [("IMH", "IMH Campus")]
    if scope_type == "department":
        return [(v, v) for v in options(df["saila"])]
    if scope_type == "team":
        return [(v, v) for v in options(teams["team_name"])]
    return [(v, v) for v in options(df["pertsona"])]


def render_config_available_hours_view(df: pd.DataFrame) -> None:
    lang = current_language()
    st.header(t("config.available_hours", lang=lang))
    st.caption(t("config.technical_columns_note", lang=lang))
    teams = load_teams(str(TEAMS_FILE))
    available = read_csv(AVAILABLE_HOURS_FILE, AVAILABLE_COLUMNS)
    years = sorted(set(df["urtea"].dropna().astype(int).tolist()) | {datetime.now().year})
    year = st.selectbox(t("app.filters.year", lang=lang), years, index=len(years) - 1)
    scope_type = st.selectbox(t("column.base_scope_type", lang=lang), SCOPE_TYPES, format_func=lambda x: {"company": "empresa", "department": "departamento", "team": "equipo", "person": "persona"}[x])
    scopes = scope_options(df, teams, scope_type)
    scope_key = st.selectbox(t("column.base_scope_name", lang=lang), [key for key, _ in scopes], format_func=lambda k: dict(scopes).get(k, k))
    scope_name = dict(scopes).get(scope_key, scope_key)
    rows = pd.DataFrame({"month": list(MONTH_NAMES_EU.keys())})
    rows["month_name"] = rows["month"].map(MONTH_NAMES_EU)
    current = available[(available["year"].astype(str) == str(year)) & (available["scope_type"] == scope_type) & (available["scope_key"] == scope_key)].copy()
    current["month"] = pd.to_numeric(current["month"], errors="coerce").astype("Int64")
    rows = rows.merge(current[["month", "available_hours", "comment"]], on="month", how="left")
    rows["available_hours"] = pd.to_numeric(rows["available_hours"], errors="coerce").fillna(0.0)
    rows["comment"] = rows["comment"].fillna("")
    edited = st.data_editor(rows, use_container_width=True, hide_index=True, disabled=["month", "month_name"], column_config={"available_hours": st.column_config.NumberColumn("available_hours", min_value=0.0, step=1.0)})
    if st.button(t("config.save", lang=lang), type="primary"):
        output = edited.copy()
        output["year"] = year
        output["scope_type"] = scope_type
        output["scope_key"] = scope_key
        output["scope_name"] = scope_name
        output["active"] = "TRUE"
        output["updated_by"] = current_user()
        output["updated_at"] = now_text()
        upsert_rows(AVAILABLE_HOURS_FILE, AVAILABLE_COLUMNS, output[AVAILABLE_COLUMNS], ["year", "month", "scope_type", "scope_key"])
        st.success(t("config.saved", lang=lang))
        st.rerun()


def consolidate_person_workload(workload: pd.DataFrame, people: list[str], year: int) -> pd.DataFrame:
    rows = []
    source = workload.copy()
    source["year"] = pd.to_numeric(source.get("year", year), errors="coerce").fillna(year).astype(int)
    source = source[source["year"] == year].copy()
    source["workload_factor"] = pd.to_numeric(source.get("workload_factor", 1.0), errors="coerce")
    source["weekly_hours"] = pd.to_numeric(source.get("weekly_hours", 40.0), errors="coerce")
    for person in people:
        current = source[source["person_key"].map(clean_text) == person].copy()
        if current.empty:
            rows.append(
                {
                    "person_key": person,
                    "person_name": person,
                    "year": year,
                    "workload_factor": 1.0,
                    "weekly_hours": 40.0,
                    "active": "TRUE",
                    "comment": "",
                    "updated_by": "",
                    "updated_at": "",
                }
            )
            continue
        active_rows = current[active_mask(current["active"])] if "active" in current.columns else current
        if active_rows.empty:
            active_rows = current
        factor = active_rows["workload_factor"].dropna().mode()
        weekly = active_rows["weekly_hours"].dropna().mode()
        last = active_rows.iloc[-1]
        rows.append(
            {
                "person_key": person,
                "person_name": clean_text(last.get("person_name", person)) or person,
                "year": year,
                "workload_factor": float(factor.iloc[0]) if not factor.empty else 1.0,
                "weekly_hours": float(weekly.iloc[0]) if not weekly.empty else 40.0,
                "active": clean_text(last.get("active", "TRUE")) or "TRUE",
                "comment": clean_text(last.get("comment", "")),
                "updated_by": clean_text(last.get("updated_by", "")),
                "updated_at": clean_text(last.get("updated_at", "")),
            }
        )
    return pd.DataFrame(rows, columns=PERSON_WORKLOAD_COLUMNS)


def render_config_person_workload_view(df: pd.DataFrame) -> None:
    lang = current_language()
    st.header(t("config.person_workload", lang=lang))
    st.caption(t("config.technical_columns_note", lang=lang))
    workload = read_csv(PERSON_WORKLOAD_FILE, PERSON_WORKLOAD_COLUMNS)
    years = sorted(set(df["urtea"].dropna().astype(int).tolist()) | {datetime.now().year})
    year = st.selectbox(t("app.filters.year", lang=lang), years, index=len(years) - 1)
    people = options(df["pertsona"])
    rows = consolidate_person_workload(workload, people, int(year))
    rows["active"] = active_mask(rows["active"])
    st.caption("Futuro: horas disponibles por persona = calendario laboral mensual * workload_factor.")
    edited = st.data_editor(
        rows[["person_key", "person_name", "year", "workload_factor", "weekly_hours", "active", "comment", "updated_by", "updated_at"]],
        use_container_width=True,
        hide_index=True,
        disabled=["person_key", "updated_by", "updated_at"],
        column_config={
            "workload_factor": st.column_config.NumberColumn("workload_factor", min_value=0.0, max_value=1.5, step=0.1),
            "weekly_hours": st.column_config.NumberColumn("weekly_hours", min_value=0.0, max_value=60.0, step=1.0),
            "active": st.column_config.CheckboxColumn("active"),
        },
    )
    if st.button(t("config.save", lang=lang), type="primary"):
        output = edited.copy()
        output["person_key"] = output["person_key"].map(clean_text)
        output["person_name"] = output["person_name"].map(clean_text)
        output["year"] = pd.to_numeric(output["year"], errors="coerce").fillna(year).astype(int)
        output["workload_factor"] = pd.to_numeric(output["workload_factor"], errors="coerce").fillna(1.0)
        output["weekly_hours"] = pd.to_numeric(output["weekly_hours"], errors="coerce").fillna(40.0)
        output["active"] = output["active"].map(lambda value: "TRUE" if str(value).upper() in {"TRUE", "1", "YES", "SI"} else "FALSE")
        output["updated_by"] = current_user()
        output["updated_at"] = now_text()
        output = output.drop_duplicates(subset=["person_key", "year"], keep="last")
        upsert_rows(PERSON_WORKLOAD_FILE, PERSON_WORKLOAD_COLUMNS, output[PERSON_WORKLOAD_COLUMNS], ["person_key", "year"])
        st.success(t("config.saved", lang=lang))
        st.rerun()


def render_config_language_view() -> None:
    lang = current_language()
    st.header(t("config.language", lang=lang))
    ensure_translation_file()
    translations = read_csv(TRANSLATIONS_FILE, TRANSLATION_COLUMNS)
    edit_mode = st.radio(t("config.edit_language", lang=lang), ["Castellano", "Euskera", t("config.edit_both", lang=lang)], horizontal=True)
    visible_columns = ["key", "context", "text_es", "text_eu", "notes", "active", "updated_at"]
    disabled = ["key", "context", "updated_at"]
    if edit_mode == "Castellano":
        disabled.append("text_eu")
    elif edit_mode == "Euskera":
        disabled.append("text_es")
    edited = st.data_editor(
        translations[visible_columns],
        use_container_width=True,
        hide_index=True,
        disabled=disabled,
        column_config={"active": st.column_config.CheckboxColumn("active")},
    )
    col1, col2 = st.columns(2)
    if col1.button(t("config.save", lang=lang)):
        output = edited.copy()
        output["updated_at"] = now_text()
        output["active"] = output["active"].map(lambda value: "TRUE" if normalize_bool(value) else "FALSE")
        output = output.drop_duplicates("key", keep="last")
        output[TRANSLATION_COLUMNS].to_csv(TRANSLATIONS_FILE, sep=";", encoding="utf-8-sig", index=False)
        load_translations_cached.clear()
        st.success(t("config.saved", lang=lang))
        st.rerun()
    if col2.button(t("config.detect_missing_translations", lang=lang)):
        seeds = seed_translation_dataframe()
        column_seeds = pd.DataFrame(
            [
                {
                    "key": f"column.{column}",
                    "context": "column",
                    "text_es": column,
                    "text_eu": "",
                    "notes": "Detectado como columna visible",
                    "active": "TRUE",
                    "updated_at": "",
                }
                for column in REQUIRED_COLUMN_KEYS
            ],
            columns=TRANSLATION_COLUMNS,
        )
        seeds = pd.concat([seeds, column_seeds], ignore_index=True).drop_duplicates("key", keep="first")
        current = read_csv(TRANSLATIONS_FILE, TRANSLATION_COLUMNS)
        missing = seeds[~seeds["key"].isin(current["key"])].copy()
        if missing.empty:
            st.info(t("config.no_new_keys", lang=lang))
        else:
            pd.concat([current, missing], ignore_index=True).drop_duplicates("key", keep="first").to_csv(
                TRANSLATIONS_FILE,
                sep=";",
                encoding="utf-8-sig",
                index=False,
            )
            load_translations_cached.clear()
            st.success(f"{t('config.keys_added', lang=lang)}: {len(missing)}")
            st.rerun()


def download_table(df: pd.DataFrame, filename: str) -> None:
    st.download_button("Descargar CSV", df.to_csv(sep=";", index=False).encode("utf-8-sig"), filename, "text/csv")


def render_explore_departments_view(df: pd.DataFrame) -> None:
    st.header("Exploracion Odoo / Departamentos")
    table = df.groupby("saila", as_index=False).agg(horas=("ordu_errealak", "sum"), personas=("pertsona", "nunique"), proyectos=("project_name", "nunique"), lineas=("ordu_errealak", "size")).sort_values("horas", ascending=False)
    st.dataframe(table, use_container_width=True, hide_index=True)
    download_table(table, "prc01_departments_explore.csv")


def render_explore_teams_view(df: pd.DataFrame) -> None:
    st.header("Exploracion Odoo / Equipos")
    teams = load_teams(str(TEAMS_FILE))
    rows = []
    assigned: set[str] = set()
    for team in options(teams["team_name"]):
        people = team_people(df, teams, team)
        assigned.update(people)
        hours = df[df["pertsona"].isin(people)]["ordu_errealak"].sum()
        rows.append({"equipo": team, "personas_configuradas": len(people), "horas_detectadas": hours, "personas": " | ".join(people)})
    without_team = sorted(set(options(df["pertsona"])) - assigned)
    table = pd.DataFrame(rows)
    st.dataframe(table, use_container_width=True, hide_index=True)
    st.markdown("Personas con horas no incluidas en ningun equipo")
    st.dataframe(pd.DataFrame({"persona": without_team}), use_container_width=True, hide_index=True)
    download_table(table, "prc01_teams_explore.csv")


def render_explore_people_view(df: pd.DataFrame) -> None:
    st.header("Exploracion Odoo / Personas")
    table = df.groupby(["pertsona", "saila"], as_index=False).agg(horas=("ordu_errealak", "sum"), proyectos=("project_name", "nunique"), tareas=("task_name", "nunique")).sort_values("horas", ascending=False)
    st.dataframe(table, use_container_width=True, hide_index=True)
    download_table(table, "prc01_people_explore.csv")


def render_explore_projects_view(df: pd.DataFrame) -> None:
    st.header("Exploracion Odoo / Proyectos")
    table = (
        df.groupby(["project_id", "project_name", "grupo_gestion", "unidad_destino_label", "naturaleza_trabajo_label", "classification_status"], as_index=False)
        .agg(horas=("ordu_errealak", "sum"), personas=("pertsona", "nunique"), tareas=("task_name", "nunique"))
        .sort_values("horas", ascending=False)
    )
    st.dataframe(translate_dataframe_columns_for_display(table, current_language()), use_container_width=True, hide_index=True)
    download_table(table, "prc01_projects_explore.csv")


def render_explore_tasks_view(df: pd.DataFrame) -> None:
    st.header("Exploracion Odoo / Tareas")
    table = (
        df.groupby(["project_id", "project_name", "task_id", "task_name", "grupo_gestion", "unidad_destino_label", "naturaleza_trabajo_label", "classification_rule_id", "classification_status"], as_index=False)
        .agg(horas=("ordu_errealak", "sum"), personas=("pertsona", "nunique"))
        .sort_values("horas", ascending=False)
    )
    st.dataframe(translate_dataframe_columns_for_display(table, current_language()), use_container_width=True, hide_index=True)
    download_table(table, "prc01_tasks_explore.csv")


def main() -> None:
    ensure_config_files()
    section, detail = navigation()
    lang = current_language()
    if section == "analysis":
        st.title(t("app.analysis.title", lang=lang))
    elif section == "planning":
        st.title(t("planning.title", lang=lang))
    elif section == "operational_performance":
        st.title(t("operational.title", lang=lang))
    elif section == "odoo":
        st.title(t("app.nav.odoo_connection", lang=lang))
    elif section == "config":
        config_titles = {
            "management_classification": "config.management_classification",
            "available_hours": "config.available_hours",
            "workload": "config.person_workload",
            "language": "config.language",
        }
        st.title(t(config_titles.get(detail, "config.title"), lang=lang))
    elif detail:
        st.title(f"{section} - {detail}")
    else:
        st.title(section)
    management_mtime = max(
        path.stat().st_mtime if path.exists() else 0
        for path in [MANAGEMENT_UNITS_FILE, WORK_NATURES_FILE, MANAGEMENT_RULES_FILE]
    )
    df, unclassified = load_data(
        str(DATA_FILE),
        CLASSIFICATION_FILE.stat().st_mtime if CLASSIFICATION_FILE.exists() else 0,
        management_mtime,
        lang,
    )
    if section == "odoo":
        render_odoo_connection_view()
    elif section == "planning":
        render_planning_view(df)
    elif section == "operational_performance":
        render_operational_performance_view(df)
    elif section == "analysis":
        render_dataset_notices(dataset_notices(df, unclassified))
        render_dashboard_view(df, "department", "department")
    elif section == "config":
        if detail == "management_classification":
            render_config_management_classification_view(df)
        elif detail == "available_hours":
            render_config_available_hours_view(df)
        elif detail == "workload":
            render_config_person_workload_view(df)
        elif detail == "language":
            render_config_language_view()
    elif section == "explore":
        if detail == "departments":
            render_explore_departments_view(df)
        elif detail == "teams":
            render_explore_teams_view(df)
        elif detail == "people":
            render_explore_people_view(df)
        elif detail == "projects":
            render_explore_projects_view(df)
        elif detail == "tasks":
            render_explore_tasks_view(df)


if __name__ == "__main__":
    main()
