from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from imh_oreka.operational_performance import (  # noqa: E402
    ACTUALS_DETAIL_FILE,
    OPERATIONAL_DETAIL_FILE,
    PLANNING_DETAIL_FILE,
    apply_management_classification,
    build_operational_performance_dataset,
    read_csv,
    write_operational_diagnostics,
)


def build_operational_dataset(
    planning_path: Path = PLANNING_DETAIL_FILE,
    actuals_path: Path = ACTUALS_DETAIL_FILE,
    output_path: Path = OPERATIONAL_DETAIL_FILE,
) -> dict[str, object]:
    if not planning_path.exists():
        raise FileNotFoundError(f"No existe el dataset de planificacion: {planning_path}")
    if not actuals_path.exists():
        raise FileNotFoundError(f"No existe el dataset de horas reales: {actuals_path}")

    planning_raw = apply_management_classification(read_csv(planning_path))
    actuals_raw = apply_management_classification(read_csv(actuals_path))
    result = build_operational_performance_dataset(
        planning_raw,
        actuals_raw,
        organization_people=None,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.detail.to_csv(output_path, sep=";", encoding="utf-8-sig", index=False)
    write_operational_diagnostics(result)

    metadata = {
        "detail_path": str(output_path.relative_to(ROOT_DIR)),
        "planning_path": str(planning_path.relative_to(ROOT_DIR)),
        "actuals_path": str(actuals_path.relative_to(ROOT_DIR)),
        "rows": int(len(result.detail)),
        "planning_rows": int(result.diagnostics["planning_rows"]),
        "actual_rows": int(result.diagnostics["actual_rows"]),
        "planning_hours": float(result.diagnostics["planning_hours"]),
        "actual_hours": float(result.diagnostics["actual_hours"]),
        "matched_actual_hours": float(result.diagnostics["matched_actual_hours"]),
        "unmatched_actual_hours": float(result.diagnostics["unmatched_actual_hours"]),
        "conflicts": int(result.diagnostics["conflicts"]),
        "generated_at": result.diagnostics["generated_at"],
    }
    metadata_path = output_path.with_suffix(".metadata.json")
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Construye el dataset PRC-01 de rendimiento operativo.")
    parser.add_argument("--planning", type=Path, default=PLANNING_DETAIL_FILE)
    parser.add_argument("--actuals", type=Path, default=ACTUALS_DETAIL_FILE)
    parser.add_argument("--output", type=Path, default=OPERATIONAL_DETAIL_FILE)
    args = parser.parse_args()
    result = build_operational_dataset(args.planning, args.actuals, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
