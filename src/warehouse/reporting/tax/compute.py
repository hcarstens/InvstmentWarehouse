"""Pure tax math for reporting scenarios — independent oracles (ST2)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from warehouse.config import Settings, get_settings
from warehouse.data.ledger.views import LotPositionView
from warehouse.decision.tax.scenarios import TaxScenarioOverlays


def holding_period_rate(
    acquisition_date: date,
    as_of: date,
    settings: Settings,
) -> Decimal:
    """Federal rate from holding period — STCG below 365 days, else LTCG."""
    days = (as_of - acquisition_date).days
    rate = settings.fed_ltcg_rate if days >= 365 else settings.fed_stcg_rate
    return Decimal(str(rate))


def tax_on_realized_gain(
    gain: Decimal,
    rate: Decimal,
    *,
    apply_niit: bool,
    settings: Settings,
) -> Decimal:
    """Tax liability from realizing gain at rate (optional NIIT overlay)."""
    tax = gain * rate
    if apply_niit and gain > Decimal("0"):
        tax += gain * Decimal(str(settings.niit_rate))
    return tax


def _position_gain_tax(
    pos: LotPositionView,
    *,
    as_of: date,
    apply_niit: bool,
    settings: Settings,
) -> Decimal:
    if pos.unrealized_gain is None:
        return Decimal("0")
    rate = holding_period_rate(pos.acquisition_date, as_of, settings)
    return tax_on_realized_gain(
        pos.unrealized_gain,
        rate,
        apply_niit=apply_niit,
        settings=settings,
    )


def compute_reporting_tax_scenario(
    positions: list[LotPositionView],
    overlays: TaxScenarioOverlays | None = None,
    *,
    as_of: date | None = None,
    settings: Settings | None = None,
) -> tuple[Decimal, Decimal, Decimal]:
    """Baseline, scenario, and delta tax for hypothetical realization."""
    cfg = settings or get_settings()
    policy = overlays or TaxScenarioOverlays()
    effective_as_of = as_of or date.today()

    baseline = sum(
        (
            _position_gain_tax(
                pos,
                as_of=effective_as_of,
                apply_niit=False,
                settings=cfg,
            )
            for pos in positions
        ),
        Decimal("0"),
    )
    scenario = sum(
        (
            _position_gain_tax(
                pos,
                as_of=effective_as_of,
                apply_niit=policy.apply_niit,
                settings=cfg,
            )
            for pos in positions
        ),
        Decimal("0"),
    )
    return baseline, scenario, scenario - baseline
