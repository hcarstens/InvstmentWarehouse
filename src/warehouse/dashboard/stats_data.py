"""Daily Movements panel data (pv2) — real FIIJ ingest + stats engine output.

Thin loader (M4 — engines live in-plane, the dashboard only consumes): emit an
in-process ``general_hnw`` rung-3 book (no DB, §8), ingest the packaged FIIJ
finance-view sample (``ingest.fiij`` → ``signal`` views + regime), seed a
deterministic price series for the book's securities (one synthetic ~3σ move so
the significance leg is visible), and run the daily-statistics engine
(``stats.daily``).

Honest by construction (§2 / §11 A.3): FIIJ views are ``signal``-sourced (never
fabricated), a failing-OOS-Brier signal is ingested below the confidence floor
and never upgraded, the factor attribution leg renders ``not_computed``, and
the panel DISCLOSES this is a **sleeve-level** rollup — FIIJ's cross-sectional
(name-picking) edge is discarded (``name dispersion not expressed``). Failures
surface in ``error``.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from decimal import Decimal

from pydantic import BaseModel

from warehouse.data.ingest.fiij import load_fiij_snapshot
from warehouse.data.ledger.views import LotPositionView
from warehouse.decision.pm import build_working_set_from_bundle
from warehouse.research.stats import PriceObservation, stats_daily
from warehouse.research.synthetic import emit_synthetic_household

_STATS_COHORT = "general_hnw"
_STATS_SEED = 42
_STATS_RUNG = 3
_SERIES_DAYS = 12

# The one place the sleeve-level altitude is disclosed on-screen (§11 A.3): the
# rollup nets FIIJ macro/strategy signals to a tilt per 6-sleeve and DISCARDS
# the cross-sectional name-picking edge. Rendered verbatim; scanned by the
# panel test — never imply the book acts on individual FIIJ names.
SLEEVE_LEVEL_DISCLOSURE = (
    "Sleeve-level rollup — name dispersion not expressed. FIIJ's "
    "cross-sectional (name-picking) edge is discarded here (long NVDA / short "
    "MSFT nets to ~neutral equity); the book does not act on individual FIIJ "
    "names. Recovering that edge is pv5 (hierarchical name selection), not "
    "naïve instrument MV."
)


class StatsMoveRow(BaseModel):
    security_id: str
    ticker: str
    ret: Decimal
    ewma_vol: Decimal
    zscore: Decimal
    significant: bool


class FiijViewRow(BaseModel):
    sleeve: str
    source_ref: str
    expected_excess: Decimal
    confidence: Decimal
    calibration: str


class StatsAttributionRow(BaseModel):
    ticker: str
    total_return: Decimal
    active_return: Decimal
    active_annualized: str  # "not_computed" when None (factor leg honest)


class DailyMovementsData(BaseModel):
    household_id: str
    cohort_id: str
    as_of_date: date
    regime_label: str
    regime_class: str
    stats_config_version: str
    fiij_config_version: str
    rolling_corr_note: str
    disclosure: str = SLEEVE_LEVEL_DISCLOSURE
    moves: list[StatsMoveRow]
    fiij_views: list[FiijViewRow]
    attribution: list[StatsAttributionRow]
    limitations: list[str]
    panel_status: str = "live"
    error: str | None = None


def _synthetic_series(
    positions: list[LotPositionView],
    as_of: date,
) -> list[PriceObservation]:
    """Deterministic dated price series per security ending at ``as_of``.

    No RNG (walk-forward reproducible): returns derive from a hash of the
    security id. The lexically-first security gets a synthetic ~+8% last move
    so the significance leg is demonstrably ``significant`` on the panel.
    """
    securities: dict[str, Decimal] = {}
    for pos in positions:
        base = pos.market_price or (
            (pos.market_value / pos.quantity)
            if pos.market_value and pos.quantity
            else Decimal("100")
        )
        securities.setdefault(pos.security_id, Decimal(str(base)))
    if not securities:
        return []
    spike_sec = min(securities)
    obs: list[PriceObservation] = []
    for security_id, base in securities.items():
        seed = int(hashlib.sha256(security_id.encode()).hexdigest(), 16)
        rets = [((seed >> i) % 21 - 10) / 1000.0 for i in range(_SERIES_DAYS)]
        rets[-1] = 0.08 if security_id == spike_sec else rets[-1]
        price = float(base)
        # Walk backwards from as_of so the last observation is dated as_of.
        start = as_of - timedelta(days=_SERIES_DAYS - 1)
        for i, r in enumerate(rets):
            price = price * (1.0 + r)
            obs.append(
                PriceObservation(
                    security_id=security_id,
                    as_of_date=start + timedelta(days=i),
                    price=Decimal(str(round(price, 6))),
                )
            )
    return obs


def load_daily_movements_dashboard() -> DailyMovementsData:
    try:
        bundle = emit_synthetic_household(
            cohort_id=_STATS_COHORT, seed=_STATS_SEED, rung=_STATS_RUNG
        )
        book = build_working_set_from_bundle(bundle)

        # FIIJ read is walk-forward safe: pick the latest snapshot ≤ today; the
        # panel's as_of is that snapshot's date (one coherent as_of).
        snapshot = load_fiij_snapshot(date.today())
        as_of = snapshot.as_of_date

        price_history = _synthetic_series(book.positions, as_of)
        report = stats_daily(book, as_of, price_history)

        ticker_by_sec = {
            pos.security_id: (pos.ticker or pos.security_id)
            for pos in book.positions
        }
        moves = [
            StatsMoveRow(
                security_id=m.security_id,
                ticker=ticker_by_sec.get(m.security_id, m.security_id),
                ret=m.ret,
                ewma_vol=m.ewma_vol,
                zscore=m.zscore,
                significant=m.significant,
            )
            for m in report.moves
        ]
        fiij_views = [
            FiijViewRow(
                sleeve=v.sleeve.value,
                source_ref=v.source_ref or "",
                expected_excess=v.expected_excess,
                confidence=v.confidence,
                calibration=v.calibration,
            )
            for v in snapshot.views
        ]
        attribution = [
            StatsAttributionRow(
                ticker=a.ticker or a.lot_id,
                total_return=a.total_return,
                active_return=a.active_return,
                active_annualized=(
                    "not_computed"
                    if a.active_annualized is None
                    else str(a.active_annualized)
                ),
            )
            for a in report.attribution
        ]
        return DailyMovementsData(
            household_id=book.household_id,
            cohort_id=_STATS_COHORT,
            as_of_date=as_of,
            regime_label=snapshot.regime_label,
            regime_class=snapshot.regime_class,
            stats_config_version=report.stats_config_version,
            fiij_config_version=snapshot.fiij_config_version,
            rolling_corr_note=report.rolling_corr_note,
            moves=moves,
            fiij_views=fiij_views,
            attribution=attribution,
            limitations=list(report.limitations),
        )
    except Exception as err:
        return DailyMovementsData(
            household_id="(unavailable)",
            cohort_id=_STATS_COHORT,
            as_of_date=date.today(),
            regime_label="(unavailable)",
            regime_class="(unavailable)",
            stats_config_version="(unavailable)",
            fiij_config_version="(unavailable)",
            rolling_corr_note="not_computed",
            moves=[],
            fiij_views=[],
            attribution=[],
            limitations=[],
            panel_status="error",
            error=str(err),
        )
