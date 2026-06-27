"""IPS sleeve rollup — si0a asset-class vocabulary."""

from datetime import date
from decimal import Decimal

from warehouse.data.ledger.views import LotPositionView
from warehouse.data.security_master import AssetClass as SecurityAssetClass
from warehouse.decision.ips import AllocationTarget, InvestmentPolicyStatement
from warehouse.decision.ips.rollup import ips_sleeve_for_position
from warehouse.decision.ips.sleeves import IpsSleeve, parse_ips_sleeve


def _position(
    *,
    ticker: str,
    asset_class: SecurityAssetClass,
    wash_group: str | None = None,
) -> LotPositionView:
    return LotPositionView(
        lot_id=f"lot_{ticker}",
        account_id="acct",
        account_name="Acct",
        security_id=f"sec_{ticker.lower()}",
        ticker=ticker,
        security_name=ticker,
        security_asset_class=asset_class,
        liquidity_tier=1,
        quantity=Decimal("10"),
        cost_basis_per_share=Decimal("100"),
        total_cost_basis=Decimal("1000"),
        market_price=Decimal("100"),
        market_value=Decimal("1000"),
        unrealized_gain=Decimal("0"),
        acquisition_date=date(2024, 1, 1),
        is_restricted=False,
        wash_sale_substitute_group=wash_group,
    )


def test_vti_rolls_to_equity_sleeve() -> None:
    pos = _position(ticker="VTI", asset_class=SecurityAssetClass.ETF)
    assert ips_sleeve_for_position(pos) == IpsSleeve.EQUITY


def test_bnd_rolls_to_fixed_income_sleeve() -> None:
    pos = _position(
        ticker="BND",
        asset_class=SecurityAssetClass.ETF,
        wash_group="us_bond_broad",
    )
    assert ips_sleeve_for_position(pos) == IpsSleeve.FIXED_INCOME


def test_parse_legacy_etf_alias() -> None:
    assert parse_ips_sleeve("etf") == IpsSleeve.EQUITY


def test_allocation_target_uses_ips_sleeve_enum() -> None:
    ips = InvestmentPolicyStatement(
        ips_id="ips_test",
        household_id="hh_test",
        version=1,
        effective_date="2026-01-01",
        allocation_targets=[
            AllocationTarget(
                asset_class=IpsSleeve.EQUITY,
                min_weight=Decimal("0.5"),
                max_weight=Decimal("0.7"),
                target_weight=Decimal("0.6"),
            ),
        ],
    )
    assert ips.allocation_targets[0].asset_class == IpsSleeve.EQUITY
