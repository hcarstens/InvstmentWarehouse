"""Synthetic rung ladder tests."""

from decimal import Decimal

import pytest

from warehouse.research.risk.models import AssetClass
from warehouse.research.risk.synthetic import rung


def test_rung_weights_sum_to_one() -> None:
    for level in (0, 1, 2, 3, 4):
        portfolio = rung(level)
        total = sum(slot.weight for slot in portfolio.allocations)
        assert total == Decimal("1")
        assert portfolio.source == "synthetic"
        assert portfolio.complexity == level


def test_rung_0_is_single_equity() -> None:
    portfolio = rung(0)
    assert len(portfolio.allocations) == 1
    assert portfolio.allocations[0].asset_class == AssetClass.EQUITY
    assert portfolio.allocations[0].beta == Decimal("1")


def test_rung_2_includes_commodities_and_fx() -> None:
    classes = {slot.asset_class for slot in rung(2).allocations}
    assert AssetClass.COMMODITIES in classes
    assert AssetClass.FX in classes


def test_rung_out_of_range_raises() -> None:
    with pytest.raises(ValueError, match="not defined"):
        rung(5)
