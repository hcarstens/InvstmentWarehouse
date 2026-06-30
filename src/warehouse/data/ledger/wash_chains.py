"""Wash-sale chain assignment for chronological lot streams (qa3).

Links lots that participate in the same wash-sale sequence via transitive
merge. Lots not wash-linked to any other lot keep ``wash_sale_chain_id=None``.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from warehouse.data.ledger import Lot

WASH_SALE_WINDOW_DAYS = 30


@dataclass(frozen=True)
class WashSaleSellEvent:
    """Loss harvest on ``lot_id`` that may trigger wash-sale linkage."""

    lot_id: str
    sell_date: date
    at_loss: bool = True


def substantially_identical_securities(
    security_a: str,
    security_b: str,
    *,
    group_a: str | None,
    group_b: str | None,
) -> bool:
    """Wash-sale identity: same security or same substitute group."""
    if security_a == security_b:
        return True
    return group_a is not None and group_a == group_b


def _within_wash_window(
    acquisition: date,
    sell_date: date,
    *,
    window_days: int,
) -> bool:
    return abs((acquisition - sell_date).days) <= window_days


class _UnionFind:
    def __init__(self, keys: Sequence[str]) -> None:
        self._parent = {key: key for key in keys}

    def find(self, key: str) -> str:
        while self._parent[key] != key:
            self._parent[key] = self._parent[self._parent[key]]
            key = self._parent[key]
        return key

    def union(self, left: str, right: str) -> None:
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left != root_right:
            self._parent[root_right] = root_left


def assign_wash_sale_chain_ids(
    lots: list[Lot],
    *,
    security_groups: Mapping[str, str | None],
    sells: Sequence[WashSaleSellEvent],
    window_days: int = WASH_SALE_WINDOW_DAYS,
) -> list[Lot]:
    """Return lots with ``wash_sale_chain_id`` set for wash-linked components.

    Components of size two or more receive a stable chain id (lexicographic
    minimum ``lot_id`` in the component). Singleton lots keep ``None``.
    """
    if not lots:
        return []

    lot_by_id = {lot.lot_id: lot for lot in lots}
    unknown = {sell.lot_id for sell in sells if sell.lot_id not in lot_by_id}
    if unknown:
        missing = ", ".join(sorted(unknown))
        raise ValueError(f"unknown sell lot_id(s): {missing}")

    uf = _UnionFind([lot.lot_id for lot in lots])

    for sell in sells:
        if not sell.at_loss:
            continue
        sold = lot_by_id[sell.lot_id]
        sold_group = security_groups.get(sold.security_id)
        for other in lots:
            if other.lot_id == sold.lot_id:
                continue
            other_group = security_groups.get(other.security_id)
            if not substantially_identical_securities(
                sold.security_id,
                other.security_id,
                group_a=sold_group,
                group_b=other_group,
            ):
                continue
            if _within_wash_window(
                other.acquisition_date,
                sell.sell_date,
                window_days=window_days,
            ):
                uf.union(sold.lot_id, other.lot_id)

    components: dict[str, list[str]] = defaultdict(list)
    for lot_id in lot_by_id:
        components[uf.find(lot_id)].append(lot_id)

    chain_for_lot: dict[str, str | None] = {}
    for members in components.values():
        if len(members) < 2:
            for member in members:
                chain_for_lot[member] = None
        else:
            chain_id = min(members)
            for member in members:
                chain_for_lot[member] = chain_id

    return [
        lot.model_copy(
            update={"wash_sale_chain_id": chain_for_lot[lot.lot_id]},
        )
        for lot in lots
    ]


def linked_lot_ids_for_sell(
    sold: Lot,
    lots: Sequence[Lot],
    *,
    security_groups: Mapping[str, str | None],
    sell_date: date,
    window_days: int = WASH_SALE_WINDOW_DAYS,
) -> frozenset[str]:
    """Lots wash-linked to ``sold`` on ``sell_date`` (oracle helper)."""
    sold_group = security_groups.get(sold.security_id)
    linked: set[str] = {sold.lot_id}
    for other in lots:
        if other.lot_id == sold.lot_id:
            continue
        other_group = security_groups.get(other.security_id)
        if not substantially_identical_securities(
            sold.security_id,
            other.security_id,
            group_a=sold_group,
            group_b=other_group,
        ):
            continue
        if _within_wash_window(
            other.acquisition_date,
            sell_date,
            window_days=window_days,
        ):
            linked.add(other.lot_id)
    return frozenset(linked)
