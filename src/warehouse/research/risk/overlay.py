"""Manifest overlays and report deltas (v1)."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from warehouse.research.risk.models import (
    AllocationSlot,
    AssetClass,
    AssetPortfolio,
    ManifestOverlay,
    MetricDelta,
    PortfolioRiskReport,
    RiskDeltas,
)


def apply_overlay(
    manifest: AssetPortfolio,
    overlay: ManifestOverlay,
) -> AssetPortfolio:
    """Apply overlay tilts/adds/drops and re-normalize weights to 1."""
    weights: dict[AssetClass, Decimal] = defaultdict(Decimal)
    slot_templates: dict[AssetClass, AllocationSlot] = {}

    for slot in manifest.allocations:
        weights[slot.asset_class] += slot.weight
        slot_templates.setdefault(slot.asset_class, slot)

    for asset_class in overlay.drop_sleeves:
        weights.pop(asset_class, None)
        slot_templates.pop(asset_class, None)

    for slot in overlay.add_sleeves:
        weights[slot.asset_class] += slot.weight
        slot_templates[slot.asset_class] = slot

    for asset_class, tilt in overlay.weight_tilts.items():
        weights[asset_class] = weights.get(asset_class, Decimal("0")) + tilt

    for asset_class, weight in weights.items():
        if weight < 0:
            raise ValueError(
                f"overlay produced negative weight for {asset_class.value}: {weight}"
            )

    total = sum(weights.values(), Decimal("0"))
    if total <= 0:
        raise ValueError("overlay produced zero total weight")

    allocations: list[AllocationSlot] = []
    for asset_class in sorted(weights, key=lambda ac: ac.value):
        normalized = weights[asset_class] / total
        template = slot_templates.get(asset_class)
        if template is not None:
            allocations.append(template.model_copy(update={"weight": normalized}))
        else:
            allocations.append(
                AllocationSlot(asset_class=asset_class, weight=normalized)
            )

    return manifest.model_copy(update={"allocations": allocations})


def _pct_change(baseline: Decimal, proposed: Decimal) -> Decimal | None:
    if baseline == 0:
        return None
    return (proposed - baseline) / baseline


def _metric_delta(
    metric: str,
    baseline: Decimal,
    proposed: Decimal,
) -> MetricDelta:
    return MetricDelta(
        metric=metric,
        baseline=baseline,
        proposed=proposed,
        delta=proposed - baseline,
        pct_change=_pct_change(baseline, proposed),
    )


def diff_reports(
    baseline: PortfolioRiskReport,
    proposed: PortfolioRiskReport,
    *,
    overlay_label: str | None = None,
) -> RiskDeltas:
    """Diff baseline vs proposed Level 1 headline metrics and Level 2 variance shares."""
    b1 = baseline.level_1_portfolio
    p1 = proposed.level_1_portfolio
    headline = [
        _metric_delta(
            "annualized_volatility",
            b1.annualized_volatility.value,
            p1.annualized_volatility.value,
        ),
        _metric_delta(
            "parametric_var",
            b1.parametric_var.value,
            p1.parametric_var.value,
        ),
        _metric_delta(
            "parametric_es",
            b1.parametric_es.value,
            p1.parametric_es.value,
        ),
    ]
    if b1.dollar_var and p1.dollar_var:
        headline.append(
            _metric_delta("dollar_var", b1.dollar_var.value, p1.dollar_var.value)
        )
    if b1.dollar_es and p1.dollar_es:
        headline.append(
            _metric_delta("dollar_es", b1.dollar_es.value, p1.dollar_es.value)
        )

    baseline_var = {
        row.asset_class: row.pct_variance_contribution
        for row in baseline.level_2_contributions.by_class
    }
    proposed_var = {
        row.asset_class: row.pct_variance_contribution
        for row in proposed.level_2_contributions.by_class
    }
    by_class_variance_delta = {
        asset_class: proposed_var.get(asset_class, Decimal("0")) - baseline_var.get(
            asset_class, Decimal("0")
        )
        for asset_class in set(baseline_var) | set(proposed_var)
    }

    return RiskDeltas(
        overlay_label=overlay_label,
        baseline_fingerprint=baseline.input_fingerprint,
        proposed_fingerprint=proposed.input_fingerprint,
        headline=headline,
        by_class_variance_delta=by_class_variance_delta,
    )
