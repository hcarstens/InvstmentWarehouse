"""Persist synthetic household bundles to SQLite — Shape B → DB slice."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from warehouse.data.security_master import TaxCharacter
from warehouse.decision.ips.store import save_ips
from warehouse.infra.db.models import (
    AlternativeEventRow,
    AlternativeHoldingRow,
    EntityRelationshipRow,
    EntityRow,
    IpsPolicyRow,
    LotRow,
    MarketPriceRow,
    SecurityRow,
)
from warehouse.models.entities import EntityType, RelationshipType
from warehouse.research.synthetic.fixture_views import (
    _WASH_GROUPS,
    _lot_liquidity_tier,
    _security_asset_class,
)
from warehouse.research.synthetic.models import (
    HouseholdFixture,
    SyntheticHouseholdBundle,
    SyntheticLot,
)

_TICKER_NAMES: dict[str, str] = {
    "VTI": "Vanguard Total Stock Market ETF",
    "BND": "Vanguard Total Bond Market ETF",
    "AAPL": "Apple Inc",
    "DBC": "Invesco DB Commodity Index",
    "CASH": "Cash & Equivalents",
}


def _security_id(ticker: str) -> str:
    return f"sec_syn_{ticker.lower()}"


def _ensure_security(session: Session, lot: SyntheticLot) -> str:
    sec_id = _security_id(lot.ticker)
    if session.get(SecurityRow, sec_id):
        return sec_id
    asset_class = _security_asset_class(lot)
    session.add(
        SecurityRow(
            security_id=sec_id,
            ticker=lot.ticker,
            name=_TICKER_NAMES.get(lot.ticker, lot.ticker),
            asset_class=asset_class.value,
            tax_character=TaxCharacter.LTCG.value,
            liquidity_tier=_lot_liquidity_tier(lot),
            wash_sale_substitute_group=_WASH_GROUPS.get(lot.ticker),
        )
    )
    return sec_id


def _seed_market_prices(
    session: Session,
    fixture: HouseholdFixture,
    *,
    as_of: date,
) -> None:
    for lot in fixture.lots:
        sec_id = _security_id(lot.ticker)
        existing = session.scalar(
            select(MarketPriceRow)
            .where(MarketPriceRow.security_id == sec_id)
            .limit(1)
        )
        if existing:
            continue
        session.add(
            MarketPriceRow(
                security_id=sec_id,
                price=lot.market_price,
                as_of_date=as_of,
            )
        )


def seed_synthetic_household(
    session: Session,
    bundle: SyntheticHouseholdBundle,
    *,
    as_of: date | None = None,
) -> bool:
    """Insert synthetic graph, lots, alts, and IPS.

    Idempotent by household_id + ips_id.
    """
    fixture = bundle.fixture
    hh_id = fixture.household_id
    price_date = as_of or date(2026, 6, 27)

    if session.get(IpsPolicyRow, bundle.ips.ips_id):
        return False

    newly_created = session.get(EntityRow, hh_id) is None
    if newly_created:
        session.add(
            EntityRow(
                entity_id=hh_id,
                entity_type=EntityType.HOUSEHOLD,
                name=f"Synthetic {fixture.provenance.cohort_id}",
                household_id=hh_id,
            )
        )

    restricted = frozenset(bundle.ips.restricted_securities)
    for account in fixture.accounts:
        if session.get(EntityRow, account.account_id) is None:
            session.add(
                EntityRow(
                    entity_id=account.account_id,
                    entity_type=EntityType.ACCOUNT,
                    name=account.name,
                    household_id=hh_id,
                )
            )
        rel_exists = session.scalar(
            select(EntityRelationshipRow.id)
            .where(
                EntityRelationshipRow.source_id == hh_id,
                EntityRelationshipRow.target_id == account.account_id,
            )
            .limit(1)
        )
        if rel_exists is None:
            session.add(
                EntityRelationshipRow(
                    source_id=hh_id,
                    target_id=account.account_id,
                    relationship_type=RelationshipType.AGGREGATES,
                )
            )

    for lot in fixture.lots:
        sec_id = _ensure_security(session, lot)
        if session.get(LotRow, lot.lot_id) is None:
            session.add(
                LotRow(
                    lot_id=lot.lot_id,
                    account_id=lot.account_id,
                    security_id=sec_id,
                    quantity=lot.quantity,
                    cost_basis_per_share=lot.cost_basis_per_share,
                    acquisition_date=lot.acquisition_date,
                    is_restricted=lot.ticker in restricted,
                )
            )

    for alt in fixture.alternative_holdings:
        if session.get(AlternativeHoldingRow, alt.holding_id) is None:
            session.add(
                AlternativeHoldingRow(
                    holding_id=alt.holding_id,
                    household_id=hh_id,
                    entity_id=alt.entity_id,
                    name=alt.name,
                    asset_type=alt.asset_type,
                    committed_capital=alt.committed_capital,
                    called_capital=alt.called_capital,
                    current_nav=alt.current_nav,
                    last_mark_date=alt.last_mark_date,
                )
            )
        for call in alt.scheduled_calls:
            if session.get(AlternativeEventRow, call.event_id) is None:
                session.add(
                    AlternativeEventRow(
                        event_id=call.event_id,
                        holding_id=alt.holding_id,
                        event_type="capital_call",
                        amount=call.amount,
                        event_date=call.event_date,
                        notes="Synthetic scheduled call",
                    )
                )

    _seed_market_prices(session, fixture, as_of=price_date)
    save_ips(session, bundle.ips)
    session.flush()
    return newly_created
