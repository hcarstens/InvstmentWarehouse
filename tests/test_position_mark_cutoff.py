"""M3 caveat fix (pv2) — ``list_lot_positions`` selects the mark ≤ ``as_of``.

``market_prices`` is now a dated series (composite PK). Pin that the join picks
the most recent mark AT OR BEFORE ``as_of`` against a two-date history — not a
later or arbitrary mark.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from warehouse.data.ledger.views import list_lot_positions
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.bootstrap import bootstrap_database
from warehouse.infra.db.models import MarketPriceRow
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID

_EARLY = date(2026, 5, 1)
_LATE = date(2026, 6, 10)
_EARLY_PRICE = Decimal("200.00")
_LATE_PRICE = Decimal("240.00")


def _vti_price(session, as_of: date) -> Decimal | None:  # type: ignore[no-untyped-def]
    positions = list_lot_positions(
        session, household_id=DEMO_HOUSEHOLD_ID, as_of=as_of
    )
    vti = [p for p in positions if p.security_id == "sec_vti"]
    assert vti, "expected a VTI lot in the demo book"
    return vti[0].market_price


def test_position_mark_selected_at_or_before_as_of() -> None:
    bootstrap_database(seed=True)
    with session_scope() as session:
        early = MarketPriceRow(
            security_id="sec_vti", as_of_date=_EARLY, price=_EARLY_PRICE
        )
        late = MarketPriceRow(
            security_id="sec_vti", as_of_date=_LATE, price=_LATE_PRICE
        )
        session.add_all([early, late])
        session.flush()
        try:
            # Between the two marks → picks the EARLY mark (≤ as_of).
            assert _vti_price(session, date(2026, 5, 20)) == _EARLY_PRICE
            # On/after the late mark (but before the seed 2026-06-24 mark) →
            # picks the LATE mark.
            assert _vti_price(session, _LATE) == _LATE_PRICE
            # Before either → no mark ≤ as_of → None (no leakage of a later
            # mark).
            assert _vti_price(session, date(2026, 4, 1)) is None
        finally:
            session.delete(early)
            session.delete(late)
            session.flush()
