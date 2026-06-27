"""Synthetic IPS generator — si1 emit_ips_for_cohort tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from warehouse.decision.ips.sleeves import IpsSleeve
from warehouse.research.risk.models import AssetClass
from warehouse.research.synthetic import (
    COHORT_IDS,
    emit_hnw_fixture,
    emit_ips_for_cohort,
    emit_synthetic_household,
    validate_ips,
)
from warehouse.research.synthetic.cohort import sample_sleeve_weights
from warehouse.research.synthetic.ips_cohort import COHORT_IPS_PRIORS
from warehouse.research.synthetic.models import HouseholdFixture


def _largest_issuer_weight(fixture: HouseholdFixture) -> Decimal:
    nav = fixture.total_nav_usd
    if nav <= 0:
        return Decimal("0")
    by_issuer: dict[str, Decimal] = {}
    for lot in fixture.lots:
        issuer = lot.concentration_issuer or lot.ticker
        mv = lot.quantity * lot.market_price
        by_issuer[issuer] = by_issuer.get(issuer, Decimal("0")) + mv
    return max(by_issuer.values(), default=Decimal("0")) / nav


def _equity_weight(weights: dict[AssetClass, Decimal]) -> Decimal:
    return weights.get(AssetClass.EQUITY, Decimal("0"))


def _equity_target(ips) -> Decimal:
    target = next(
        t for t in ips.allocation_targets if t.asset_class == IpsSleeve.EQUITY
    )
    return target.max_weight


@pytest.mark.parametrize("cohort_id", COHORT_IDS)
def test_emit_ips_deterministic(cohort_id: str) -> None:
    weights = sample_sleeve_weights(cohort_id, seed=42)
    hh_id = f"synthetic-{cohort_id}-s42"
    first = emit_ips_for_cohort(
        cohort_id=cohort_id,
        seed=42,
        household_id=hh_id,
        weights=weights,
    )
    second = emit_ips_for_cohort(
        cohort_id=cohort_id,
        seed=42,
        household_id=hh_id,
        weights=weights,
    )
    assert first == second


@pytest.mark.parametrize("cohort_id", COHORT_IDS)
def test_emit_ips_matches_cohort_priors(cohort_id: str) -> None:
    priors = COHORT_IPS_PRIORS[cohort_id]
    weights = sample_sleeve_weights(cohort_id, seed=7)
    ips = emit_ips_for_cohort(
        cohort_id=cohort_id,
        seed=7,
        household_id=f"synthetic-{cohort_id}-s7",
        weights=weights,
    )
    assert ips.liquidity_tier_min_pct == priors.liquidity_tier_min_pct
    assert ips.turnover_budget_pct == priors.turnover_budget_pct
    assert ips.household_id == f"synthetic-{cohort_id}-s7"
    assert ips.ips_id == f"ips_synthetic-{cohort_id}-s7_v1"
    for target in ips.allocation_targets:
        assert target.min_weight <= target.target_weight <= target.max_weight
        band = priors.allocation_band_pct
        assert target.max_weight - target.min_weight <= band * 2 + Decimal(
            "0.000001"
        )


def test_general_hnw_has_nonzero_headroom() -> None:
    weights = sample_sleeve_weights("general_hnw", seed=1)
    ips = emit_ips_for_cohort(
        cohort_id="general_hnw",
        seed=1,
        household_id="synthetic-general_hnw-s1",
        weights=weights,
    )
    equity = next(
        t for t in ips.allocation_targets if t.asset_class == IpsSleeve.EQUITY
    )
    assert equity.max_weight - equity.min_weight == Decimal("0.10")
    assert ips.concentration_limit_pct == Decimal("0.12")
    assert ips.liquidity_tier_min_pct == Decimal("0.75")


def test_founder_concentration_scales_with_equity_weight() -> None:
    weights = sample_sleeve_weights("founder_executive", seed=11)
    ips = emit_ips_for_cohort(
        cohort_id="founder_executive",
        seed=11,
        household_id="synthetic-founder_executive-s11",
        weights=weights,
    )
    assert Decimal("0.01") <= ips.concentration_limit_pct <= Decimal("0.50")


def test_concentrated_stress_binding_path() -> None:
    seed = 99
    cohort_id = "concentrated_stress"
    weights = sample_sleeve_weights(cohort_id, seed=seed)
    fixture = emit_hnw_fixture(cohort_id=cohort_id, seed=seed, rung=4)
    ips = emit_ips_for_cohort(
        cohort_id=cohort_id,
        seed=seed,
        household_id=fixture.household_id,
        weights=weights,
        rung=4,
    )
    equity_weight = _equity_weight(weights)
    max_equity = _equity_target(ips)
    largest_issuer = _largest_issuer_weight(fixture)
    assert max_equity < equity_weight or ips.concentration_limit_pct < (
        largest_issuer
    )
    assert Decimal("0.20") <= ips.concentration_limit_pct <= Decimal("0.25")


def test_concentrated_stress_equity_band_is_narrow() -> None:
    weights = sample_sleeve_weights("concentrated_stress", seed=3)
    ips = emit_ips_for_cohort(
        cohort_id="concentrated_stress",
        seed=3,
        household_id="synthetic-concentrated_stress-s3",
        weights=weights,
    )
    equity = next(
        t for t in ips.allocation_targets if t.asset_class == IpsSleeve.EQUITY
    )
    assert equity.max_weight - equity.min_weight <= Decimal("0.04")


def test_unknown_cohort_raises() -> None:
    with pytest.raises(KeyError):
        emit_ips_for_cohort(
            cohort_id="unknown",
            seed=0,
            household_id="x",
            weights={AssetClass.EQUITY: Decimal("1")},
        )


def test_empty_weights_raises() -> None:
    with pytest.raises(ValueError, match="no positive sleeve weights"):
        emit_ips_for_cohort(
            cohort_id="general_hnw",
            seed=0,
            household_id="x",
            weights={AssetClass.EQUITY: Decimal("0")},
        )


def test_emit_synthetic_household_general_hnw_passes() -> None:
    bundle = emit_synthetic_household(cohort_id="general_hnw", seed=42, rung=3)
    assert bundle.validation.ok
    assert bundle.ips.household_id == bundle.fixture.household_id
    assert bundle.fixture.asset_portfolio is not None
    assert not bundle.validation.binding_constraints
    assert len(bundle.fixture.provenance.stage_hashes) == 5


def test_concentrated_stress_bundle_has_bindings() -> None:
    bundle = emit_synthetic_household(
        cohort_id="concentrated_stress", seed=99, rung=4
    )
    assert bundle.validation.ok
    assert len(bundle.validation.binding_constraints) >= 1


def test_validate_rejects_mismatched_ips() -> None:
    bundle = emit_synthetic_household(cohort_id="general_hnw", seed=42, rung=3)
    tight_equity = [
        target.model_copy(update={"max_weight": Decimal("0.01")})
        if target.asset_class == IpsSleeve.EQUITY
        else target
        for target in bundle.ips.allocation_targets
    ]
    bad_ips = bundle.ips.model_copy(
        update={"allocation_targets": tight_equity}
    )
    result = validate_ips(bundle.fixture, bad_ips)
    assert not result.ok
    assert result.binding_constraints


def test_validate_rejects_household_mismatch() -> None:
    bundle = emit_synthetic_household(cohort_id="general_hnw", seed=42, rung=3)
    bad_ips = bundle.ips.model_copy(update={"household_id": "wrong-household"})
    result = validate_ips(bundle.fixture, bad_ips)
    assert not result.ok
    assert "household_id mismatch" in result.warnings[0]
