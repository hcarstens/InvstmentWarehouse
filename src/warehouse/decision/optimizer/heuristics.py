"""Tax-aware optimizer v0 — TLH heuristics + greedy rebalance."""

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


def _holding_period_rate(acquisition_date: date, as_of: date, settings: Settings) -> Decimal:
    days = (as_of - acquisition_date).days
    rate = settings.fed_ltcg_rate if days >= 365 else settings.fed_stcg_rate
    return Decimal(str(rate))


def _tax_on_gain(gain: Decimal, rate: Decimal) -> Decimal:
    """Tax-liability delta from realizing ``gain`` at ``rate``, vs the do-nothing baseline.

    Sign convention: positive = additional tax owed (realized gain), negative = tax
    reduced (harvested loss, where ``gain < 0``). Harvesting losses therefore lowers
    ``estimated_tax_delta`` — a negative delta is the after-tax benefit.
    """
    return gain * rate


def run_tax_aware_optimizer(
    household_id: str,
    positions: list[LotPositionView],
    ips: InvestmentPolicyStatement,
    *,
    settings: Settings | None = None,
    as_of: date | None = None,
    input_snapshot_id: str = "snapshot_local",
) -> OptimizationResult:
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
        class_weights[ac] = class_weights.get(
            ac, Decimal("0")) + pos.market_value / total_mv

    loss_lots = sorted(
        [p for p in positions if p.unrealized_gain is not None and p.unrealized_gain < 0],
        key=lambda p: p.unrealized_gain or Decimal("0"),
    )

    for lot in loss_lots:
        allowed, lot_binding = evaluate_lot_sell_allowed(lot, ips)
        binding.update(lot_binding)
        if not allowed:
            continue
        if lot.unrealized_gain is None or lot.market_value is None:
            continue
        wash_triggers = evaluate_wash_sale_risk(lot, positions, as_of=today)
        if wash_triggers:
            binding.update(wash_triggers)
            continue
        rate = _holding_period_rate(lot.acquisition_date, today, cfg)
        harvest_tax = _tax_on_gain(lot.unrealized_gain, rate)
        tax_delta += harvest_tax
        trades.append(
            TradeProposal(
                lot_id=lot.lot_id,
                security_id=lot.security_id,
                account_id=lot.account_id,
                side="sell",
                quantity=lot.quantity,
                rationale=(
                    f"TLH harvest unrealized loss {lot.unrealized_gain:.2f} "
                    f"({lot.ticker}, est tax delta {harvest_tax:.2f})"
                ),
            )
        )

    for target in ips.allocation_targets:
        current = class_weights.get(target.asset_class, Decimal("0"))
        if current > target.max_weight:
            binding.add(f"ips_max:{target.asset_class}")
        if current < target.min_weight:
            binding.add(f"ips_min:{target.asset_class}")

    if not trades and binding:
        binding.add("no_action:constraints_or_no_loss_lots")

    return OptimizationResult(
        household_id=household_id,
        config_version=cfg.tax_config_version,
        trades=trades,
        estimated_tax_delta=tax_delta,
        binding_constraints=sorted(binding),
    )


def _asset_class_for_position(pos: LotPositionView) -> str:
    ticker = pos.ticker or ""
    if ticker in {"VTI", "BND"}:
        return "etf"
    return "equity"
