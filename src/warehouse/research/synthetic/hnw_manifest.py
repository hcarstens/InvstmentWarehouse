"""Build Shape A manifests from HNW leaf-type combinations."""

from __future__ import annotations

from decimal import Decimal

from warehouse.research.risk.models import AllocationSlot, AssetPortfolio
from warehouse.research.synthetic.hnw_asset_types import (
    HnwAssetType,
    IpsExcludedError,
    hnw_asset_spec,
    ips_excluded_types,
)


def build_manifest_from_hnw_types(
    types: tuple[HnwAssetType, ...],
    *,
    portfolio_id: str | None = None,
    seed: int | None = None,
) -> AssetPortfolio:
    """Equal-weight manifest over selected leaf types (one slot per type).

    Raises ``IpsExcludedError`` when any selected type is outside the IPS
    investable numerator (philanthropic, personal-use).
    """
    if not types:
        raise ValueError("at least one HNW asset type required")

    excluded = ips_excluded_types(types)
    if excluded:
        names = ", ".join(t.value for t in excluded)
        raise IpsExcludedError(
            f"IPS excludes non-investable asset type(s): {names}"
        )

    n = len(types)
    unit = (Decimal("1") / Decimal(n)).quantize(Decimal("0.0000001"))
    assigned = Decimal("0")
    allocations: list[AllocationSlot] = []

    for index, asset_type in enumerate(types):
        if index == len(types) - 1:
            weight = Decimal("1") - assigned
        else:
            weight = unit
            assigned += weight

        spec = hnw_asset_spec(asset_type)
        allocations.append(
            AllocationSlot(
                asset_class=spec.risk_class,
                weight=weight,
                duration_years=spec.duration_years,
                beta=spec.beta,
                liquidity_tier=spec.liquidity_tier,
                measurement=spec.measurement,
                label=asset_type.value,
            )
        )

    pid = portfolio_id or f"hnw-{'-'.join(t.value for t in types)}"
    return AssetPortfolio(
        portfolio_id=pid,
        source="synthetic",
        complexity=len(types),
        seed=seed,
        tension_tags=["hnw_leaf_combo"],
        allocations=allocations,
    )
