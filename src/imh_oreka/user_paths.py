from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path


def user_output_directory(
    *,
    home: Path | None = None,
    environment: Mapping[str, str] | None = None,
) -> Path:
    values = os.environ if environment is None else environment
    configured = values.get("IMH_OREKA_OUTPUT_DIR", "").strip()
    if configured:
        return Path(os.path.expandvars(configured)).expanduser()
    return (home or Path.home()) / "Documents" / "IMH-Oreka"


def user_reports_directory(
    *,
    home: Path | None = None,
    environment: Mapping[str, str] | None = None,
) -> Path:
    return user_output_directory(home=home, environment=environment) / "informes"
