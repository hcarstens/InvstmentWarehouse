"""Risk dashboard panel tests."""

from decimal import Decimal

from warehouse.dashboard.render_risk import render_risk_section
from warehouse.dashboard.risk_data import load_risk_dashboard
from warehouse.research.risk.portfolio_builder import (
    build_portfolio_from_holdings,
)


def test_load_risk_dashboard_from_demo_holdings() -> None:
    risk = load_risk_dashboard()
    assert risk.error is None
    assert risk.report is not None
    assert risk.source == "ledger"
    assert risk.report.level_1_portfolio.parametric_var.confidence == Decimal(
        "0.95"
    )
    assert len(risk.report.level_2_contributions.by_class) >= 2
    assert len(risk.report.level_4_stress.scenarios) == 3


def test_render_risk_section_includes_levels() -> None:
    risk = load_risk_dashboard()
    html = render_risk_section(risk)
    assert "Level 1" in html
    assert "Level 2" in html
    assert "Level 3" in html
    assert "Level 4" in html
    assert "2022_inflation" in html
    assert risk.report is not None
    assert risk.report.input_fingerprint in html


def test_render_risk_section_includes_deltas_when_overlay_enabled() -> None:
    risk = load_risk_dashboard()
    html = render_risk_section(risk)
    if risk.deltas is not None:
        assert "Proposal deltas" in html
        assert "annualized_volatility" in html


def test_portfolio_builder_maps_bnd_and_alts() -> None:
    from datetime import date

    from warehouse.data.alternatives.service import AlternativeHoldingView
    from warehouse.data.ledger.views import LotPositionView
    from warehouse.research.risk.models import AssetClass

    positions = [
        LotPositionView(
            lot_id="l1",
            account_id="a1",
            account_name="Acct",
            security_id="s1",
            ticker="VTI",
            security_name="VTI",
            quantity=Decimal("10"),
            cost_basis_per_share=Decimal("100"),
            total_cost_basis=Decimal("1000"),
            market_price=Decimal("100"),
            market_value=Decimal("1000"),
            unrealized_gain=Decimal("0"),
            acquisition_date=date(2024, 1, 1),
            is_restricted=False,
            wash_sale_substitute_group=None,
        ),
        LotPositionView(
            lot_id="l2",
            account_id="a1",
            account_name="Acct",
            security_id="s2",
            ticker="BND",
            security_name="BND",
            quantity=Decimal("10"),
            cost_basis_per_share=Decimal("50"),
            total_cost_basis=Decimal("500"),
            market_price=Decimal("50"),
            market_value=Decimal("500"),
            unrealized_gain=Decimal("0"),
            acquisition_date=date(2024, 1, 1),
            is_restricted=False,
            wash_sale_substitute_group=None,
        ),
    ]
    alts = [
        AlternativeHoldingView(
            holding_id="alt1",
            household_id="hh",
            entity_id="ent",
            name="PE",
            asset_type="private_equity",
            committed_capital=Decimal("100000"),
            called_capital=Decimal("50000"),
            current_nav=Decimal("500"),
            last_mark_date=date(2026, 1, 1),
        )
    ]
    portfolio = build_portfolio_from_holdings("hh", positions, alts)
    classes = {slot.asset_class for slot in portfolio.allocations}
    assert AssetClass.EQUITY in classes
    assert AssetClass.FIXED_INCOME in classes
    assert AssetClass.ALTERNATIVES in classes
    total = sum(slot.weight for slot in portfolio.allocations)
    assert total == Decimal("1")
