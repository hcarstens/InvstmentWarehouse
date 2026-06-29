"""st5i — reporting performance falsifiers (ST2 independent oracles).

Coverage floor is an amber badge only (¬QA6) — pass/fail is pytest verdict.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from hypothesis import given
from hypothesis import strategies as st

from warehouse.data.ledger.views import LotPositionView
from warehouse.data.security_master import AssetClass, TaxCharacter
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.models import (
    EntityRow,
    LotRow,
    MarketPriceRow,
    SecurityRow,
)
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID
from warehouse.models.entities import EntityType
from warehouse.reporting.performance import (
    HouseholdPerformanceReport,
    PerformanceError,
    RealizedGainEvent,
    build_household_performance_report,
    realized_gain_ytd,
)
from warehouse.reporting.performance.compute import _aggregate_positions

AS_OF = date(2026, 6, 24)


# --- independent oracles (ST2) -----------------------------------------------


def _independent_mv(
    lots: list[tuple[Decimal, Decimal]],
) -> Decimal:
    """Sum qty × mark — independent of build_household_performance_report."""
    return sum((qty * price for qty, price in lots), Decimal("0"))


def _independent_unrealized(
    lots: list[tuple[Decimal, Decimal, Decimal]],
) -> Decimal:
    """Sum MV − cost for (qty, mark, cost_per_share) tuples."""
    return sum(
        (qty * mark - qty * cost for qty, mark, cost in lots),
        Decimal("0"),
    )


def _oracle_realized_ytd(
    events: list[tuple[date, Decimal]],
    *,
    as_of: date,
) -> Decimal:
    ytd_start = date(as_of.year, 1, 1)
    return sum(
        (amt for evt_date, amt in events if ytd_start <= evt_date <= as_of),
        Decimal("0"),
    )


# --- session helpers ---------------------------------------------------------


def _seed_perf_household(
    session,
    *,
    household_id: str,
    lots: list[tuple[str, str, Decimal, Decimal, date]],
    prices: list[tuple[str, Decimal]],
) -> None:
    """Insert household, account, lots, and marks for an isolated fixture."""
    session.add(
        EntityRow(
            entity_id=household_id,
            entity_type=EntityType.HOUSEHOLD,
            name="Perf Test HH",
            household_id=household_id,
        )
    )
    account_id = f"acct_{household_id}"
    session.add(
        EntityRow(
            entity_id=account_id,
            entity_type=EntityType.ACCOUNT,
            name="Perf Test Account",
            household_id=household_id,
        )
    )
    for lot_id, security_id, qty, cost, acq in lots:
        if session.get(SecurityRow, security_id) is None:
            session.add(
                SecurityRow(
                    security_id=security_id,
                    ticker=security_id.upper(),
                    cusip=None,
                    name=security_id,
                    asset_class=AssetClass.ETF,
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
    for security_id, price in prices:
        existing = session.get(MarketPriceRow, security_id)
        if existing is None:
            session.add(
                MarketPriceRow(
                    security_id=security_id,
                    price=price,
                    as_of_date=AS_OF,
                )
            )
    session.flush()


# --- falsifiers --------------------------------------------------------------


def test_known_two_lot_mv_and_unrealized() -> None:
    hh = "hh_perf_two"
    lot_specs = [
        ("lot_a", "sec_x", Decimal("10"), Decimal("100"), date(2024, 1, 1)),
        ("lot_b", "sec_y", Decimal("5"), Decimal("200"), date(2024, 6, 1)),
    ]
    marks = [("sec_x", Decimal("110")), ("sec_y", Decimal("210"))]
    expected_mv = _independent_mv(
        [(Decimal("10"), Decimal("110")), (Decimal("5"), Decimal("210"))]
    )
    expected_unreal = _independent_unrealized(
        [
            (Decimal("10"), Decimal("110"), Decimal("100")),
            (Decimal("5"), Decimal("210"), Decimal("200")),
        ]
    )
    with session_scope() as session:
        _seed_perf_household(
            session,
            household_id=hh,
            lots=lot_specs,
            prices=marks,
        )
        report = build_household_performance_report(
            session,
            household_id=hh,
            as_of=AS_OF,
        )
    assert report.total_market_value == expected_mv
    assert report.unrealized_gain == expected_unreal


def test_empty_household_zero_mv() -> None:
    with session_scope() as session:
        report = build_household_performance_report(
            session,
            household_id="hh_no_lots",
            as_of=AS_OF,
        )
    assert report.total_market_value == Decimal("0")
    assert report.unrealized_gain == Decimal("0")
    assert report.realized_gain_ytd == Decimal("0")


def test_missing_mark_treated_loudly() -> None:
    hh = "hh_perf_nomark"
    with session_scope() as session:
        _seed_perf_household(
            session,
            household_id=hh,
            lots=[
                (
                    "lot_nomark",
                    "sec_unmarked",
                    Decimal("1"),
                    Decimal("50"),
                    date(2024, 1, 1),
                )
            ],
            prices=[],
        )
        with pytest.raises(PerformanceError, match="missing market mark"):
            build_household_performance_report(
                session,
                household_id=hh,
                as_of=AS_OF,
            )


def test_as_of_before_acquisition_raises() -> None:
    with session_scope() as session:
        with pytest.raises(PerformanceError, match="before lot"):
            build_household_performance_report(
                session,
                household_id=DEMO_HOUSEHOLD_ID,
                as_of=date(2020, 1, 1),
            )


def test_ytd_realized_from_events() -> None:
    as_of = date(2026, 6, 15)
    stream = [
        RealizedGainEvent(
            event_id="e1",
            event_date=date(2026, 2, 1),
            amount=Decimal("1500"),
        ),
        RealizedGainEvent(
            event_id="e2",
            event_date=date(2025, 12, 31),
            amount=Decimal("999"),
        ),
        RealizedGainEvent(
            event_id="e3",
            event_date=date(2026, 7, 1),
            amount=Decimal("500"),
        ),
    ]
    expected = _oracle_realized_ytd(
        [(date(2026, 2, 1), Decimal("1500"))],
        as_of=as_of,
    )
    assert realized_gain_ytd(stream, as_of=as_of) == expected


def test_performance_report_round_trip() -> None:
    with session_scope() as session:
        report = build_household_performance_report(
            session,
            household_id=DEMO_HOUSEHOLD_ID,
            as_of=AS_OF,
        )
    assert isinstance(report, HouseholdPerformanceReport)
    assert report.household_id == DEMO_HOUSEHOLD_ID
    assert report.as_of_date == AS_OF.isoformat()
    assert report.total_market_value >= Decimal("0")


def test_demo_household_matches_independent_oracle() -> None:
    """Full demo seed — recompute MV/unrealized without calling aggregate."""
    prices = {
        "sec_vti": Decimal("245.50"),
        "sec_bnd": Decimal("73.10"),
        "sec_aapl": Decimal("195.20"),
    }
    lot_rows = [
        ("sec_vti", Decimal("500"), Decimal("210.00")),
        ("sec_vti", Decimal("50"), Decimal("255.00")),
        ("sec_aapl", Decimal("100"), Decimal("145.50")),
        ("sec_bnd", Decimal("300"), Decimal("72.25")),
        ("sec_vti", Decimal("200"), Decimal("230.00")),
        ("sec_bnd", Decimal("150"), Decimal("74.00")),
    ]
    expected_mv = _independent_mv(
        [(qty, prices[sec]) for sec, qty, _ in lot_rows]
    )
    expected_unreal = _independent_unrealized(
        [(qty, prices[sec], cost) for sec, qty, cost in lot_rows]
    )
    with session_scope() as session:
        report = build_household_performance_report(
            session,
            household_id=DEMO_HOUSEHOLD_ID,
            as_of=AS_OF,
        )
    assert report.total_market_value == expected_mv
    assert report.unrealized_gain == expected_unreal


def test_ytd_realized_wired_through_build() -> None:
    events = [
        RealizedGainEvent(
            event_id="r1",
            event_date=date(2026, 3, 10),
            amount=Decimal("2500"),
        ),
    ]
    with session_scope() as session:
        with patch(
            "warehouse.reporting.performance.compute._fetch_realized_events",
            return_value=events,
        ):
            report = build_household_performance_report(
                session,
                household_id=DEMO_HOUSEHOLD_ID,
                as_of=AS_OF,
            )
    assert report.realized_gain_ytd == Decimal("2500")


def _position_view(
    *,
    lot_id: str,
    mv: Decimal,
    cost: Decimal,
    acq: date = date(2024, 1, 1),
) -> LotPositionView:
    return LotPositionView(
        lot_id=lot_id,
        account_id="acct",
        account_name="Account",
        security_id="sec",
        ticker="TST",
        security_name="Test",
        security_asset_class=AssetClass.ETF,
        quantity=Decimal("1"),
        cost_basis_per_share=cost,
        total_cost_basis=cost,
        market_price=mv,
        market_value=mv,
        unrealized_gain=mv - cost,
        acquisition_date=acq,
        is_restricted=False,
        wash_sale_substitute_group=None,
    )


@given(
    scale=st.decimals(
        min_value=Decimal("0.01"),
        max_value=Decimal("100"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    )
)
def test_scale_marks_scales_mv_metamorphic(scale: Decimal) -> None:
    """Metamorphic: scaling all marks scales total MV by the same factor."""
    base = [
        _position_view(lot_id="a", mv=Decimal("120"), cost=Decimal("30")),
        _position_view(lot_id="b", mv=Decimal("420"), cost=Decimal("140")),
    ]
    scaled = [
        _position_view(
            lot_id="a",
            mv=Decimal("120") * scale,
            cost=Decimal("30"),
        ),
        _position_view(
            lot_id="b",
            mv=Decimal("420") * scale,
            cost=Decimal("140"),
        ),
    ]
    base_mv, _ = _aggregate_positions(base, as_of=AS_OF)
    scaled_mv, _ = _aggregate_positions(scaled, as_of=AS_OF)
    assert scaled_mv == base_mv * scale
