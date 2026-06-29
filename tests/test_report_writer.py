"""rw0 — report writer collector falsifiers."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from warehouse.data.security_master import AssetClass, TaxCharacter
from warehouse.decision.ips import AllocationTarget, InvestmentPolicyStatement
from warehouse.decision.ips.sleeves import IpsSleeve
from warehouse.decision.ips.store import save_ips
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.models import (
    EntityRow,
    LotRow,
    MarketPriceRow,
    SecurityRow,
)
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID
from warehouse.models.entities import EntityType
from warehouse.reporting.report_writer import (
    ReportPeriod,
    ReportWriterError,
    collect_report_bundle,
)

AS_OF = date(2026, 6, 24)


def _seed_household_with_lot(
    session,
    *,
    household_id: str,
    lot_id: str,
    security_id: str,
    account_id: str,
    qty: Decimal,
    cost: Decimal,
    price: Decimal,
    acq: date,
) -> None:
    session.add(
        EntityRow(
            entity_id=household_id,
            entity_type=EntityType.HOUSEHOLD,
            name="Report Writer HH",
            household_id=household_id,
        )
    )
    session.add(
        EntityRow(
            entity_id=account_id,
            entity_type=EntityType.ACCOUNT,
            name="Report Writer Account",
            household_id=household_id,
        )
    )
    session.add(
        SecurityRow(
            security_id=security_id,
            ticker=security_id.upper(),
            cusip=None,
            name=security_id,
            asset_class=AssetClass.EQUITY,
            tax_character=TaxCharacter.LTCG,
            liquidity_tier=1,
        )
    )
    session.add(
        LotRow(
            lot_id=lot_id,
            account_id=account_id,
            security_id=security_id,
            quantity=qty,
            cost_basis_per_share=cost,
            acquisition_date=acq,
        )
    )
    session.add(
        MarketPriceRow(
            security_id=security_id,
            price=price,
            as_of_date=AS_OF,
        )
    )
    session.flush()


def test_demo_household_bundle_has_performance_and_ips_drift() -> None:
    with session_scope() as session:
        bundle = collect_report_bundle(
            session,
            DEMO_HOUSEHOLD_ID,
            period=ReportPeriod.month_end(AS_OF),
            as_of=AS_OF,
        )
    assert bundle.performance is not None
    assert bundle.ips_drift is not None
    assert bundle.performance.total_market_value > Decimal("0")
    assert bundle.ips_drift.household_id == DEMO_HOUSEHOLD_ID
    assert bundle.period.label == f"month-end-{AS_OF.isoformat()}"
    assert bundle.snapshot_id.startswith("rpt_")


def test_missing_ips_raises() -> None:
    hh = "hh_report_no_ips"
    with session_scope() as session:
        _seed_household_with_lot(
            session,
            household_id=hh,
            lot_id="lot_nips",
            security_id="sec_nips",
            account_id="acct_nips",
            qty=Decimal("1"),
            cost=Decimal("100"),
            price=Decimal("110"),
            acq=date(2024, 1, 1),
        )
        with pytest.raises(ReportWriterError, match="No IPS"):
            collect_report_bundle(
                session,
                hh,
                period=ReportPeriod.month_end(AS_OF),
                as_of=AS_OF,
            )


def test_missing_positions_raises() -> None:
    hh = "hh_report_no_positions"
    with session_scope() as session:
        session.add(
            EntityRow(
                entity_id=hh,
                entity_type=EntityType.HOUSEHOLD,
                name="No Positions",
                household_id=hh,
            )
        )
        save_ips(
            session,
            InvestmentPolicyStatement(
                ips_id="ips_npos",
                household_id=hh,
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
            ),
        )
        session.flush()
        with pytest.raises(ReportWriterError, match="No positions"):
            collect_report_bundle(
                session,
                hh,
                period=ReportPeriod.month_end(AS_OF),
                as_of=AS_OF,
            )


def test_limitations_include_tax_stub_when_zero() -> None:
    hh = "hh_report_zero_tax"
    with session_scope() as session:
        _seed_household_with_lot(
            session,
            household_id=hh,
            lot_id="lot_ztax",
            security_id="sec_ztax",
            account_id="acct_ztax",
            qty=Decimal("10"),
            cost=Decimal("100"),
            price=Decimal("100"),
            acq=date(2024, 1, 1),
        )
        save_ips(
            session,
            InvestmentPolicyStatement(
                ips_id="ips_ztax",
                household_id=hh,
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
            ),
        )
        session.flush()
        bundle = collect_report_bundle(
            session,
            hh,
            period=ReportPeriod.month_end(AS_OF),
            as_of=AS_OF,
        )
    assert all(ts.tax_delta == Decimal("0") for ts in bundle.tax_scenarios)
    assert any("zero-stubbed" in note for note in bundle.limitations)
