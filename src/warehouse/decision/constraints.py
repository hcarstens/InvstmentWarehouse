"""Constraint library — IPS, restricted lists, do-not-sell lots."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from warehouse.data.ledger.views import LotPositionView
from warehouse.decision.ips import InvestmentPolicyStatement

WASH_SALE_WINDOW_DAYS = 30


@dataclass
class ConstraintReport:
    active_constraints: list[str] = field(default_factory=list)
    binding_constraints: list[str] = field(default_factory=list)


def evaluate_lot_sell_allowed(
    lot: LotPositionView,
    ips: InvestmentPolicyStatement,
) -> tuple[bool, list[str]]:
    binding: list[str] = []
    if lot.is_restricted:
        binding.append(f"do_not_sell_lot:{lot.lot_id}")
        return False, binding
    if lot.security_id in ips.restricted_securities:
        binding.append(f"restricted_security:{lot.security_id}")
        return False, binding
    return True, binding


def _substantially_identical(a: LotPositionView, b: LotPositionView) -> bool:
    """Wash-sale identity: same security, or same wash-sale substitute group."""
    if a.security_id == b.security_id:
        return True
    group = a.wash_sale_substitute_group
    return group is not None and group == b.wash_sale_substitute_group


def evaluate_wash_sale_risk(
    lot: LotPositionView,
    positions: list[LotPositionView],
    *,
    as_of: date,
    window_days: int = WASH_SALE_WINDOW_DAYS,
) -> list[str]:
    """Detect whether harvesting ``lot`` at a loss would trigger a wash sale.

    A wash sale disallows the loss when substantially identical securities (same
    security or same wash-sale substitute group) are acquired within ``±window_days``
    of realizing it — in ANY household account. We scan all current lots for such a
    replacement purchase and return one binding-constraint tag per offending lot.
    An empty list means the harvest is clear to propose.
    """
    triggers: list[str] = []
    for other in positions:
        if other.lot_id == lot.lot_id:
            continue
        if not _substantially_identical(lot, other):
            continue
        if abs((other.acquisition_date - as_of).days) <= window_days:
            triggers.append(f"wash_sale_30d:{lot.lot_id}<-{other.lot_id}")
    return triggers


def active_constraint_summary(ips: InvestmentPolicyStatement) -> list[str]:
    active = [
        f"ips_target:{t.asset_class}={t.target_weight}"
        for t in ips.allocation_targets
    ]
    active.extend(
        f"ips_min:{t.asset_class}>={t.min_weight}"
        for t in ips.allocation_targets
    )
    active.extend(
        f"ips_max:{t.asset_class}<={t.max_weight}"
        for t in ips.allocation_targets
    )
    active.extend(f"restricted:{sid}" for sid in ips.restricted_securities)
    active.append("wash_sale_30d:enforced")
    active.append("tax_config:version_pinned")
    return active


def drift_vs_ips(
    weights: dict[str, Decimal],
    ips: InvestmentPolicyStatement,
) -> list[str]:
    alerts: list[str] = []
    for target in ips.allocation_targets:
        current = weights.get(target.asset_class, Decimal("0"))
        if current < target.min_weight:
            alerts.append(
                f"{target.asset_class} below min ({current:.1%} < {target.min_weight:.1%})"
            )
        if current > target.max_weight:
            alerts.append(
                f"{target.asset_class} above max ({current:.1%} > {target.max_weight:.1%})"
            )
        drift = abs(current - target.target_weight)
        if drift > Decimal("0.05"):
            alerts.append(
                f"{target.asset_class} drift {drift:.1%} from target {target.target_weight:.1%}"
            )
    return alerts
