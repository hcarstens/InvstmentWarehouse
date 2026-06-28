"""Portfolio Analyst — falsifiable theses + kill-criteria monitor (pa1).

Axiom 2 (pre-commitment): every position carries a thesis whose kill criteria
were fixed *on or before* the lot was acquired, so a breach is a falsification,
never hindsight curve-fitting. ``evaluate_kill_criteria`` is **pure and
advisory**: it returns ``KillBreach`` alerts and never stages or sells anything
(CLAUDE.md human gate). The advisor decides.

The thesis is keyed ``account × instrument`` — one thesis covers every lot of
an instrument in an account, and each lot is evaluated against it
independently.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from warehouse.data.ledger.views import LotPositionView
from warehouse.decision.analyst.models import (
    KillBreach,
    KillCriteria,
    KillCriterion,
    PositionAttribution,
    PositionThesis,
)

_DAYS_PER_YEAR = Decimal("365.25")


class ThesisError(ValueError):
    """Raised on a mis-keyed or hindsight (post-acquisition) thesis."""


def instrument_key(position: LotPositionView) -> str:
    """The account×instrument key for a lot — ticker, else security_id."""
    return position.ticker or position.security_id


class ThesisStore:
    """In-memory thesis registry keyed ``(account_id, instrument)`` (pa1).

    Deliberately not frozen — it is a mutable store, like the op registry. The
    theses it holds *are* frozen/audit-critical.
    """

    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], PositionThesis] = {}

    @classmethod
    def from_theses(cls, theses: Iterable[PositionThesis]) -> ThesisStore:
        store = cls()
        for thesis in theses:
            store.add(thesis)
        return store

    def add(self, thesis: PositionThesis) -> None:
        self._by_key[(thesis.account_id, thesis.instrument)] = thesis

    def get(self, account_id: str, instrument: str) -> PositionThesis | None:
        return self._by_key.get((account_id, instrument))

    def all(self) -> list[PositionThesis]:
        return list(self._by_key.values())

    def __len__(self) -> int:
        return len(self._by_key)


def evaluate_kill_criteria(
    position: LotPositionView,
    thesis: PositionThesis,
    *,
    as_of: date,
    active_return: Decimal | None = None,
) -> list[KillBreach]:
    """Return kill-criteria breaches for one lot — ALERTS ONLY, never sells.

    Raises ``ThesisError`` if the thesis does not key to this lot, or if it
    post-dates the lot's ``acquisition_date`` (axiom 2: no hindsight). The
    residual cap is only evaluated when ``active_return`` is supplied (from the
    attribution leg); a bare position cannot compute it.
    """
    key = instrument_key(position)
    if thesis.account_id != position.account_id or thesis.instrument != key:
        raise ThesisError(
            f"thesis ({thesis.account_id}, {thesis.instrument}) does not key "
            f"to lot {position.lot_id} ({position.account_id}, {key})"
        )
    if thesis.effective_date > position.acquisition_date:
        raise ThesisError(
            f"thesis for {thesis.instrument} effective "
            f"{thesis.effective_date} post-dates lot {position.lot_id} "
            f"acquired {position.acquisition_date} — pre-commitment "
            "violation (axiom 2)"
        )
    if position.market_value is None or position.unrealized_gain is None:
        raise ThesisError(
            f"lot {position.lot_id} has no market value; cannot monitor "
            "kill criteria"
        )
    if position.total_cost_basis <= 0:
        raise ThesisError(
            f"lot {position.lot_id} has non-positive cost basis; cannot "
            "compute drawdown vs cost"
        )

    total_return = position.unrealized_gain / position.total_cost_basis
    days = max((as_of - position.acquisition_date).days, 0)
    holding_years = Decimal(days) / _DAYS_PER_YEAR
    return _breaches(
        account_id=position.account_id,
        instrument=key,
        kill_criteria=thesis.kill_criteria,
        total_return=total_return,
        holding_years=holding_years,
        liquidity_tier=position.liquidity_tier,
        active_return=active_return,
    )


def breaches_for_attribution(
    pa: PositionAttribution, thesis: PositionThesis
) -> list[KillBreach]:
    """Kill breaches for an attribution row (report-side, e.g. checkpoint 1).

    Uses the already-computed ``active_return``/``total_return``/
    ``holding_years``/``liquidity_tier`` on the row. The pre-commitment date
    assertion lives in ``evaluate_kill_criteria`` (the report drops the
    acquisition date); it is the primary runtime guard.
    """
    return _breaches(
        account_id=pa.account_id,
        instrument=pa.ticker or "",
        kill_criteria=thesis.kill_criteria,
        total_return=pa.total_return,
        holding_years=pa.holding_years,
        liquidity_tier=pa.liquidity_tier,
        active_return=pa.active_return,
    )


def _breaches(
    *,
    account_id: str,
    instrument: str,
    kill_criteria: KillCriteria,
    total_return: Decimal,
    holding_years: Decimal,
    liquidity_tier: int,
    active_return: Decimal | None,
) -> list[KillBreach]:
    kc = kill_criteria
    breaches: list[KillBreach] = []

    if (
        kc.max_drawdown_vs_cost is not None
        and total_return <= kc.max_drawdown_vs_cost
    ):
        breaches.append(
            KillBreach(
                account_id=account_id,
                instrument=instrument,
                criterion=KillCriterion.DRAWDOWN_VS_COST,
                observed=total_return,
                threshold=kc.max_drawdown_vs_cost,
                detail=(
                    f"drawdown {total_return:.2%} ≤ kill "
                    f"{kc.max_drawdown_vs_cost:.2%}"
                ),
            )
        )

    if (
        kc.max_active_residual is not None
        and active_return is not None
        and abs(active_return) >= kc.max_active_residual
    ):
        breaches.append(
            KillBreach(
                account_id=account_id,
                instrument=instrument,
                criterion=KillCriterion.RESIDUAL_CAP,
                observed=active_return,
                threshold=kc.max_active_residual,
                detail=(
                    f"|active return| {abs(active_return):.2%} ≥ cap "
                    f"{kc.max_active_residual:.2%}"
                ),
            )
        )

    if (
        kc.min_liquidity_tier is not None
        and liquidity_tier > kc.min_liquidity_tier
    ):
        breaches.append(
            KillBreach(
                account_id=account_id,
                instrument=instrument,
                criterion=KillCriterion.LIQUIDITY_FLOOR,
                observed=Decimal(liquidity_tier),
                threshold=Decimal(kc.min_liquidity_tier),
                detail=(
                    f"liquidity tier {liquidity_tier} worse than floor "
                    f"{kc.min_liquidity_tier}"
                ),
            )
        )

    if (
        kc.max_holding_years is not None
        and holding_years > kc.max_holding_years
    ):
        breaches.append(
            KillBreach(
                account_id=account_id,
                instrument=instrument,
                criterion=KillCriterion.HORIZON,
                observed=holding_years.quantize(Decimal("0.01")),
                threshold=kc.max_holding_years,
                detail=(
                    f"held {holding_years:.2f}y past horizon "
                    f"{kc.max_holding_years}y"
                ),
            )
        )

    return breaches
