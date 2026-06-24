"""Constraint library — IPS, restricted lists, do-not-sell lots."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from warehouse.data.ledger.views import LotPositionView
from warehouse.decision.ips import InvestmentPolicyStatement


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


def active_constraint_summary(ips: InvestmentPolicyStatement) -> list[str]:
    active = [
        f"ips_target:{t.asset_class}={t.target_weight}" for t in ips.allocation_targets
    ]
    active.extend(f"ips_min:{t.asset_class}>={t.min_weight}" for t in ips.allocation_targets)
    active.extend(f"ips_max:{t.asset_class}<={t.max_weight}" for t in ips.allocation_targets)
    active.extend(f"restricted:{sid}" for sid in ips.restricted_securities)
    active.append("wash_sale_30d:monitor")
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
