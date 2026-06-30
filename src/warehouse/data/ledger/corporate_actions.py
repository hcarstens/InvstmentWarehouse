"""Corporate actions on lot ledger — stock splits (qa4).

Adjusts quantity and per-share basis while preserving total cost basis.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext

from warehouse.data.ledger import Lot

_SPLIT_CONTEXT_PREC = 50


def oracle_stock_split_basis(
    quantity: Decimal,
    cost_basis_per_share: Decimal,
    ratio: Decimal,
) -> tuple[Decimal, Decimal]:
    """ST2 independent oracle — total cost basis is invariant under split."""
    if ratio <= 0:
        raise ValueError(f"split ratio must be positive, got {ratio}")
    new_qty = quantity * ratio
    if new_qty <= 0:
        msg = (
            f"split ratio {ratio} reduces quantity {quantity} "
            "to zero or negative"
        )
        raise ValueError(msg)
    with localcontext() as ctx:
        ctx.prec = _SPLIT_CONTEXT_PREC
        new_cost = cost_basis_per_share / ratio
    return new_qty, new_cost


@dataclass(frozen=True)
class StockSplitAction:
    """Forward or reverse stock split for ``security_id``.

    ``ratio`` is new shares per existing share — e.g. ``Decimal("2")`` for a
    2-for-1 split, ``Decimal("0.1")`` for a 1-for-10 reverse split.
    """

    security_id: str
    ratio: Decimal


def apply_stock_split(
    lots: list[Lot],
    action: StockSplitAction,
) -> list[Lot]:
    """Return lots after applying ``action`` to matching security rows."""
    if action.ratio <= 0:
        raise ValueError(f"split ratio must be positive, got {action.ratio}")

    updated: list[Lot] = []
    for lot in lots:
        if lot.security_id != action.security_id:
            updated.append(lot)
            continue
        new_qty, new_cost = oracle_stock_split_basis(
            lot.quantity,
            lot.cost_basis_per_share,
            action.ratio,
        )
        updated.append(
            lot.model_copy(
                update={
                    "quantity": new_qty,
                    "cost_basis_per_share": new_cost,
                },
            ),
        )
    return updated


def apply_stock_splits(
    lots: list[Lot],
    actions: list[StockSplitAction],
) -> list[Lot]:
    """Apply corporate split actions in order."""
    result = lots
    for action in actions:
        result = apply_stock_split(result, action)
    return result
