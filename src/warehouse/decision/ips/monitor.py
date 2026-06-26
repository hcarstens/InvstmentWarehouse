"""IPS drift and concentration monitoring."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from warehouse.data.ledger.views import LotPositionView
from warehouse.decision.constraints import drift_vs_ips
from warehouse.decision.ips import InvestmentPolicyStatement
from warehouse.decision.ips.store import load_ips


class AllocationDriftRow(BaseModel):
    asset_class: str
    current_weight: Decimal
    target_weight: Decimal
    min_weight: Decimal
    max_weight: Decimal
    drift: Decimal


class IpsDriftReport(BaseModel):
    household_id: str
    rows: list[AllocationDriftRow]
    alerts: list[str]
    concentration_alerts: list[str]


def _class_for_ticker(ticker: str | None) -> str:
    if ticker in {"VTI", "BND"}:
        return "etf"
    return "equity"


def build_ips_drift_report(
    session: Session,
    household_id: str,
    positions: list[LotPositionView],
    ips: InvestmentPolicyStatement | None = None,
) -> IpsDriftReport:
    policy = ips or load_ips(session, household_id)
    if policy is None:
        raise ValueError(f"No IPS found for household {household_id}")

    total_mv = sum((p.market_value or Decimal("0")) for p in positions)
    class_mv: dict[str, Decimal] = {}
    for pos in positions:
        if pos.market_value is None:
            continue
        ac = _class_for_ticker(pos.ticker)
        class_mv[ac] = class_mv.get(ac, Decimal("0")) + pos.market_value

    rows: list[AllocationDriftRow] = []
    weights: dict[str, Decimal] = {}
    for target in policy.allocation_targets:
        mv = class_mv.get(target.asset_class, Decimal("0"))
        current = mv / total_mv if total_mv > 0 else Decimal("0")
        weights[target.asset_class] = current
        rows.append(
            AllocationDriftRow(
                asset_class=target.asset_class,
                current_weight=current,
                target_weight=target.target_weight,
                min_weight=target.min_weight,
                max_weight=target.max_weight,
                drift=current - target.target_weight,
            )
        )

    concentration: list[str] = []
    if total_mv > 0:
        for pos in positions:
            if pos.market_value is None:
                continue
            weight = pos.market_value / total_mv
            if weight > Decimal("0.25"):
                concentration.append(
                    f"{pos.ticker} concentration {weight:.1%}")

    return IpsDriftReport(
        household_id=household_id,
        rows=rows,
        alerts=drift_vs_ips(weights, policy),
        concentration_alerts=concentration,
    )
