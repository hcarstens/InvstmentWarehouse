"""st6c — reporting-plane tax scenario falsifiers (ST2 independent oracles).

Coverage floor is an amber badge only (¬QA6) — pass/fail is pytest verdict.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from warehouse.config import get_settings
from warehouse.data.ledger.views import LotPositionView
from warehouse.data.security_master import AssetClass
from warehouse.decision.tax.scenarios import TaxScenarioOverlays
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID
from warehouse.reporting.tax import (
    ReportingTaxResult,
    compute_reporting_tax_scenario,
    holding_period_rate,
    run_reporting_tax_scenario,
    tax_on_realized_gain,
)

AS_OF = date(2026, 6, 24)


# --- independent oracles (ST2) -----------------------------------------------


def _oracle_holding_rate(days: int, settings) -> Decimal:  # type: ignore[no-untyped-def]
    rate = settings.fed_ltcg_rate if days >= 365 else settings.fed_stcg_rate
    return Decimal(str(rate))


def _oracle_gain_tax(
    gain: Decimal,
    days: int,
    *,
    apply_niit: bool,
    settings,
) -> Decimal:
    rate = _oracle_holding_rate(days, settings)
    tax = gain * rate
    if apply_niit and gain > Decimal("0"):
        tax += gain * Decimal(str(settings.niit_rate))
    return tax


def _lot(
    *,
    lot_id: str,
    gain: Decimal,
    acq: date,
) -> LotPositionView:
    cost = Decimal("1000")
    mv = cost + gain
    return LotPositionView(
        lot_id=lot_id,
        account_id="acct_test",
        account_name="Test",
        security_id="sec_test",
        ticker="TST",
        security_name="Test",
        security_asset_class=AssetClass.EQUITY,
        liquidity_tier=1,
        quantity=Decimal("1"),
        cost_basis_per_share=cost,
        total_cost_basis=cost,
        market_price=mv,
        market_value=mv,
        unrealized_gain=gain,
        acquisition_date=acq,
        is_restricted=False,
        wash_sale_substitute_group=None,
    )


# --- falsifiers --------------------------------------------------------------


def test_holding_period_rate_stcg_at_364_days() -> None:
    settings = get_settings()
    acq = date(2025, 1, 1)
    as_of = acq + timedelta(days=364)
    assert (as_of - acq).days == 364
    expected = _oracle_holding_rate(364, settings)
    assert holding_period_rate(acq, as_of, settings) == expected
    assert holding_period_rate(acq, as_of, settings) == Decimal(
        str(settings.fed_stcg_rate)
    )


def test_holding_period_rate_ltcg_at_365_days() -> None:
    settings = get_settings()
    acq = date(2025, 1, 1)
    as_of = acq + timedelta(days=365)
    assert (as_of - acq).days == 365
    expected = _oracle_holding_rate(365, settings)
    assert holding_period_rate(acq, as_of, settings) == expected
    assert holding_period_rate(acq, as_of, settings) == Decimal(
        str(settings.fed_ltcg_rate)
    )


def test_niit_overlay_increases_scenario_tax() -> None:
    settings = get_settings()
    gain = Decimal("50000")
    stcg_lot = _lot(
        lot_id="lot_stcg",
        gain=gain,
        acq=date(2026, 1, 1),
    )
    baseline_oracle = _oracle_gain_tax(
        gain,
        (AS_OF - stcg_lot.acquisition_date).days,
        apply_niit=False,
        settings=settings,
    )
    scenario_oracle = _oracle_gain_tax(
        gain,
        (AS_OF - stcg_lot.acquisition_date).days,
        apply_niit=True,
        settings=settings,
    )
    baseline, scenario, delta = compute_reporting_tax_scenario(
        [stcg_lot],
        TaxScenarioOverlays(apply_niit=True),
        as_of=AS_OF,
        settings=settings,
    )
    assert baseline == baseline_oracle
    assert scenario == scenario_oracle
    assert delta == scenario_oracle - baseline_oracle
    assert delta > Decimal("0")


def test_zero_gain_zero_liability() -> None:
    settings = get_settings()
    flat = _lot(lot_id="flat", gain=Decimal("0"), acq=date(2020, 1, 1))
    baseline, scenario, delta = compute_reporting_tax_scenario(
        [flat],
        TaxScenarioOverlays(apply_niit=True),
        as_of=AS_OF,
        settings=settings,
    )
    assert baseline == Decimal("0")
    assert scenario == Decimal("0")
    assert delta == Decimal("0")


def test_tax_on_realized_loss_reduces_liability() -> None:
    settings = get_settings()
    loss = Decimal("-2000")
    rate = Decimal(str(settings.fed_stcg_rate))
    expected = loss * rate
    assert (
        tax_on_realized_gain(
            loss,
            rate,
            apply_niit=True,
            settings=settings,
        )
        == expected
    )
    assert expected < Decimal("0")


def test_run_reporting_tax_scenario_persists() -> None:
    with session_scope() as session:
        result = run_reporting_tax_scenario(
            session,
            DEMO_HOUSEHOLD_ID,
            scenario_name="st6c_niit",
            overlays=TaxScenarioOverlays(apply_niit=True),
            as_of=AS_OF,
        )
        session.commit()
    assert isinstance(result, ReportingTaxResult)
    assert result.baseline_tax >= Decimal("0")
    assert result.scenario_tax >= result.baseline_tax


def test_reporting_tax_empty_household_raises() -> None:
    with session_scope() as session:
        with pytest.raises(ValueError, match="No positions"):
            run_reporting_tax_scenario(
                session,
                "hh_empty_tax",
                scenario_name="empty",
            )
