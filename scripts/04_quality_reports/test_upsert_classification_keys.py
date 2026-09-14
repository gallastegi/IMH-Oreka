from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
APP_PATH = ROOT / "apps" / "streamlit" / "prc01_horas_imputadas.py"


def load_app_module():
    spec = importlib.util.spec_from_file_location("prc01_horas_imputadas", APP_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"No se puede cargar {APP_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_series(value):
    assert isinstance(value, pd.Series), type(value)


def main() -> None:
    app = load_app_module()
    columns = app.CLASSIFICATION_COLUMNS
    key_cols = ["project_id", "task_id"]

    duplicated_columns = pd.DataFrame(
        [["P1", "Proyecto 1", "", "Proyecto duplicado"]],
        columns=["project_id", "project_name", "task_id", "project_id"],
    )
    duplicated_key = app.make_key(duplicated_columns, key_cols)
    assert_series(duplicated_key)
    assert duplicated_key.iloc[0] == "P1||"

    empty = pd.DataFrame(columns=columns)
    empty_key = app.make_key(empty, key_cols)
    assert_series(empty_key)
    assert len(empty_key) == 0

    temp_path = ROOT / "logs" / "_tmp_test_upsert_classification_keys.csv"
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(columns=columns).to_csv(temp_path, sep=";", encoding="utf-8-sig", index=False)

    new_rows = pd.DataFrame(
        [
            {
                "project_id": "P1",
                "project_name": "Proyecto 1",
                "task_id": False,
                "task_name": "",
                "grupo_actividad": "Proiektuak",
                "subgrupo": "",
                "active": "TRUE",
                "review_status": "reviewed",
                "comment": "insert project",
                "reviewed_by": "test",
                "reviewed_at": "2026-07-08",
            },
            {
                "project_id": "P2",
                "project_name": "Proyecto 2",
                "task_id": float("nan"),
                "task_name": "",
                "grupo_actividad": "Orokorrak",
                "subgrupo": "",
                "active": "TRUE",
                "review_status": "reviewed",
                "comment": "insert nan task",
                "reviewed_by": "test",
                "reviewed_at": "2026-07-08",
            },
        ],
        columns=columns,
    )
    app.upsert_rows(temp_path, columns, new_rows, key_cols)

    update_rows = pd.DataFrame(
        [
            {
                "project_id": "P1",
                "project_name": "Proyecto 1",
                "task_id": "",
                "task_name": "",
                "grupo_actividad": "Formakuntza",
                "subgrupo": "",
                "active": "TRUE",
                "review_status": "reviewed",
                "comment": "updated project",
                "reviewed_by": "test",
                "reviewed_at": "2026-07-08",
            },
            {
                "project_id": "P2",
                "project_name": "Proyecto 2",
                "task_id": "T1",
                "task_name": "Tarea 1",
                "grupo_actividad": "Proiektuak",
                "subgrupo": "",
                "active": "TRUE",
                "review_status": "reviewed",
                "comment": "insert task",
                "reviewed_by": "test",
                "reviewed_at": "2026-07-08",
            },
        ],
        columns=columns,
    )
    app.upsert_rows(temp_path, columns, update_rows, key_cols)

    output = pd.read_csv(temp_path, sep=";", encoding="utf-8-sig", dtype=str).fillna("")
    output_key = app.make_key(output, key_cols)
    assert_series(output_key)
    assert output_key.duplicated().sum() == 0
    assert len(output) == 3
    assert output.loc[(output["project_id"] == "P1") & (output["task_id"] == ""), "grupo_actividad"].iloc[0] == "Formakuntza"
    assert len(output[(output["project_id"] == "P2") & (output["task_id"] == "")]) == 1
    assert len(output[(output["project_id"] == "P2") & (output["task_id"] == "T1")]) == 1

    temp_path.unlink()
    print("OK test_upsert_classification_keys")


if __name__ == "__main__":
    main()
