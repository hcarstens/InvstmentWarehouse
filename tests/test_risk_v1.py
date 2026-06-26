"""Risk API v1 — overlays, deltas, rungs 3–4."""

from __future__ import annotations

from decimal import Decimal

import pytest

from warehouse.research.risk.assumptions import build_assumptions
from warehouse.research.risk.models import (
    AssetClass,
    ManifestOverlay,
    RiskHorizon,
    RiskRequest,
)
from warehouse.research.risk.overlay import apply_overlay, diff_reports
from warehouse.research.risk.service import evaluate_risk
from warehouse.research.risk.synthetic import rung


def test_apply_overlay_renormalizes_weights() -> None:
    portfolio = rung(1)
    overlay = ManifestOverlay(
        label="tilt to bonds",
        weight_tilts={
            AssetClass.EQUITY: Decimal("-0.10"),
            AssetClass.FIXED_INCOME: Decimal("0.10"),
        },
    )
    derived = apply_overlay(portfolio, overlay)
    total = sum(slot.weight for slot in derived.allocations)
    assert total == Decimal("1")
    equity = next(
        s for s in derived.allocations if s.asset_class == AssetClass.EQUITY
    )
    assert equity.weight < Decimal("0.6")


def test_evaluate_risk_overlay_produces_deltas() -> None:
    portfolio = rung(1)
    request = RiskRequest(
        horizon=RiskHorizon.parse("5y"),
        overlay=ManifestOverlay(
            label="de-risk",
            weight_tilts={
                AssetClass.EQUITY: Decimal("-0.15"),
                AssetClass.FIXED_INCOME: Decimal("0.15"),
            },
        ),
    )
    result = evaluate_risk(request, portfolio)
    assert result.deltas is not None
    assert result.deltas.overlay_label == "de-risk"
    assert (
        result.deltas.baseline_fingerprint
        != result.deltas.proposed_fingerprint
    )
    vol_delta = next(
        row
        for row in result.deltas.headline
        if row.metric == "annualized_volatility"
    )
    assert vol_delta.proposed < vol_delta.baseline


def test_founder_executive_concentration_overlay() -> None:
    """SDG2-style negation: concentrated rung 4 + equity reduction overlay."""
    portfolio = rung(4)
    overlay = ManifestOverlay(
        label="founder_executive de-concentrate",
        weight_tilts={
            AssetClass.EQUITY: Decimal("-0.20"),
            AssetClass.FIXED_INCOME: Decimal("0.20"),
        },
    )
    result = evaluate_risk(
        RiskRequest(horizon=RiskHorizon.parse("5y"), overlay=overlay),
        portfolio,
    )
    assert result.deltas is not None
    assert "equity" in result.deltas.by_class_variance_delta


def test_assumptions_override_changes_vol() -> None:
    portfolio = rung(0)
    base = evaluate_risk(
        RiskRequest(horizon=RiskHorizon.parse("5y")), portfolio
    )
    custom = build_assumptions(
        regime="research_sweep",
        class_annual_vol={AssetClass.EQUITY: Decimal("0.32")},
    )
    swept = evaluate_risk(
        RiskRequest(horizon=RiskHorizon.parse("5y")),
        portfolio,
        assumptions=custom,
    )
    assert (
        swept.report.level_1_portfolio.annualized_volatility.value
        > base.report.level_1_portfolio.annualized_volatility.value
    )


def test_overlay_negative_weight_raises() -> None:
    portfolio = rung(0)
    overlay = ManifestOverlay(
        weight_tilts={AssetClass.EQUITY: Decimal("-1.5")},
    )
    with pytest.raises(ValueError, match="negative weight"):
        apply_overlay(portfolio, overlay)


def test_rung_3_has_fermi_alts_and_five_sleeves() -> None:
    portfolio = rung(3, seed=0)
    assert portfolio.complexity == 3
    assert portfolio.cohort_id == "general_hnw"
    assert portfolio.generator_version is not None
    alts = next(
        s
        for s in portfolio.allocations
        if s.asset_class == AssetClass.ALTERNATIVES
    )
    assert alts.liquidity_tier == 3
    assert alts.measurement.value == "fermi"


def test_rung_4_concentrated_equity() -> None:
    portfolio = rung(4, seed=0)
    assert portfolio.cohort_id == "concentrated_stress"
    equity = next(
        s for s in portfolio.allocations if s.asset_class == AssetClass.EQUITY
    )
    assert equity.weight > Decimal("0.6")


def test_diff_reports_headline_metrics() -> None:
    from warehouse.research.risk.engine import evaluate_portfolio_risk

    portfolio = rung(1)
    horizon = RiskHorizon.parse("5y")
    baseline = evaluate_risk(RiskRequest(horizon=horizon), portfolio).report
    overlay = ManifestOverlay(
        weight_tilts={
            AssetClass.EQUITY: Decimal("-0.10"),
            AssetClass.FIXED_INCOME: Decimal("0.10"),
        },
    )
    derived = apply_overlay(portfolio, overlay)
    proposed = evaluate_portfolio_risk(derived, horizon)
    deltas = diff_reports(baseline, proposed, overlay_label="tilt")
    assert len(deltas.headline) >= 3
    assert deltas.overlay_label == "tilt"
