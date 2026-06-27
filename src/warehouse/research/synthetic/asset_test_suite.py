"""Risk asset test suite — Phase A (singles) and Phase B (combinations).

Walk HNW leaf types through ``evaluate_risk``, write per-cell JSON
reports under ``runs/research/risk_asset_tests/``, return suite results.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from warehouse.config import repo_root
from warehouse.research.risk.api import risk_result_to_json
from warehouse.research.risk.models import (
    RiskHorizon,
    RiskRequest,
    RiskResult,
    ScenarioSet,
)
from warehouse.research.risk.service import evaluate_risk
from warehouse.research.synthetic.hnw_asset_types import (
    HNW_ASSET_TYPES,
    HnwAssetType,
    IpsExcludedError,
)
from warehouse.research.synthetic.hnw_manifest import (
    build_manifest_from_hnw_types,
)
from warehouse.research.synthetic.stress_harness import (
    HarnessCell,
    HarnessStatus,
    iter_hnw_combinations,
    summarize_matrix,
)

AssetTestPhase = Literal["A", "B"]


class AssetTestCellResult(BaseModel):
    types: list[str]
    combination_size: int
    status: HarnessStatus
    fingerprint: str | None = None
    annualized_vol: Decimal | None = None
    error: str | None = None
    report_path: str | None = None


class AssetTestSuiteResult(BaseModel):
    phase: AssetTestPhase
    cells_run: int
    summary: dict[str, int]
    reports_dir: str
    cells: list[AssetTestCellResult] = Field(default_factory=list)


def default_asset_test_dir() -> Path:
    return repo_root() / "runs" / "research" / "risk_asset_tests"


def _cell_filename(types: tuple[str, ...]) -> str:
    return "__".join(types) + ".json"


def _evaluate_cell(
    types: tuple[HnwAssetType, ...],
    request: RiskRequest,
) -> tuple[HarnessCell, RiskResult | None]:
    type_names = tuple(t.value for t in types)
    try:
        manifest = build_manifest_from_hnw_types(types)
        result = evaluate_risk(request, manifest)
        vol = result.report.level_1_portfolio.annualized_volatility.value
        cell = HarnessCell(
            types=type_names,
            combination_size=len(types),
            status="ok",
            fingerprint=result.report.input_fingerprint,
            annualized_vol=vol,
        )
        return cell, result
    except IpsExcludedError as err:
        return (
            HarnessCell(
                types=type_names,
                combination_size=len(types),
                status="ips_excluded",
                error=str(err),
            ),
            None,
        )
    except Exception as err:  # noqa: BLE001 — suite records all failures
        return (
            HarnessCell(
                types=type_names,
                combination_size=len(types),
                status="error",
                error=f"{type(err).__name__}: {err}",
            ),
            None,
        )


def _write_cell_report(
    path: Path,
    cell: HarnessCell,
    result: RiskResult | None,
) -> None:
    payload: dict[str, object] = {
        "types": list(cell.types),
        "combination_size": cell.combination_size,
        "status": cell.status,
        "fingerprint": cell.fingerprint,
        "annualized_vol": (
            str(cell.annualized_vol)
            if cell.annualized_vol is not None
            else None
        ),
        "error": cell.error,
    }
    if result is not None:
        payload["risk_eval"] = risk_result_to_json(result)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _path_for_report(path: Path) -> str:
    try:
        return str(path.relative_to(repo_root()))
    except ValueError:
        return str(path)


def _cell_result(
    cell: HarnessCell, report_path: Path | None
) -> AssetTestCellResult:
    rel = _path_for_report(report_path) if report_path is not None else None
    return AssetTestCellResult(
        types=list(cell.types),
        combination_size=cell.combination_size,
        status=cell.status,
        fingerprint=cell.fingerprint,
        annualized_vol=cell.annualized_vol,
        error=cell.error,
        report_path=rel,
    )


def run_asset_test_suite(
    phase: AssetTestPhase,
    *,
    request: RiskRequest | None = None,
    reports_dir: Path | None = None,
    phase_b_max_size: int | None = None,
) -> AssetTestSuiteResult:
    """Run Phase A (singles) or Phase B (combinations size ≥ 2)."""
    req = request or RiskRequest(
        horizon=RiskHorizon.parse("5y"),
        run_scenarios=ScenarioSet.NONE,
    )
    root = reports_dir or default_asset_test_dir()
    phase_dir = root / f"phase_{phase.lower()}"
    phase_dir.mkdir(parents=True, exist_ok=True)

    if phase == "A":
        combo_list: list[tuple[HnwAssetType, ...]] = [
            (t,) for t in HNW_ASSET_TYPES
        ]
    else:
        combo_list = list(
            iter_hnw_combinations(
                min_size=2,
                max_size=phase_b_max_size,
            )
        )

    cells: list[AssetTestCellResult] = []
    harness_cells: list[HarnessCell] = []
    for combo in combo_list:
        cell, result = _evaluate_cell(combo, req)
        harness_cells.append(cell)
        report_path = phase_dir / _cell_filename(cell.types)
        _write_cell_report(report_path, cell, result)
        cells.append(_cell_result(cell, report_path))

    summary = summarize_matrix(harness_cells)
    suite = AssetTestSuiteResult(
        phase=phase,
        cells_run=len(cells),
        summary=summary,
        reports_dir=_path_for_report(phase_dir),
        cells=cells,
    )
    summary_path = root / f"phase_{phase.lower()}_summary.json"
    summary_path.write_text(suite.model_dump_json(indent=2) + "\n")
    return suite


def load_asset_test_summary(
    phase: AssetTestPhase,
    *,
    reports_dir: Path | None = None,
) -> AssetTestSuiteResult | None:
    root = reports_dir or default_asset_test_dir()
    path = root / f"phase_{phase.lower()}_summary.json"
    if not path.is_file():
        return None
    return AssetTestSuiteResult.model_validate_json(path.read_text())
