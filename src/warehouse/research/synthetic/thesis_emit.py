"""Synthetic position theses — co-emitted with Shape B households (pa1).

So kill-criteria are flow-testable without a DB (§9): every
instrument-in-account gets a pre-committed ``PositionThesis``. The
``effective_date`` is the earliest acquisition of that instrument's lots, so it
is on/before every lot (axiom 2 — no hindsight). Concentrated single-issuer
holdings get the tighter drawdown floor, so the ``concentrated_stress`` fixture
trips a real kill breach.

Kill thresholds default to ``analyst_*`` config (version-pinned to
``analyst_config_version``); attribution decides the residual at runtime.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from warehouse.config import get_settings
from warehouse.decision.analyst import (
    KillCriteria,
    PositionThesis,
)
from warehouse.research.synthetic.models import HouseholdFixture, SyntheticLot


def emit_synthetic_theses(
    fixture: HouseholdFixture,
    *,
    config_version: str | None = None,
) -> list[PositionThesis]:
    """One pre-committed thesis per ``(account, ticker)`` in the fixture."""
    settings = get_settings()
    version = config_version or settings.analyst_config_version

    groups: dict[tuple[str, str], list[SyntheticLot]] = defaultdict(list)
    for lot in fixture.lots:
        groups[(lot.account_id, lot.ticker)].append(lot)

    theses: list[PositionThesis] = []
    for (account_id, ticker), lots in sorted(groups.items()):
        earliest = min(lot.acquisition_date for lot in lots)
        concentrated = any(lot.concentration_issuer for lot in lots)
        theses.append(
            PositionThesis(
                account_id=account_id,
                instrument=ticker,
                mechanism=_mechanism_for(ticker, concentrated),
                effective_date=earliest,  # pre-committed on/before acquisition
                kill_criteria=_kill_criteria_for(ticker, concentrated),
                config_version=version,
            )
        )
    return theses


def _mechanism_for(ticker: str, concentrated: bool) -> str:
    if concentrated:
        return (
            f"{ticker} — concentrated single-issuer equity; thesis: franchise "
            "compounding, monitored against drawdown + residual kill criteria"
        )
    if ticker == "CASH":
        return "CASH — liquidity reserve; held, not a return thesis"
    return f"{ticker} — diversified beta sleeve; thesis: hold to class return"


def _kill_criteria_for(ticker: str, concentrated: bool) -> KillCriteria:
    settings = get_settings()
    if ticker == "CASH":
        # A reserve has no drawdown/residual thesis to falsify.
        return KillCriteria()
    if concentrated:
        return KillCriteria(
            max_drawdown_vs_cost=Decimal(
                str(settings.analyst_kill_concentrated_drawdown_pct)
            ),
            max_active_residual=Decimal(
                str(settings.analyst_kill_residual_cap)
            ),
            min_liquidity_tier=settings.analyst_kill_min_liquidity_tier,
        )
    return KillCriteria(
        max_drawdown_vs_cost=Decimal(str(settings.analyst_kill_drawdown_pct)),
        min_liquidity_tier=settings.analyst_kill_min_liquidity_tier,
    )


def synthetic_thesis_as_of(fixture: HouseholdFixture) -> date:
    """Deterministic walk-forward-safe as-of for thesis flow tests."""
    _ = fixture
    return date(2026, 6, 27)
