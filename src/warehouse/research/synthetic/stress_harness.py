"""Combinatorial HNW leaf-type stress harness → ``evaluate_risk``.

Walks subsets of the 15 HNW asset types (size 1, then 2, then 3, …) and records
a structured outcome per cell. No database required for risk-only
falsification.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from warehouse.research.risk.models import (
    RiskHorizon,
    RiskRequest,
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

HarnessStatus = Literal["ok", "ips_excluded", "error"]


@dataclass(frozen=True)
class HarnessCell:
    """One combinatorial cell: leaf types → risk API outcome."""

    types: tuple[str, ...]
    combination_size: int
    status: HarnessStatus
    fingerprint: str | None = None
    annualized_vol: Decimal | None = None
    error: str | None = None


def iter_hnw_combinations(
    *,
    max_size: int | None = None,
    min_size: int = 1,
) -> Iterator[tuple[HnwAssetType, ...]]:
    """Yield sorted leaf-type tuples from ``min_size`` up to ``max_size``."""
    upper = max_size if max_size is not None else len(HNW_ASSET_TYPES)
    for k in range(min_size, upper + 1):
        yield from itertools.combinations(HNW_ASSET_TYPES, k)


def run_harness_cell(
    types: tuple[HnwAssetType, ...],
    request: RiskRequest | None = None,
) -> HarnessCell:
    """Evaluate one combination; never raises — outcome in ``HarnessCell``."""
    type_names = tuple(t.value for t in types)
    req = request or RiskRequest(
        horizon=RiskHorizon.parse("5y"),
        run_scenarios=ScenarioSet.NONE,
    )
    try:
        manifest = build_manifest_from_hnw_types(types)
        result = evaluate_risk(req, manifest)
        vol = result.report.level_1_portfolio.annualized_volatility.value
        return HarnessCell(
            types=type_names,
            combination_size=len(types),
            status="ok",
            fingerprint=result.report.input_fingerprint,
            annualized_vol=vol,
        )
    except IpsExcludedError as err:
        return HarnessCell(
            types=type_names,
            combination_size=len(types),
            status="ips_excluded",
            error=str(err),
        )
    except Exception as err:  # noqa: BLE001 — harness records all failures
        return HarnessCell(
            types=type_names,
            combination_size=len(types),
            status="error",
            error=f"{type(err).__name__}: {err}",
        )


def run_combination_matrix(
    *,
    max_size: int | None = None,
    min_size: int = 1,
    request: RiskRequest | None = None,
) -> list[HarnessCell]:
    """Run all combinations in ``[min_size, max_size]``.

    Default: full 2^15−1 matrix.
    """
    return [
        run_harness_cell(combo, request)
        for combo in iter_hnw_combinations(
            max_size=max_size,
            min_size=min_size,
        )
    ]


def summarize_matrix(cells: list[HarnessCell]) -> dict[str, int]:
    """Count outcomes by status."""
    counts: dict[str, int] = {"ok": 0, "ips_excluded": 0, "error": 0}
    for cell in cells:
        counts[cell.status] = counts.get(cell.status, 0) + 1
    return counts
