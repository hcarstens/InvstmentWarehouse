"""Positions and daily P&L views."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from warehouse.infra.db.models import EntityRow, LotRow, MarketPriceRow, SecurityRow


class LotPositionView(BaseModel):
    lot_id: str
    account_id: str
    account_name: str
    security_id: str
    ticker: str | None
    security_name: str
    quantity: Decimal
    cost_basis_per_share: Decimal
    total_cost_basis: Decimal
    market_price: Decimal | None
    market_value: Decimal | None
    unrealized_gain: Decimal | None
    acquisition_date: date
    is_restricted: bool


class HouseholdPnlSummary(BaseModel):
    household_id: str
    as_of_date: date | None
    total_market_value: Decimal
    total_cost_basis: Decimal
    unrealized_gain: Decimal
    lot_count: int


def list_lot_positions(
    session: Session,
    *,
    household_id: str | None = None,
) -> list[LotPositionView]:
    stmt = (
        select(LotRow, SecurityRow, EntityRow, MarketPriceRow)
        .join(SecurityRow, LotRow.security_id == SecurityRow.security_id)
        .join(EntityRow, LotRow.account_id == EntityRow.entity_id)
        .outerjoin(MarketPriceRow, LotRow.security_id == MarketPriceRow.security_id)
    )
    if household_id:
        stmt = stmt.where(EntityRow.household_id == household_id)

    views: list[LotPositionView] = []
    for lot, security, account, price_row in session.execute(stmt):
        total_cost = lot.quantity * lot.cost_basis_per_share
        market_price = price_row.price if price_row else None
        market_value = lot.quantity * market_price if market_price is not None else None
        unrealized = market_value - total_cost if market_value is not None else None
        views.append(
            LotPositionView(
                lot_id=lot.lot_id,
                account_id=lot.account_id,
                account_name=account.name,
                security_id=lot.security_id,
                ticker=security.ticker,
                security_name=security.name,
                quantity=lot.quantity,
                cost_basis_per_share=lot.cost_basis_per_share,
                total_cost_basis=total_cost,
                market_price=market_price,
                market_value=market_value,
                unrealized_gain=unrealized,
                acquisition_date=lot.acquisition_date,
                is_restricted=lot.is_restricted,
            )
        )
    return views


def household_pnl_summary(session: Session, household_id: str) -> HouseholdPnlSummary:
    positions = list_lot_positions(session, household_id=household_id)
    total_mv = Decimal("0")
    total_cost = Decimal("0")
    as_of: date | None = None
    for pos in positions:
        total_cost += pos.total_cost_basis
        if pos.market_value is not None:
            total_mv += pos.market_value
    price_dates = session.scalars(select(MarketPriceRow.as_of_date)).all()
    if price_dates:
        as_of = max(price_dates)

    return HouseholdPnlSummary(
        household_id=household_id,
        as_of_date=as_of,
        total_market_value=total_mv,
        total_cost_basis=total_cost,
        unrealized_gain=total_mv - total_cost,
        lot_count=len(positions),
    )
