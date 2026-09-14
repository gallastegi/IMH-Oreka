from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import xmlrpc.client
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_REPORTS_DIR = ROOT_DIR / "data" / "reports"
LOGS_DIR = ROOT_DIR / "logs"

MODELS_TO_CHECK = [
    "res.partner",
    "crm.lead",
    "sale.order",
    "sale.order.line",
    "product.product",
    "project.project",
    "project.task",
    "project.forecast",
    "account.analytic.line",
    "hr.employee",
    "hr.department",
    "res.users",
    "ir.model",
    "ir.model.access",
    "ir.rule",
]

RELEVANT_FIELDS = {
    "res.partner": ["name", "customer", "supplier", "email", "user_id", "company_id"],
    "crm.lead": ["name", "type", "partner_id", "partner_name", "planned_revenue", "expected_revenue", "probability", "stage_id", "user_id", "team_id"],
    "sale.order": ["name", "partner_id", "state", "opportunity_id", "origin", "client_order_ref", "amount_total"],
    "sale.order.line": ["order_id", "product_id", "name", "product_uom_qty", "price_unit", "project_id", "task_id"],
    "product.product": ["name", "type", "sale_ok", "list_price", "uom_id"],
    "project.project": ["name", "partner_id", "user_id", "sale_order_id", "sale_line_id"],
    "project.task": ["name", "project_id", "user_id", "partner_id", "planned_hours", "sale_order_id", "sale_line_id"],
    "project.forecast": ["employee_id", "user_id", "project_id", "task_id", "date_start", "date_end", "quantity"],
    "account.analytic.line": ["name", "employee_id", "user_id", "project_id", "task_id", "date", "unit_amount"],
    "hr.employee": ["name", "user_id", "department_id", "resource_calendar_id"],
    "hr.department": ["name", "parent_id"],
    "res.users": ["name", "login", "groups_id"],
}

ACCESS_OPERATIONS = ["read", "create", "write", "unlink"]


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def json_default(value: Any) -> str:
    return str(value)


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        raise RuntimeError(f"No existe --env-file: {path}")
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        quote: str | None = None
        if value.startswith('"') and '"' in value[1:]:
            quote = '"'
        elif value.startswith("'") and "'" in value[1:]:
            quote = "'"
        if quote:
            end = value.find(quote, 1)
            value = value[1:end]
        else:
            value = value.split("#", 1)[0].strip()
        values[key] = value
    return values


def load_environment(env_file: str | None) -> dict[str, str]:
    if env_file:
        for key, value in parse_env_file(Path(env_file)).items():
            os.environ[key] = value
    env = {
        "ODOO_URL": os.getenv("ODOO_URL", "").rstrip("/"),
        "ODOO_DB": os.getenv("ODOO_DB", ""),
        "ODOO_USER": os.getenv("ODOO_USER", ""),
        "ODOO_PASSWORD": os.getenv("ODOO_PASSWORD", ""),
    }
    missing = [key for key, value in env.items() if not value]
    if missing:
        raise RuntimeError(f"Faltan variables de entorno obligatorias: {', '.join(missing)}")
    return env


class ReadOnlyOdooClient:
    def __init__(self, url: str, db: str, user: str, password: str) -> None:
        self.url = url.rstrip("/")
        self.db = db
        self.user = user
        self.password = password
        self.common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common", allow_none=True)
        self.models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object", allow_none=True)
        self.uid: int | None = None

    def authenticate(self) -> int:
        uid = self.common.authenticate(self.db, self.user, self.password, {})
        if not uid:
            raise RuntimeError("No se ha podido autenticar en Odoo.")
        self.uid = int(uid)
        return self.uid

    def version(self) -> dict[str, Any]:
        return self.common.version()

    def execute(self, model: str, method: str, args: list[Any] | None = None, kwargs: dict[str, Any] | None = None) -> Any:
        if self.uid is None:
            self.authenticate()
        return self.models.execute_kw(self.db, self.uid, self.password, model, method, args or [], kwargs or {})

    def fields_get(self, model: str) -> dict[str, Any]:
        return self.execute(model, "fields_get", kwargs={"attributes": ["string", "type", "relation", "required"]})

    def check_access_rights(self, model: str, operation: str) -> bool:
        return bool(self.execute(model, "check_access_rights", args=[operation], kwargs={"raise_exception": False}))

    def search_count(self, model: str) -> int:
        return int(self.execute(model, "search_count", args=[[]]))

    def search(self, model: str, limit: int = 1) -> list[int]:
        return self.execute(model, "search", args=[[]], kwargs={"limit": limit})

    def read(self, model: str, ids: list[int], fields: list[str]) -> list[dict[str, Any]]:
        return self.execute(model, "read", args=[ids], kwargs={"fields": fields})


def base_model_result() -> dict[str, Any]:
    return {
        "exists": False,
        "permissions": {operation: None for operation in ACCESS_OPERATIONS},
        "permission_errors": {},
        "search_count_ok": False,
        "search_count": None,
        "search_count_error": "",
        "fields_get_ok": False,
        "fields_count": 0,
        "relevant_fields_available": [],
        "sample_search_ok": None,
        "sample_read_ok": None,
        "sample_id": None,
        "sample_values": {},
        "sample_error": "",
        "errors": [],
    }


def inspect_model(client: ReadOnlyOdooClient, model: str, with_read_sample: bool) -> dict[str, Any]:
    result = base_model_result()
    fields: dict[str, Any] = {}
    try:
        fields = client.fields_get(model)
        result["exists"] = True
        result["fields_get_ok"] = True
        result["fields_count"] = len(fields)
        result["relevant_fields_available"] = [field for field in RELEVANT_FIELDS.get(model, []) if field in fields]
    except Exception as exc:
        result["errors"].append(f"fields_get: {exc}")
        return result

    for operation in ACCESS_OPERATIONS:
        try:
            result["permissions"][operation] = client.check_access_rights(model, operation)
        except Exception as exc:
            result["permissions"][operation] = None
            result["permission_errors"][operation] = str(exc)
            result["errors"].append(f"check_access_rights({operation}): {exc}")

    try:
        result["search_count"] = client.search_count(model)
        result["search_count_ok"] = True
    except Exception as exc:
        result["search_count_error"] = str(exc)
        result["errors"].append(f"search_count: {exc}")

    if with_read_sample:
        try:
            ids = client.search(model, limit=1)
            result["sample_search_ok"] = True
            if ids:
                result["sample_id"] = ids[0]
                sample_fields = [field for field in ["name", "display_name"] if field in fields]
                sample_fields = ["id"] + sample_fields
                records = client.read(model, [ids[0]], sample_fields)
                result["sample_read_ok"] = True
                if records:
                    result["sample_values"] = {key: value for key, value in records[0].items() if key in {"id", "name", "display_name"}}
            else:
                result["sample_read_ok"] = None
        except Exception as exc:
            result["sample_read_ok"] = False
            result["sample_error"] = str(exc)
            result["errors"].append(f"sample read: {exc}")

    return result


def read_user_groups(client: ReadOnlyOdooClient, uid: int) -> dict[str, Any]:
    result = {"read_ok": False, "user": {}, "groups": [], "error": ""}
    fields = ["id", "name", "login", "groups_id", "company_id", "company_ids"]
    try:
        users = client.read("res.users", [uid], fields)
        if not users:
            result["error"] = "res.users read no devolvio registros."
            return result
        user = users[0]
        result["read_ok"] = True
        result["user"] = {key: user.get(key) for key in ["id", "name", "login", "company_id", "company_ids"] if key in user}
        group_ids = user.get("groups_id") or []
        if group_ids:
            try:
                groups = client.read("res.groups", group_ids, ["id", "name", "full_name", "category_id"])
                result["groups"] = [
                    {
                        "id": group.get("id"),
                        "name": group.get("full_name") or group.get("name"),
                        "category_id": group.get("category_id"),
                    }
                    for group in groups
                ]
            except Exception as exc:
                result["error"] = f"No se han podido leer nombres de grupos: {exc}"
        return result
    except Exception as exc:
        result["error"] = str(exc)
        return result


def bool_text(value: Any) -> str:
    if value is True:
        return "SI"
    if value is False:
        return "NO"
    return "N/D"


def first_error(model_result: dict[str, Any]) -> str:
    if model_result.get("errors"):
        return str(model_result["errors"][0])
    if model_result.get("search_count_error"):
        return str(model_result["search_count_error"])
    if model_result.get("sample_error"):
        return str(model_result["sample_error"])
    return ""


def build_summary(models: dict[str, dict[str, Any]]) -> dict[str, Any]:
    def can(model: str, operation: str) -> bool:
        return bool(models.get(model, {}).get("permissions", {}).get(operation))

    crm_viable = can("crm.lead", "create") and can("crm.lead", "read")
    partner_create = can("res.partner", "create")
    partner_read = can("res.partner", "read")
    sale_viable = can("sale.order", "create") and can("sale.order.line", "create") and partner_read
    forecast_viable = (
        models.get("project.forecast", {}).get("exists")
        and can("project.forecast", "create")
        and can("hr.employee", "read")
        and (can("project.project", "read") or can("project.project", "create"))
        and (can("project.task", "read") or can("project.task", "create"))
    )
    if crm_viable:
        crm_recommendation = "Se puede plantear una prueba controlada de escritura CRM."
        if not partner_create:
            crm_recommendation += " Si no puede crear contacto, probar oportunidad sin partner_id usando partner_name si el modelo lo permite."
    else:
        crm_recommendation = "No hacer prueba de escritura CRM con este usuario."

    return {
        "crm_minimal_write_viable": crm_viable,
        "partner_read": partner_read,
        "partner_create": partner_create,
        "sale_order_write_viable": sale_viable,
        "forecast_write_viable": bool(forecast_viable),
        "can_create_crm_lead": can("crm.lead", "create"),
        "can_create_partner": partner_create,
        "can_create_sale_order": can("sale.order", "create"),
        "can_create_project": can("project.project", "create"),
        "can_create_task": can("project.task", "create"),
        "can_create_forecast": can("project.forecast", "create"),
        "recommendation": crm_recommendation,
    }


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=json_default), encoding="utf-8")


def write_matrix_csv(path: Path, models: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "model",
        "exists",
        "read",
        "create",
        "write",
        "unlink",
        "search_count_ok",
        "search_count",
        "fields_get_ok",
        "sample_read_ok",
        "main_error",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter=";")
        writer.writeheader()
        for model, result in models.items():
            row = {
                "model": model,
                "exists": result.get("exists"),
                "read": result.get("permissions", {}).get("read"),
                "create": result.get("permissions", {}).get("create"),
                "write": result.get("permissions", {}).get("write"),
                "unlink": result.get("permissions", {}).get("unlink"),
                "search_count_ok": result.get("search_count_ok"),
                "search_count": result.get("search_count"),
                "fields_get_ok": result.get("fields_get_ok"),
                "sample_read_ok": result.get("sample_read_ok"),
                "main_error": first_error(result),
            }
            writer.writerow(row)


def model_line(model: str, result: dict[str, Any]) -> str:
    permissions = result.get("permissions", {})
    return (
        f"| `{model}` | {bool_text(result.get('exists'))} | {bool_text(permissions.get('read'))} | "
        f"{bool_text(permissions.get('create'))} | {bool_text(permissions.get('write'))} | "
        f"{bool_text(permissions.get('unlink'))} | {bool_text(result.get('search_count_ok'))} | "
        f"{result.get('search_count') if result.get('search_count') is not None else ''} | {first_error(result)[:120]} |"
    )


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    env = report["environment"]
    models = report["models"]
    summary = report["summary"]
    groups = report["user_groups"]
    lines = [
        "# Diagnóstico de permisos Odoo",
        "",
        "## Entorno",
        "",
        f"- URL: `{env['url']}`",
        f"- DB: `{env['db']}`",
        f"- Usuario: `{env['user']}`",
        f"- UID: `{env['uid']}`",
        f"- Versión: `{env.get('version', {})}`",
        "",
        "## Resumen ejecutivo",
        "",
        f"- Puede crear oportunidades CRM: {bool_text(summary['can_create_crm_lead'])}",
        f"- Puede crear clientes/contactos: {bool_text(summary['can_create_partner'])}",
        f"- Puede crear presupuestos: {bool_text(summary['can_create_sale_order'])}",
        f"- Puede crear proyectos: {bool_text(summary['can_create_project'])}",
        f"- Puede crear tareas: {bool_text(summary['can_create_task'])}",
        f"- Puede crear forecast: {bool_text(summary['can_create_forecast'])}",
        "",
        "## Matriz de permisos",
        "",
        "| Modelo | Existe | Read | Create | Write | Unlink | Search count | Count | Error principal |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for model in MODELS_TO_CHECK:
        lines.append(model_line(model, models[model]))

    def bullet_models(title: str, model_names: list[str]) -> None:
        lines.extend(["", f"## {title}", ""])
        for model in model_names:
            result = models[model]
            permissions = result.get("permissions", {})
            lines.append(
                f"- `{model}`: read={bool_text(permissions.get('read'))}, create={bool_text(permissions.get('create'))}, "
                f"fields={result.get('relevant_fields_available', [])}"
            )

    bullet_models("Modelos clave para CRM", ["res.partner", "crm.lead", "sale.order", "sale.order.line", "product.product"])
    bullet_models("Modelos clave para planificación", ["project.project", "project.task", "project.forecast", "account.analytic.line", "hr.employee", "hr.department"])

    lines.extend(["", "## Grupos del usuario", ""])
    if groups.get("read_ok"):
        lines.append(f"- Usuario leído: {groups.get('user', {})}")
        for group in groups.get("groups", []):
            lines.append(f"- {group.get('id')}: {group.get('name')}")
    else:
        lines.append(f"- No se han podido leer grupos: {groups.get('error', '')}")

    lines.extend(
        [
            "",
            "## Conclusión",
            "",
            f"- ¿Puede crear oportunidades CRM? {bool_text(summary['can_create_crm_lead'])}",
            f"- ¿Puede crear clientes/contactos? {bool_text(summary['can_create_partner'])}",
            f"- ¿Puede crear presupuestos? {bool_text(summary['sale_order_write_viable'])}",
            f"- ¿Puede crear proyectos? {bool_text(summary['can_create_project'])}",
            f"- ¿Puede crear tareas? {bool_text(summary['can_create_task'])}",
            f"- ¿Puede crear forecast? {bool_text(summary['can_create_forecast'])}",
            f"- ¿Tiene sentido probar escritura controlada en producción? {bool_text(summary['crm_minimal_write_viable'])}",
            "",
            "## Recomendación",
            "",
            summary["recommendation"],
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_log(path: Path, report: dict[str, Any], with_read_sample: bool) -> None:
    summary = report["summary"]
    lines = [
        "# Log diagnóstico permisos Odoo",
        "",
        f"- fecha/hora: {now_text()}",
        f"- entorno: {report['environment']['url']} / {report['environment']['db']}",
        f"- usuario: {report['environment']['user']}",
        f"- with_read_sample: {with_read_sample}",
        "",
        "## Resultado",
        "",
        f"- CRM viable: {summary['crm_minimal_write_viable']}",
        f"- Presupuestos viable: {summary['sale_order_write_viable']}",
        f"- Forecast viable: {summary['forecast_write_viable']}",
        f"- Recomendación: {summary['recommendation']}",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnóstico read-only de permisos Odoo.")
    parser.add_argument("--with-read-sample", action="store_true", help="Intenta search/read de 1 registro por modelo.")
    parser.add_argument("--verbose", action="store_true", help="Muestra progreso por consola.")
    parser.add_argument("--env-file", help="Ruta a .env privado con ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    env = load_environment(args.env_file)
    client = ReadOnlyOdooClient(env["ODOO_URL"], env["ODOO_DB"], env["ODOO_USER"], env["ODOO_PASSWORD"])
    uid = client.authenticate()
    version = client.version()
    models: dict[str, dict[str, Any]] = {}
    for model in MODELS_TO_CHECK:
        if args.verbose:
            print(f"Comprobando {model}")
        models[model] = inspect_model(client, model, args.with_read_sample)
    user_groups = read_user_groups(client, uid)
    summary = build_summary(models)
    report = {
        "environment": {
            "url": env["ODOO_URL"],
            "db": env["ODOO_DB"],
            "user": env["ODOO_USER"],
            "uid": uid,
            "version": version,
        },
        "models": models,
        "user_groups": user_groups,
        "summary": summary,
    }

    DATA_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = DATA_REPORTS_DIR / "21_odoo_permissions_report.json"
    md_path = DATA_REPORTS_DIR / "21_odoo_permissions_report.md"
    csv_path = DATA_REPORTS_DIR / "21_odoo_permissions_matrix.csv"
    log_path = LOGS_DIR / f"odoo_permissions_check_{now_stamp()}.md"
    write_json(json_path, report)
    write_matrix_csv(csv_path, models)
    write_markdown(md_path, report)
    write_log(log_path, report, args.with_read_sample)

    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    print(f"CSV: {csv_path}")
    print(f"Log: {log_path}")
    print(f"Recomendación: {summary['recommendation']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
