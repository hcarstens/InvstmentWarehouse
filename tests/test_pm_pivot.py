"""pm_pivot pv0 — reframe falsifiers (additive, no engine change).

pv0 is docs + vocabulary only. These pin the two things pv0 asserts about the
running system: the ``Book``/``Portfolio`` alias resolves to the shipped
working set on both the demo household and HNW rung 3, and the dashboard status
north star reads as portfolio management (ℍ_Allocation), not wealth.
"""

from collections.abc import Iterator

import pytest

from warehouse.dashboard.status import build_status_report
from warehouse.decision.pm import (
    Book,
    Portfolio,
    resolve_book,
    resolve_book_from_bundle,
)
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.bootstrap import bootstrap_database
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID
from warehouse.messaging.payloads import PmAdvisePayload
from warehouse.research.synthetic import emit_synthetic_household

DEMO = DEMO_HOUSEHOLD_ID


@pytest.fixture
def seeded() -> Iterator[None]:
    bootstrap_database(seed=True)
    yield


def test_book_alias_is_working_set() -> None:
    # Book/Portfolio are a thin alias of the shipped working set — not a
    # forked type and not a household_id rename (pm_pivot decision 3).
    assert Book is PmAdvisePayload
    assert Portfolio is PmAdvisePayload


def test_resolve_book_demo(seeded: None) -> None:
    with session_scope() as session:
        book = resolve_book(session, DEMO)
    assert isinstance(book, Book)
    assert book.household_id == DEMO
    assert book.ips is not None


def test_resolve_book_from_bundle_hnw_rung3() -> None:
    bundle = emit_synthetic_household(cohort_id="general_hnw", seed=42, rung=3)
    book = resolve_book_from_bundle(bundle)
    assert isinstance(book, Portfolio)
    assert book.positions  # non-empty whole-book working set
    assert book.cohort_id == "general_hnw"


def test_status_north_star_is_pm() -> None:
    report = build_status_report()
    north = report.north_star.lower()
    assert "portfolio management" in north
    assert "wealth" not in north
