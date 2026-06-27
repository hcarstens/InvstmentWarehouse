"""IPS policy constraint fields — si0b."""

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from warehouse.data.ledger.views import LotPositionView
from warehouse.data.security_master import AssetClass as SecurityAssetClass
from warehouse.decision.constraints import active_constraint_summary
from warehouse.decision.ips import AllocationTarget, InvestmentPolicyStatement
from warehouse.decision.ips.liquidity import liquid_tier_nav_share
from warehouse.decision.ips.monitor import build_ips_drift_report
from warehouse.decision.ips.sleeves import IpsSleeve
from warehouse.decision.ips.store import load_ips, save_ips
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.bootstrap import bootstrap_database
from warehouse.infra.db.models import IpsPolicyRow
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID


def _lot(ticker: str, mv: Decimal, *, tier: int = 1) -> LotPositionView:
    return LotPositionView(
        lot_id=f"lot_{ticker}",
        account_id="acct",
        account_name="Acct",
        security_id=f"sec_{ticker}",
        ticker=ticker,
        security_name=ticker,
        security_asset_class=SecurityAssetClass.EQUITY,
        liquidity_tier=tier,
        quantity=Decimal("1"),
        cost_basis_per_share=mv,
        total_cost_basis=mv,
        market_price=mv,
        market_value=mv,
        unrealized_gain=Decimal("0"),
        acquisition_date=date(2024, 1, 1),
        is_restricted=False,
        wash_sale_substitute_group=None,
    )


def test_concentration_limit_from_ips_not_hardcoded() -> None:
    ips = InvestmentPolicyStatement(
        ips_id="ips_cap",
        household_id="hh_test",
        version=1,
        effective_date="2026-01-01",
        allocation_targets=[
            AllocationTarget(
                asset_class=IpsSleeve.EQUITY,
                min_weight=Decimal("0"),
                max_weight=Decimal("1"),
                target_weight=Decimal("1"),
            ),
        ],
        concentration_limit_pct=Decimal("0.15"),
    )
    positions = [
        _lot("AAA", Decimal("120")),
        _lot("BBB", Decimal("880")),
    ]
    with session_scope() as session:
        report = build_ips_drift_report(session, "hh_test", positions, ips=ips)
    assert not any("AAA" in a for a in report.concentration_alerts)
    assert any("BBB" in a for a in report.concentration_alerts)


def test_liquid_tier_nav_share() -> None:
    positions = [
        _lot("L1", Decimal("600"), tier=1),
        _lot("L3", Decimal("400"), tier=3),
    ]
    assert liquid_tier_nav_share(positions, max_tier=2) == Decimal("0.6")


def test_active_constraint_summary_includes_policy_fields() -> None:
    ips = InvestmentPolicyStatement(
        ips_id="ips_fields",
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
        concentration_limit_pct=Decimal("0.12"),
        liquidity_tier_min_pct=Decimal("0.75"),
        turnover_budget_pct=Decimal("0.20"),
    )
    summary = active_constraint_summary(ips)
    assert "concentration_limit<=0.12" in summary
    assert "liquidity_tier_1_2>=0.75" in summary
    assert "turnover_budget<=0.20" in summary


def test_ips_constraints_persist_round_trip() -> None:
    bootstrap_database(seed=True)
    ips = InvestmentPolicyStatement(
        ips_id="ips_roundtrip",
        household_id="hh_roundtrip",
        version=1,
        effective_date="2026-01-01",
        allocation_targets=[
            AllocationTarget(
                asset_class=IpsSleeve.CASH,
                min_weight=Decimal("0"),
                max_weight=Decimal("1"),
                target_weight=Decimal("0.1"),
            ),
        ],
        concentration_limit_pct=Decimal("0.15"),
        liquidity_tier_min_pct=Decimal("0.60"),
        turnover_budget_pct=Decimal("0.10"),
    )
    with session_scope() as session:
        save_ips(session, ips)
    with session_scope() as session:
        loaded = load_ips(session, "hh_roundtrip")
        row = session.scalar(
            select(IpsPolicyRow).where(
                IpsPolicyRow.household_id == "hh_roundtrip"
            )
        )
        assert loaded is not None
        assert loaded.concentration_limit_pct == Decimal("0.15")
        assert loaded.liquidity_tier_min_pct == Decimal("0.60")
        assert loaded.turnover_budget_pct == Decimal("0.10")
        assert row is not None
        assert "concentration_limit_pct" in row.constraints_json


def test_demo_seed_ips_has_policy_fields() -> None:
    bootstrap_database(seed=True)
    with session_scope() as session:
        ips = load_ips(session, DEMO_HOUSEHOLD_ID)
        assert ips is not None
        summary = active_constraint_summary(ips)
    assert ips.turnover_budget_pct == Decimal("0.15")
    assert any("concentration_limit" in s for s in summary)
    assert any("turnover_budget" in s for s in summary)
