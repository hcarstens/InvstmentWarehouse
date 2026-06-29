"""Household performance snapshot from lot ledger positions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from warehouse.data.ledger.views import LotPositionView, list_lot_positions
from warehouse.infra.db.models import RealizedGainEventRow


class PerformanceError(ValueError):
    """Reporting failed — missing data or walk-forward violation."""


class HouseholdPerformanceReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    household_id: str
    as_of_date: str
    total_market_value: Decimal
    unrealized_gain: Decimal
    realized_gain_ytd: Decimal
    after_tax_return_ytd: Decimal | None = None


class RealizedGainEvent(BaseModel):
    """Realized gain or loss (event stream row until persisted)."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    event_date: date
    amount: Decimal = Field(
        description="Realized gain (positive) or loss (negative)"
    )


def realized_gain_ytd(
    events: list[RealizedGainEvent],
    *,
    as_of: date,
) -> Decimal:
    """Sum realized gains with event_date in [Jan 1, as_of] of as_of.year."""
    ytd_start = date(as_of.year, 1, 1)
    return sum(
        (
            event.amount
            for event in events
            if ytd_start <= event.event_date <= as_of
        ),
        Decimal("0"),
    )


def _fetch_realized_events(
    session: Session,
    household_id: str,
    *,
    as_of: date,
) -> list[RealizedGainEvent]:
    """Load realized gain/loss events for the household through ``as_of``."""
    rows = session.scalars(
        select(RealizedGainEventRow)
        .where(RealizedGainEventRow.household_id == household_id)
        .where(RealizedGainEventRow.event_date <= as_of)
        .order_by(RealizedGainEventRow.event_date)
    ).all()
    return [
        RealizedGainEvent(
            event_id=row.event_id,
            event_date=row.event_date,
            amount=row.amount,
        )
        for row in rows
    ]


def _aggregate_positions(
    positions: list[LotPositionView],
    *,
    as_of: date,
) -> tuple[Decimal, Decimal]:
    """Return (total_market_value, total_cost_basis) with loud failures."""
    total_mv = Decimal("0")
    total_cost = Decimal("0")
    for pos in positions:
        if as_of < pos.acquisition_date:
            raise PerformanceError(
                f"as_of {as_of} before lot {pos.lot_id} acquisition "
                f"{pos.acquisition_date}"
            )
        total_cost += pos.total_cost_basis
        if pos.market_value is None:
            ticker = pos.ticker or pos.security_id
            raise PerformanceError(
                f"missing market mark for {ticker} (lot {pos.lot_id})"
            )
        total_mv += pos.market_value
    return total_mv, total_cost


def build_household_performance_report(
    session: Session,
    *,
    household_id: str,
    as_of: date,
) -> HouseholdPerformanceReport:
    """Build a frozen household performance snapshot as of ``as_of``."""
    positions = list_lot_positions(session, household_id=household_id)
    total_mv, total_cost = _aggregate_positions(positions, as_of=as_of)
    unrealized = total_mv - total_cost
    realized_events = _fetch_realized_events(
        session,
        household_id,
        as_of=as_of,
    )
    realized_ytd = realized_gain_ytd(realized_events, as_of=as_of)
    return HouseholdPerformanceReport(
        household_id=household_id,
        as_of_date=as_of.isoformat(),
        total_market_value=total_mv,
        unrealized_gain=unrealized,
        realized_gain_ytd=realized_ytd,
        after_tax_return_ytd=None,
    )
