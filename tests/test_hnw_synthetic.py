"""HNW compositional synthetic generator — v1.1 tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from warehouse.research.risk.models import AssetClass, RiskHorizon, RiskRequest
from warehouse.research.risk.service import evaluate_risk
from warehouse.research.risk.synthetic import rung
from warehouse.research.synthetic import (
    COHORT_IDS,
    emit_hnw_fixture,
    emit_synthetic_household,
    project_to_asset_portfolio,
)
from warehouse.research.synthetic.cohort import sample_sleeve_weights
from warehouse.research.synthetic.scenario_card import build_scenario_card


def test_emit_fixture_reconciles_lot_nav_to_total() -> None:
    fixture = emit_hnw_fixture(cohort_id="general_hnw", seed=42, rung=3)
    lot_nav = sum(lot.quantity * lot.market_price for lot in fixture.lots)
    alt_nav = sum(alt.current_nav for alt in fixture.alternative_holdings)
    assert fixture.total_nav_usd == lot_nav + alt_nav


def test_shape_a_weights_sum_to_one() -> None:
    fixture = emit_hnw_fixture(cohort_id="general_hnw", seed=7, rung=3)
    shape_a = project_to_asset_portfolio(fixture)
    total = sum(slot.weight for slot in shape_a.allocations)
    assert total == Decimal("1")
    assert shape_a.cohort_id == "general_hnw"
    assert shape_a.generator_version is not None
    assert shape_a.seed == 7


def test_cohort_profiles_differ_deterministically() -> None:
    general = sample_sleeve_weights("general_hnw", seed=1)
    stress = sample_sleeve_weights("concentrated_stress", seed=1)
    assert stress[AssetClass.EQUITY] > general[AssetClass.EQUITY]


def test_rung4_has_concentrated_aapl_lots() -> None:
    fixture = emit_hnw_fixture(
        cohort_id="concentrated_stress", seed=99, rung=4
    )
    aapl_lots = [lot for lot in fixture.lots if lot.ticker == "AAPL"]
    assert len(aapl_lots) >= 3
    assert any(lot.is_loss_lot for lot in aapl_lots)
    assert fixture.provenance.tension_tags


def test_rung4_alts_have_scheduled_calls() -> None:
    fixture = emit_hnw_fixture(cohort_id="uhnw_inherited", seed=5, rung=4)
    assert fixture.alternative_holdings
    assert fixture.alternative_holdings[0].scheduled_calls


def test_risk_synthetic_rung3_uses_generator() -> None:
    portfolio = rung(3, seed=11)
    assert portfolio.complexity == 3
    assert portfolio.cohort_id == "general_hnw"
    assert portfolio.generator_version is not None


def test_scenario_card_links_fingerprint() -> None:
    card = build_scenario_card(rung_level=3, seed=3)
    assert card.risk_fingerprint
    assert card.generator_version != "unknown"
    assert card.cohort_id == "general_hnw"


def test_evaluate_risk_rung4_compositional() -> None:
    portfolio = rung(4, seed=0)
    result = evaluate_risk(
        RiskRequest(
            horizon=RiskHorizon.parse("5y"), notional_usd=Decimal("10000000")
        ),
        portfolio,
    )
    assert result.report.level_1_portfolio.annualized_volatility.value > 0


def test_all_cohort_ids_defined() -> None:
    assert "founder_executive" in COHORT_IDS
    for cohort_id in COHORT_IDS:
        weights = sample_sleeve_weights(cohort_id, seed=0)
        assert sum(weights.values(), Decimal("0")) == Decimal("1")


def test_unknown_cohort_raises() -> None:
    with pytest.raises(KeyError):
        sample_sleeve_weights("unknown_cohort", seed=0)


def test_emit_synthetic_household_bundle_coherent() -> None:
    bundle = emit_synthetic_household(cohort_id="general_hnw", seed=42, rung=3)
    assert bundle.validation.ok
    assert bundle.fixture.total_nav_usd > 0
    assert bundle.ips.household_id == bundle.fixture.household_id
    manifest = bundle.fixture.asset_portfolio
    assert manifest is not None
    assert manifest.cohort_id == "general_hnw"
