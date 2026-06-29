"""SDG3 ablation falsifier — axioms-disabled generator underperforms (st5g).

Full cohort-conditioned generator must beat uniform-Dirichlet sleeve weights
on downstream emit+smoke pass rate (falsifier #50).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tests.synth_stats_helpers import ABLATON_SEEDS
from warehouse.research.synthetic.cohort import COHORT_IDS
from warehouse.research.synthetic.cohort_ablation import (
    emit_ablated_household,
    equity_weight_from_bundle,
)
from warehouse.research.synthetic.ips_validate import IpsValidationError
from warehouse.research.synthetic.pipeline import emit_synthetic_household
from warehouse.research.synthetic.workflow_smoke import run_workflow_smoke


def _rung_for(cohort_id: str) -> int:
    return 4 if cohort_id == "concentrated_stress" else 3


def _emit_and_smoke(
    *,
    cohort_id: str,
    seed: int,
    rung: int,
    ablated: bool,
) -> bool:
    try:
        if ablated:
            bundle = emit_ablated_household(
                cohort_id=cohort_id, seed=seed, rung=rung, validate=True
            )
        else:
            bundle = emit_synthetic_household(
                cohort_id=cohort_id, seed=seed, rung=rung, validate=True
            )
    except IpsValidationError:
        return False
    return run_workflow_smoke(bundle).ok


def _pass_rate(*, ablated: bool) -> float:
    passed = 0
    total = 0
    for cohort_id in COHORT_IDS:
        rung = _rung_for(cohort_id)
        for seed in ABLATON_SEEDS:
            passed += int(
                _emit_and_smoke(
                    cohort_id=cohort_id,
                    seed=seed,
                    rung=rung,
                    ablated=ablated,
                )
            )
            total += 1
    return passed / total


def test_full_generator_pass_rate_exceeds_ablated_matrix() -> None:
    full_rate = _pass_rate(ablated=False)
    ablated_rate = _pass_rate(ablated=True)
    assert full_rate > ablated_rate


def test_concentrated_stress_binds_only_on_full_generator() -> None:
    cohort_id = "concentrated_stress"
    for seed in ABLATON_SEEDS:
        full = emit_synthetic_household(
            cohort_id=cohort_id, seed=seed, rung=4, validate=False
        )
        ablated = emit_ablated_household(
            cohort_id=cohort_id, seed=seed, rung=4, validate=False
        )
        full_eq = equity_weight_from_bundle(full)
        ablated_eq = equity_weight_from_bundle(ablated)
        assert full_eq > Decimal("0.65")
        uniform_third = Decimal("1") / Decimal("3")
        assert ablated_eq == pytest.approx(uniform_third, abs=Decimal("0.02"))
        assert full_eq > ablated_eq
