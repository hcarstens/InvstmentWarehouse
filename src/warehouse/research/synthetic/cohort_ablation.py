"""SDG3 ablation entry — axioms-disabled household emission (st5g)."""

from __future__ import annotations

from decimal import Decimal

from warehouse.research.risk.models import AssetClass
from warehouse.research.synthetic.cohort import sample_sleeve_weights_uniform
from warehouse.research.synthetic.models import SyntheticHouseholdBundle
from warehouse.research.synthetic.pipeline import emit_synthetic_household


def emit_ablated_household(
    *,
    cohort_id: str,
    seed: int,
    rung: int = 3,
    validate: bool = True,
) -> SyntheticHouseholdBundle:
    """Uniform weights — negation of cohort-conditioned priors (SDG3)."""
    weights = sample_sleeve_weights_uniform(cohort_id, seed)
    return emit_synthetic_household(
        cohort_id=cohort_id,
        seed=seed,
        rung=rung,
        validate=validate,
        weights=weights,
    )


def equity_weight_from_bundle(bundle: SyntheticHouseholdBundle) -> Decimal:
    """Shape-A equity sleeve — downstream oracle for binding checks."""
    portfolio = bundle.fixture.asset_portfolio
    if portfolio is None:
        raise ValueError("bundle missing asset_portfolio projection")
    for slot in portfolio.allocations:
        if slot.asset_class == AssetClass.EQUITY:
            return slot.weight
    return Decimal("0")
