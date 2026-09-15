from __future__ import annotations

from pathlib import Path

from imh_oreka.user_paths import user_output_directory, user_reports_directory


def test_default_output_directory_is_under_user_documents() -> None:
    home = Path("C:/Users/persona-ejemplo")
    assert user_output_directory(home=home, environment={}) == home / "Documents" / "IMH-Oreka"
    assert user_reports_directory(home=home, environment={}) == home / "Documents" / "IMH-Oreka" / "informes"


def test_output_directory_can_be_overridden() -> None:
    configured = Path("D:/IMH-Oreka-Datos")
    environment = {"IMH_OREKA_OUTPUT_DIR": str(configured)}
    assert user_output_directory(environment=environment) == configured
    assert user_reports_directory(environment=environment) == configured / "informes"
