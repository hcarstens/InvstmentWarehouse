"""Portfolio Analyst — non-performing-asset (NPA) flags (pa2).

``flag_non_performing`` is **pure and advisory** (like pa1's kill-criteria, not
a new op): it returns reason-coded ``NpaFlag`` alerts across public lots and
the alternatives sleeve and never stages a trade, never touches the optimizer
(CLAUDE.md human gate). v0 flags feed the dashboard + the approval gate only.

Four version-pinned rules (open question #13):

- **sustained drawdown vs cost** — a lot below cost beyond ``drawdown_pct``
  *and* held past ``sustained_years`` (a fresh dip is not a non-performer);
- **stale alt mark** — an alt's ``last_mark_date`` older than
  ``stale_mark_days`` (manual marks go stale; the NAV is suspect);
- **missed capital call** — a scheduled call due on/before ``as_of`` with
  capital still unfunded (v0: there is no funded flag — see ``_LIMITATIONS``);
- **IPS liquidity breach** — liquid-tier NAV share below the IPS floor.

Walk-forward safe: a position acquired or an alt marked after ``as_of`` is a
lookahead error and raises (CLAUDE.md walk-forward); only as-of data is read.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Protocol

from warehouse.data.ledger.views import LotPositionView
from warehouse.decision.analyst.models import (
    NpaFlag,
    NpaFlags,
    NpaReason,
    NpaSubject,
)
from warehouse.decision.ips import InvestmentPolicyStatement
from warehouse.decision.ips.liquidity import liquid_tier_nav_share

_DAYS_PER_YEAR = Decimal("365.25")
_RETURN_QUANTUM = Decimal("0.0001")
_LIQUID_MAX_TIER = 2

_LIMITATIONS: tuple[str, ...] = (
    "Sustained drawdown is unrealized point-in-time vs cost — holding age "
    "stands in for the duration the lot has been underwater (no price path).",
    "Missed capital call is a v0 heuristic — SyntheticAltCall carries no "
    "funded flag, so a scheduled call due on/before as_of with capital still "
    "unfunded is treated as missed.",
    "IPS liquidity share covers public lots only (liquidity tiers on "
    "positions); the alternatives sleeve is not yet folded into the "
    "liquid-share denominator.",
    "Advisory only — flags feed the dashboard and the approval gate, never "
    "optimizer constraints or staged trades (human gate).",
)


class ScheduledCallLike(Protocol):
    """Structural view of a scheduled capital call (e.g. SyntheticAltCall)."""

    event_date: date
    amount: Decimal


class AltHoldingLike(Protocol):
    """Structural view of an alt holding the NPA rules consume.

    ``SyntheticAltHolding`` satisfies this; the DB-backed
    ``AlternativeHoldingView`` does not yet carry ``unfunded_capital`` /
    ``scheduled_calls`` / ``liquidity_tier``, so missed-call flags need the
    richer synthetic type until that view is enriched.
    """

    holding_id: str
    name: str
    current_nav: Decimal
    unfunded_capital: Decimal
    last_mark_date: date
    liquidity_tier: int
    scheduled_calls: Sequence[ScheduledCallLike]


class NpaError(ValueError):
    """Raised on an un-flaggable input (e.g. a lookahead acquisition/mark)."""


def flag_non_performing(
    positions: list[LotPositionView],
    alts: Sequence[AltHoldingLike],
    ips: InvestmentPolicyStatement | None,
    *,
    household_id: str,
    as_of: date,
    config_version: str,
    stale_mark_days: int,
    drawdown_pct: Decimal,
    sustained_years: Decimal,
) -> NpaFlags:
    """Return reason-coded NPA flags — ALERTS ONLY, never staged trades.

    Pure: same inputs → same flags; nothing is persisted, no optimizer is
    touched. Thresholds are passed in (the caller reads version-pinned
    settings) so the function stays testable and replay-stable, mirroring
    ``evaluate_attribution``.
    """
    flags: list[NpaFlag] = []
    flags.extend(
        _sustained_drawdown_flags(
            positions,
            as_of=as_of,
            drawdown_pct=drawdown_pct,
            sustained_years=sustained_years,
        )
    )
    flags.extend(
        _alt_flags(alts, as_of=as_of, stale_mark_days=stale_mark_days)
    )
    liquidity = _liquidity_flag(positions, ips)
    if liquidity is not None:
        flags.append(liquidity)

    flags.sort(key=lambda f: (f.reason.value, f.subject_id, f.label))
    return NpaFlags(
        household_id=household_id,
        as_of_date=as_of,
        config_version=config_version,
        flags=flags,
        limitations=list(_LIMITATIONS),
    )


def _sustained_drawdown_flags(
    positions: list[LotPositionView],
    *,
    as_of: date,
    drawdown_pct: Decimal,
    sustained_years: Decimal,
) -> list[NpaFlag]:
    flags: list[NpaFlag] = []
    for pos in positions:
        if pos.acquisition_date > as_of:
            raise NpaError(
                f"lot {pos.lot_id} acquired {pos.acquisition_date} after "
                f"as_of {as_of} — walk-forward violation"
            )
        if pos.market_value is None or pos.unrealized_gain is None:
            continue  # no mark — attribution/recon owns that gap, not NPA
        if pos.total_cost_basis <= 0:
            continue
        total_return = pos.unrealized_gain / pos.total_cost_basis
        days = (as_of - pos.acquisition_date).days
        holding_years = Decimal(days) / _DAYS_PER_YEAR
        if total_return <= drawdown_pct and holding_years >= sustained_years:
            label = pos.ticker or pos.security_id
            flags.append(
                NpaFlag(
                    subject=NpaSubject.POSITION,
                    subject_id=pos.lot_id,
                    label=label,
                    reason=NpaReason.SUSTAINED_DRAWDOWN,
                    observed=total_return.quantize(_RETURN_QUANTUM),
                    threshold=drawdown_pct,
                    detail=(
                        f"{label} {total_return:.1%} below cost, held "
                        f"{holding_years:.1f}y past the {sustained_years}y "
                        "sustained window"
                    ),
                )
            )
    return flags


def _alt_flags(
    alts: Sequence[AltHoldingLike],
    *,
    as_of: date,
    stale_mark_days: int,
) -> list[NpaFlag]:
    flags: list[NpaFlag] = []
    for alt in alts:
        if alt.last_mark_date > as_of:
            raise NpaError(
                f"alt {alt.holding_id} marked {alt.last_mark_date} after "
                f"as_of {as_of} — walk-forward violation"
            )
        mark_age = (as_of - alt.last_mark_date).days
        if mark_age > stale_mark_days:
            flags.append(
                NpaFlag(
                    subject=NpaSubject.ALTERNATIVE,
                    subject_id=alt.holding_id,
                    label=alt.name,
                    reason=NpaReason.STALE_ALT_MARK,
                    observed=Decimal(mark_age),
                    threshold=Decimal(stale_mark_days),
                    detail=(
                        f"{alt.name} last marked {alt.last_mark_date} — "
                        f"{mark_age}d old (> {stale_mark_days}d floor); NAV "
                        "is suspect"
                    ),
                )
            )

        missed = [c for c in alt.scheduled_calls if c.event_date <= as_of]
        if missed and alt.unfunded_capital > 0:
            earliest = min(c.event_date for c in missed)
            flags.append(
                NpaFlag(
                    subject=NpaSubject.ALTERNATIVE,
                    subject_id=alt.holding_id,
                    label=alt.name,
                    reason=NpaReason.MISSED_CAPITAL_CALL,
                    observed=alt.unfunded_capital,
                    threshold=Decimal(0),
                    detail=(
                        f"{alt.name} — {len(missed)} capital call(s) due "
                        f"on/before {as_of} (earliest {earliest}); "
                        f"${alt.unfunded_capital:,.0f} still unfunded"
                    ),
                )
            )
    return flags


def _liquidity_flag(
    positions: list[LotPositionView],
    ips: InvestmentPolicyStatement | None,
) -> NpaFlag | None:
    if ips is None or ips.liquidity_tier_min_pct is None or not positions:
        return None
    floor = ips.liquidity_tier_min_pct
    share = liquid_tier_nav_share(positions, max_tier=_LIQUID_MAX_TIER)
    if share >= floor:
        return None
    return NpaFlag(
        subject=NpaSubject.MANIFEST,
        subject_id=ips.household_id,
        label="IPS liquidity floor",
        reason=NpaReason.IPS_LIQUIDITY_BREACH,
        observed=share.quantize(_RETURN_QUANTUM),
        threshold=floor,
        detail=(
            f"liquid tier 1+{_LIQUID_MAX_TIER} NAV share {share:.1%} below "
            f"IPS floor {floor:.1%}"
        ),
    )
