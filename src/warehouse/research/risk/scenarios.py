"""Risk-owned scenario catalog — base/high/low with PSD validation."""

from __future__ import annotations

from decimal import Decimal

import numpy as np

from warehouse.research.risk.assumptions import (
    RiskAssumptions,
    build_assumptions,
)
from warehouse.research.risk.models import AssetClass

HIGH_VOL_MULTIPLIER = Decimal("1.4")
LOW_VOL_MULTIPLIER = Decimal("0.85")
HIGH_ES_MULTIPLIER = Decimal("1.15")
LOW_ES_MULTIPLIER = Decimal("0.90")
CRISIS_CORRELATION = Decimal("0.85")
CRISIS_BLEND = Decimal("0.80")
BENIGN_CORRELATION_SCALE = Decimal("0.50")

_CATALOG: dict[str, RiskAssumptions] = {}


def _scale_vols(
    vols: dict[AssetClass, Decimal],
    multiplier: Decimal,
) -> dict[AssetClass, Decimal]:
    return {asset: vol * multiplier for asset, vol in vols.items()}


def _transform_correlations(
    correlations: dict[frozenset[AssetClass], Decimal],
    default: Decimal,
    *,
    crisis: bool,
) -> tuple[dict[frozenset[AssetClass], Decimal], Decimal]:
    if crisis:

        def transform(rho: Decimal) -> Decimal:
            return rho + (CRISIS_CORRELATION - rho) * CRISIS_BLEND
    else:

        def transform(rho: Decimal) -> Decimal:
            return rho * BENIGN_CORRELATION_SCALE

    transformed = {pair: transform(rho) for pair, rho in correlations.items()}
    new_default = transform(default)
    return transformed, new_default


def _scale_es_multipliers(
    multipliers: dict[str, Decimal],
    factor: Decimal,
) -> dict[str, Decimal]:
    return {key: value * factor for key, value in multipliers.items()}


def _correlation_matrix(assumptions: RiskAssumptions) -> np.ndarray:
    classes = list(AssetClass)
    size = len(classes)
    matrix = np.eye(size, dtype=np.float64)
    for i, left in enumerate(classes):
        for j, right in enumerate(classes):
            if i >= j:
                continue
            rho = float(assumptions.pairwise_correlation(left, right))
            matrix[i, j] = rho
            matrix[j, i] = rho
    return matrix


def validate_correlation_psd(assumptions: RiskAssumptions) -> None:
    matrix = _correlation_matrix(assumptions)
    eigenvalues = np.linalg.eigvalsh(matrix)
    min_eval = float(np.min(eigenvalues))
    if min_eval < -1e-8:
        raise ValueError(
            f"{assumptions.regime} correlation matrix not PSD: "
            f"min eigenvalue {min_eval:.6f}"
        )


def _register(assumptions: RiskAssumptions) -> RiskAssumptions:
    validate_correlation_psd(assumptions)
    _CATALOG[assumptions.regime] = assumptions
    return assumptions


def assumptions_for(name: str) -> RiskAssumptions:
    if name not in _CATALOG:
        raise KeyError(f"unknown assumption regime: {name}")
    return _CATALOG[name]


def scenario_names() -> tuple[str, ...]:
    return tuple(_CATALOG.keys())


def _build_high_risk(base: RiskAssumptions) -> RiskAssumptions:
    correlations, default = _transform_correlations(
        base.class_correlations,
        base.default_class_correlation,
        crisis=True,
    )
    return build_assumptions(
        regime="high_risk",
        class_annual_vol=_scale_vols(
            base.class_annual_vol, HIGH_VOL_MULTIPLIER
        ),
        class_correlations=correlations,
        default_class_correlation=default,
        es_multipliers=_scale_es_multipliers(
            base.es_multipliers, HIGH_ES_MULTIPLIER
        ),
    )


def _build_low_risk(base: RiskAssumptions) -> RiskAssumptions:
    correlations, default = _transform_correlations(
        base.class_correlations,
        base.default_class_correlation,
        crisis=False,
    )
    return build_assumptions(
        regime="low_risk",
        class_annual_vol=_scale_vols(
            base.class_annual_vol, LOW_VOL_MULTIPLIER
        ),
        class_correlations=correlations,
        default_class_correlation=default,
        es_multipliers=_scale_es_multipliers(
            base.es_multipliers, LOW_ES_MULTIPLIER
        ),
    )


_BASE = _register(build_assumptions())
_register(_build_high_risk(_BASE))
_register(_build_low_risk(_BASE))
