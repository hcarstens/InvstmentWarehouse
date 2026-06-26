"""HNW leaf-type combinatorial stress — risk API harness."""

from __future__ import annotations

from decimal import Decimal

import pytest

from warehouse.research.synthetic.hnw_asset_types import (
    HNW_ASSET_TYPES,
    HnwAssetType,
    IpsExcludedError,
)
from warehouse.research.synthetic.hnw_manifest import (
    build_manifest_from_hnw_types,
)
from warehouse.research.synthetic.stress_harness import (
    iter_hnw_combinations,
    run_combination_matrix,
    run_harness_cell,
    summarize_matrix,
)


@pytest.mark.parametrize("asset_type", HNW_ASSET_TYPES)
def test_single_hnw_type_risk_or_ips_excluded(
    asset_type: HnwAssetType,
) -> None:
    cell = run_harness_cell((asset_type,))
    if asset_type in (
        HnwAssetType.PHILANTHROPIC,
        HnwAssetType.PERSONAL_USE,
    ):
        assert cell.status == "ips_excluded"
        assert cell.fingerprint is None
    else:
        assert cell.status == "ok"
        assert cell.fingerprint
        assert cell.annualized_vol is not None
        assert cell.annualized_vol > Decimal("0")


def test_pair_combinations_all_ok_or_ips_excluded() -> None:
    cells = run_combination_matrix(max_size=2, min_size=2)
    assert len(cells) == 105  # C(15, 2)
    summary = summarize_matrix(cells)
    assert summary["error"] == 0
    assert summary["ok"] + summary["ips_excluded"] == 105


def test_ips_excluded_when_philanthropic_in_mix() -> None:
    with pytest.raises(IpsExcludedError):
        build_manifest_from_hnw_types(
            (HnwAssetType.PUBLIC_EQUITY, HnwAssetType.PHILANTHROPIC)
        )
    cell = run_harness_cell(
        (HnwAssetType.PUBLIC_EQUITY, HnwAssetType.PHILANTHROPIC)
    )
    assert cell.status == "ips_excluded"


def test_equal_weight_pair_sums_to_one() -> None:
    manifest = build_manifest_from_hnw_types(
        (HnwAssetType.PUBLIC_EQUITY, HnwAssetType.FIXED_INCOME_CASH)
    )
    total = sum(slot.weight for slot in manifest.allocations)
    assert total == Decimal("1")
    assert len(manifest.allocations) == 2
    assert manifest.allocations[0].label == "public_equity"
    assert manifest.allocations[1].label == "fixed_income_cash"


def test_triple_combo_evaluates() -> None:
    cell = run_harness_cell(
        (
            HnwAssetType.PUBLIC_EQUITY,
            HnwAssetType.FIXED_INCOME_CASH,
            HnwAssetType.PE_VC,
        )
    )
    assert cell.status == "ok"
    assert cell.annualized_vol is not None


def test_combination_iterator_sizes() -> None:
    singles = list(iter_hnw_combinations(max_size=1))
    pairs = list(iter_hnw_combinations(max_size=2, min_size=2))
    assert len(singles) == 15
    assert len(pairs) == 105


def test_full_matrix_no_unexpected_errors() -> None:
    """All 32,767 subsets — investable-only cells must succeed."""
    cells = run_combination_matrix()
    summary = summarize_matrix(cells)
    assert summary["error"] == 0
    assert summary["ips_excluded"] > 0
    assert summary["ok"] > 0
    assert len(cells) == 2**15 - 1
