"""MIP optimizer stub — lot-discrete selection without external solver.

Upgrade path: Gurobi / CPLEX for full mixed-integer formulation.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from warehouse.config import Settings, get_settings
from warehouse.data.ledger.views import LotPositionView
from warehouse.decision.constraints import (
    evaluate_lot_sell_allowed,
    evaluate_wash_sale_risk,
)
from warehouse.decision.ips import InvestmentPolicyStatement
from warehouse.decision.optimizer import OptimizationResult, TradeProposal
from warehouse.decision.optimizer.heuristics import (
    _asset_class_for_position,
    _holding_period_rate,
)


def run_mip_optimizer(
    household_id: str,
    positions: list[LotPositionView],
    ips: InvestmentPolicyStatement,
    *,
    settings: Settings | None = None,
    as_of: date | None = None,
) -> OptimizationResult:
    """Discrete lot selection — ranks TLH candidates by tax benefit per dollar sold."""
    cfg = settings or get_settings()
    today = as_of or date.today()
    trades: list[TradeProposal] = []
    binding: set[str] = set()
    tax_delta = Decimal("0")

    total_mv = sum((p.market_value or Decimal("0")) for p in positions)
    if total_mv <= 0:
        raise ValueError("Cannot optimize — portfolio has no market value")

    class_weights: dict[str, Decimal] = {}
    for pos in positions:
        if pos.market_value is None:
            continue
        ac = _asset_class_for_position(pos)
        class_weights[ac] = (
            class_weights.get(ac, Decimal("0")) + pos.market_value / total_mv
        )

    candidates: list[tuple[Decimal, LotPositionView]] = []
    for lot in positions:
        if lot.unrealized_gain is None or lot.unrealized_gain >= 0:
            continue
        allowed, lot_binding = evaluate_lot_sell_allowed(lot, ips)
        binding.update(lot_binding)
        if not allowed or lot.market_value is None:
            continue
        wash_triggers = evaluate_wash_sale_risk(lot, positions, as_of=today)
        if wash_triggers:
            binding.update(wash_triggers)
            continue
        rate = _holding_period_rate(lot.acquisition_date, today, cfg)
        benefit = abs(lot.unrealized_gain * rate)
        score = (
            benefit / lot.market_value
            if lot.market_value > 0
            else Decimal("0")
        )
        candidates.append((score, lot))

    candidates.sort(key=lambda item: item[0], reverse=True)
    max_trades = cfg.mip_max_trades
    for _score, lot in candidates[:max_trades]:
        if lot.unrealized_gain is None:
            continue
        rate = _holding_period_rate(lot.acquisition_date, today, cfg)
        harvest_tax = lot.unrealized_gain * rate
        tax_delta += harvest_tax
        trades.append(
            TradeProposal(
                lot_id=lot.lot_id,
                security_id=lot.security_id,
                account_id=lot.account_id,
                side="sell",
                quantity=lot.quantity,
                rationale=(
                    f"MIP discrete lot {lot.lot_id} score {_score:.4f} "
                    f"loss {lot.unrealized_gain:.2f} tax delta {harvest_tax:.2f}"
                ),
            )
        )

    for target in ips.allocation_targets:
        current = class_weights.get(target.asset_class, Decimal("0"))
        if current > target.max_weight:
            binding.add(f"ips_max:{target.asset_class}")
        if current < target.min_weight:
            binding.add(f"ips_min:{target.asset_class}")

    if not trades:
        binding.add("mip_no_feasible_lots")

    return OptimizationResult(
        household_id=household_id,
        config_version=cfg.tax_config_version,
        trades=trades,
        estimated_tax_delta=tax_delta,
        binding_constraints=sorted(binding),
    )
