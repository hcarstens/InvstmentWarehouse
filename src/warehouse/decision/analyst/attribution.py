"""Position-level attribution (pa0) — implements Addendum A (§12).

``evaluate_attribution`` decomposes each lot's unrealized return into the
ex-ante class assumption scaled to the holding window
(``expected_cumulative``) and the leftover ``active_return``. The class
assumption is de-annualized onto the window (A.2) — no ``1/holding_years``
term — so the figure is stable as the window → 0.

Walk-forward safe: uses only ``acquisition_date`` and current marks against an
``as_of`` date; a future acquisition raises (CLAUDE.md walk-forward). Unmapped
asset classes raise rather than defaulting to a silent zero residual that would
mislabel an unattributed lot as fully explained.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from warehouse.data.ledger.views import LotPositionView
from warehouse.data.security_master import AssetClass as SecClass
from warehouse.decision.analyst.models import (
    AttributionReport,
    PositionAttribution,
)
from warehouse.research.risk.models import AssetClass as RiskClass

# Security-master classes → risk classes (A.1). These are *different* enums
# with different members and string values; a direct join raises KeyError.
_SEC_TO_RISK: dict[SecClass, RiskClass] = {
    SecClass.EQUITY: RiskClass.EQUITY,
    SecClass.ETF: RiskClass.EQUITY,  # v0 beta proxy — see _LIMITATIONS
    SecClass.FIXED_INCOME: RiskClass.FIXED_INCOME,
    SecClass.CASH: RiskClass.CASH,
    SecClass.ALTERNATIVE: RiskClass.ALTERNATIVES,
}

_LIMITATIONS: tuple[str, ...] = (
    "Unrealized point-in-time only — no realized lots, income or dividends.",
    "Class-beta first cut — not full factor (Brinson) attribution.",
    "ETF maps to EQUITY as a v0 beta proxy; bond/commodity ETFs are "
    "mis-mapped until look-through ships.",
    "The beta-stripped idiosyncratic component (axiom 1) is not_computed — "
    "no realized class-return series to subtract.",
)

_RETURN_QUANTUM = Decimal("0.000001")
_YEARS_QUANTUM = Decimal("0.0001")
_ONE = Decimal(1)
_DAYS_PER_YEAR = Decimal("365.25")


class AttributionError(ValueError):
    """Raised when a position cannot be attributed (e.g. unmapped class)."""


def risk_class_for(sec: SecClass) -> RiskClass:
    """Map a security class to a risk class, or raise (no silent zero)."""
    try:
        return _SEC_TO_RISK[sec]
    except KeyError as err:  # bubble to surface, never default
        raise AttributionError(
            f"no risk-class mapping for {sec!r}; cannot assign a "
            "class-expected return"
        ) from err


def evaluate_attribution(
    positions: list[LotPositionView],
    class_expected_return: Mapping[RiskClass, Decimal],
    *,
    household_id: str,
    as_of: date,
    config_version: str,
    min_holding_years: Decimal,
) -> AttributionReport:
    """Decompose each lot into ``expected_cumulative`` + ``active_return``.

    ``class_expected_return`` is the shipped ``RiskAssumptions`` mapping (keyed
    by the risk-side ``AssetClass``). Positions are returned ordered by
    ``|active_return|`` (the primary signal); the portfolio figure is
    market-value-weighted (A.5).
    """
    rows: list[PositionAttribution] = []
    for pos in positions:
        rows.append(
            _attribute_one(
                pos,
                class_expected_return,
                as_of=as_of,
                min_holding_years=min_holding_years,
            )
        )
    rows.sort(key=lambda r: abs(r.active_return), reverse=True)
    return AttributionReport(
        household_id=household_id,
        as_of_date=as_of,
        config_version=config_version,
        positions=rows,
        portfolio_active_return=_mv_weighted_active(rows),
        limitations=list(_LIMITATIONS),
    )


def _attribute_one(
    pos: LotPositionView,
    class_expected_return: Mapping[RiskClass, Decimal],
    *,
    as_of: date,
    min_holding_years: Decimal,
) -> PositionAttribution:
    if pos.acquisition_date > as_of:
        raise AttributionError(
            f"lot {pos.lot_id} acquired {pos.acquisition_date} after as_of "
            f"{as_of} — walk-forward violation"
        )
    if pos.market_value is None or pos.unrealized_gain is None:
        raise AttributionError(
            f"lot {pos.lot_id} has no market value; cannot attribute return"
        )
    if pos.total_cost_basis <= 0:
        raise AttributionError(
            f"lot {pos.lot_id} has non-positive cost basis "
            f"{pos.total_cost_basis}; cannot compute return"
        )

    risk_class = risk_class_for(pos.security_asset_class)
    try:
        class_expected = class_expected_return[risk_class]
    except KeyError as err:
        raise AttributionError(
            f"no class-expected return for {risk_class!r}"
        ) from err

    days = max((as_of - pos.acquisition_date).days, 0)
    holding_years = Decimal(days) / _DAYS_PER_YEAR
    total_return = pos.unrealized_gain / pos.total_cost_basis
    # De-annualize the class assumption onto the window (A.2): stable as h→0,
    # no 1/holding_years explosion. h=0 → expected_cumulative=0.
    expected_cumulative = (_ONE + class_expected) ** holding_years - _ONE
    active_return = total_return - expected_cumulative
    active_annualized = _annualized_active(
        total_return, class_expected, holding_years, min_holding_years
    )
    return PositionAttribution(
        lot_id=pos.lot_id,
        account_id=pos.account_id,
        ticker=pos.ticker,
        security_asset_class=pos.security_asset_class,
        risk_class=risk_class,
        holding_years=holding_years.quantize(_YEARS_QUANTUM),
        market_value=pos.market_value,
        total_return=total_return.quantize(_RETURN_QUANTUM),
        class_expected=class_expected,
        expected_cumulative=expected_cumulative.quantize(_RETURN_QUANTUM),
        active_return=active_return.quantize(_RETURN_QUANTUM),
        active_annualized=(
            None
            if active_annualized is None
            else active_annualized.quantize(_RETURN_QUANTUM)
        ),
    )


def _annualized_active(
    total_return: Decimal,
    class_expected: Decimal,
    holding_years: Decimal,
    min_holding_years: Decimal,
) -> Decimal | None:
    """Annualized active return, or ``None`` below the holding floor (A.5).

    Below ``min_holding_years`` annualizing a short window amplifies noise, so
    the figure is honestly ``not_computed``. A wipeout (``total_return ≤ -1``)
    has no real annual root → also ``None``.
    """
    if holding_years < min_holding_years or holding_years <= 0:
        return None
    one_plus = _ONE + total_return
    if one_plus <= 0:
        return None
    realized_annual = one_plus ** (_ONE / holding_years) - _ONE
    return realized_annual - class_expected


def _mv_weighted_active(rows: list[PositionAttribution]) -> Decimal:
    total_mv = sum((r.market_value for r in rows), Decimal(0))
    if total_mv <= 0:
        return Decimal(0)
    weighted = sum(
        ((r.market_value / total_mv) * r.active_return for r in rows),
        Decimal(0),
    )
    return weighted.quantize(_RETURN_QUANTUM)
