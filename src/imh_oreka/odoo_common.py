from __future__ import annotations

import csv
import json
import os
import re
import xmlrpc.client
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_ODOO_URL = "https://odoo.imh.eus"
DEFAULT_ODOO_DB = "imh"

DATA_DIR = PROJECT_ROOT / "data"
DATA_RAW_DIR = DATA_DIR / "raw"
DATA_PROCESSED_DIR = DATA_DIR / "processed"
DATA_REPORTS_DIR = DATA_DIR / "reports"
CONFIG_DIR = PROJECT_ROOT / "config"

for path in (DATA_RAW_DIR, DATA_PROCESSED_DIR, DATA_REPORTS_DIR, CONFIG_DIR):
    path.mkdir(parents=True, exist_ok=True)

OUTPUT_DIR = DATA_RAW_DIR


def get_env(name: str, default: str | None = None, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"Falta la variable de entorno obligatoria: {name}")
    return value or ""


ODOO_URL = get_env("ODOO_URL", DEFAULT_ODOO_URL).rstrip("/")
ODOO_DB = get_env("ODOO_DB", DEFAULT_ODOO_DB)
ODOO_USER = get_env("ODOO_USER", "")
ODOO_PASSWORD = get_env("ODOO_PASSWORD", "")
ODOO_LIMIT = int(get_env("ODOO_LIMIT", "30"))


class OdooClient:
    def __init__(
        self,
        url: str | None = None,
        db: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ) -> None:
        self.url = (url or ODOO_URL).rstrip("/")
        self.db = db if db is not None else ODOO_DB
        self.user = user if user is not None else ODOO_USER
        self.password = password if password is not None else ODOO_PASSWORD

        if not self.url:
            raise RuntimeError("Falta la variable de entorno obligatoria: ODOO_URL")
        if not self.db:
            raise RuntimeError("Falta la variable de entorno obligatoria: ODOO_DB")
        if not self.user:
            raise RuntimeError("Falta la variable de entorno obligatoria: ODOO_USER")
        if not self.password:
            raise RuntimeError("Falta la variable de entorno obligatoria: ODOO_PASSWORD")

        self.common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common", allow_none=True)
        self.models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object", allow_none=True)
        self.uid: int | None = None

    @classmethod
    def from_config(cls, url: str, db: str, user: str, password: str) -> "OdooClient":
        return cls(url=url, db=db, user=user, password=password)

    def version(self) -> dict[str, Any]:
        return self.common.version()

    def authenticate(self) -> int:
        uid = self.common.authenticate(self.db, self.user, self.password, {})
        if not uid:
            raise RuntimeError(
                "No se ha podido autenticar en Odoo. "
                "Revisa ODOO_URL, ODOO_DB, ODOO_USER y ODOO_PASSWORD."
            )
        self.uid = uid
        return uid

    def ensure_auth(self) -> int:
        if self.uid is None:
            return self.authenticate()
        return self.uid

    def execute(self, model: str, method: str, *args: Any, **kwargs: Any) -> Any:
        uid = self.ensure_auth()
        return self.models.execute_kw(
            self.db,
            uid,
            self.password,
            model,
            method,
            list(args),
            kwargs or {},
        )

    def fields_get(self, model: str, attributes: list[str] | None = None) -> dict[str, Any]:
        attributes = attributes or [
            "string",
            "type",
            "relation",
            "required",
            "readonly",
            "store",
            "help",
        ]
        return self.execute(model, "fields_get", attributes=attributes)

    def search_count(self, model: str, domain: list[Any] | None = None) -> int:
        return self.execute(model, "search_count", domain or [])

    def search_read(
        self,
        model: str,
        domain: list[Any] | None = None,
        fields: list[str] | None = None,
        limit: int = ODOO_LIMIT,
        order: str = "id desc",
    ) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {"limit": limit, "order": order}
        if fields:
            kwargs["fields"] = fields
        return self.execute(model, "search_read", domain or [], **kwargs)

    def model_exists(self, model: str) -> bool:
        try:
            self.fields_get(model, attributes=["string", "type"])
            return True
        except Exception:
            return False


def safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)


def json_default(obj: Any) -> str:
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return str(obj)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=json_default)


def flatten_value(value: Any) -> Any:
    """
    Convierte valores típicos de Odoo a texto/celda simple.
    - many2one suele venir como [id, "nombre"]
    - many2many suele venir como lista de ids
    """
    if isinstance(value, list):
        if len(value) == 2 and isinstance(value[0], int) and isinstance(value[1], str):
            return value[1]
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, default=json_default)
    return value


def save_csv(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if not records:
        with path.open("w", encoding="utf-8", newline="") as f:
            f.write("")
        return

    fieldnames: list[str] = []
    seen = set()
    for record in records:
        for key in record.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore", delimiter=";")
        writer.writeheader()
        for record in records:
            writer.writerow({k: flatten_value(v) for k, v in record.items()})


def valid_fields(client: OdooClient, model: str, requested_fields: Iterable[str]) -> list[str]:
    fields = client.fields_get(model, attributes=["string", "type"])
    return [f for f in requested_fields if f in fields]


def month_date_range(year: int, month: int) -> tuple[str, str]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start.isoformat(), end.isoformat()


def print_section(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)
