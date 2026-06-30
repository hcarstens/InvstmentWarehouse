"""qa4 — corporate actions on lot ledger (ST2 basis oracle)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from warehouse.data.ledger import Lot
from warehouse.data.ledger.corporate_actions import (
    StockSplitAction,
    apply_stock_split,
    apply_stock_splits,
    oracle_stock_split_basis,
)

# --- independent oracles -----------------------------------------------------


def _total_basis(lot: Lot) -> Decimal:
    return lot.quantity * lot.cost_basis_per_share


def _sample_lot(
    *,
    lot_id: str = "lot_a",
    security_id: str = "sec_aapl",
    quantity: Decimal = Decimal("100"),
    cost_basis_per_share: Decimal = Decimal("150"),
) -> Lot:
    return Lot(
        lot_id=lot_id,
        account_id="acct_taxable",
        security_id=security_id,
        quantity=quantity,
        cost_basis_per_share=cost_basis_per_share,
        acquisition_date=date(2020, 3, 15),
        wash_sale_chain_id="chain_1",
        is_restricted=True,
    )


# --- hand-math falsifiers ----------------------------------------------------


def test_stock_split_2_for_1_preserves_total_basis() -> None:
    """qa4 — 2:1 split doubles qty and halves per-share basis."""
    lot = _sample_lot()
    before_total = _total_basis(lot)
    action = StockSplitAction(security_id="sec_aapl", ratio=Decimal("2"))
    merged = apply_stock_split([lot], action)
    assert len(merged) == 1
    result = merged[0]
    assert result.quantity == Decimal("200")
    assert result.cost_basis_per_share == Decimal("75")
    assert _total_basis(result) == before_total
    expected_qty, expected_cost = oracle_stock_split_basis(
        lot.quantity,
        lot.cost_basis_per_share,
        action.ratio,
    )
    assert result.quantity == expected_qty
    assert result.cost_basis_per_share == expected_cost


def test_stock_split_reverse_1_for_10_preserves_total_basis() -> None:
    """qa4/ST6 — reverse split shrinks qty and raises per-share basis."""
    lot = _sample_lot(
        quantity=Decimal("1000"),
        cost_basis_per_share=Decimal("2"),
    )
    before_total = _total_basis(lot)
    action = StockSplitAction(security_id="sec_aapl", ratio=Decimal("0.1"))
    result = apply_stock_split([lot], action)[0]
    assert result.quantity == Decimal("100")
    assert result.cost_basis_per_share == Decimal("20")
    assert _total_basis(result) == before_total


def test_stock_split_other_securities_unchanged() -> None:
    """qa4 — only the targeted security_id is adjusted."""
    aapl = _sample_lot(lot_id="lot_aapl", security_id="sec_aapl")
    vti = _sample_lot(
        lot_id="lot_vti",
        security_id="sec_vti",
        quantity=Decimal("50"),
        cost_basis_per_share=Decimal("200"),
    )
    action = StockSplitAction(security_id="sec_aapl", ratio=Decimal("3"))
    merged = apply_stock_split([aapl, vti], action)
    by_id = {lot.lot_id: lot for lot in merged}
    assert by_id["lot_aapl"].quantity == Decimal("300")
    assert by_id["lot_vti"] == vti


def test_stock_split_preserves_metadata() -> None:
    """qa4 — lot_id, acquisition_date, wash chain, restriction survive."""
    lot = _sample_lot()
    result = apply_stock_split(
        [lot],
        StockSplitAction(security_id="sec_aapl", ratio=Decimal("2")),
    )[0]
    assert result.lot_id == lot.lot_id
    assert result.account_id == lot.account_id
    assert result.acquisition_date == lot.acquisition_date
    assert result.wash_sale_chain_id == lot.wash_sale_chain_id
    assert result.is_restricted == lot.is_restricted


def test_stock_split_identity_ratio_is_no_op() -> None:
    """ST6 — ratio 1 leaves qty and basis unchanged."""
    lot = _sample_lot()
    result = apply_stock_split(
        [lot],
        StockSplitAction(security_id="sec_aapl", ratio=Decimal("1")),
    )[0]
    assert result.quantity == lot.quantity
    assert result.cost_basis_per_share == lot.cost_basis_per_share


def test_stock_split_invalid_ratio_raises() -> None:
    """Errors bubble — zero/negative ratio is not silently ignored."""
    lot = _sample_lot()
    with pytest.raises(ValueError, match="split ratio must be positive"):
        apply_stock_split(
            [lot],
            StockSplitAction(security_id="sec_aapl", ratio=Decimal("0")),
        )
    with pytest.raises(ValueError, match="split ratio must be positive"):
        oracle_stock_split_basis(
            lot.quantity,
            lot.cost_basis_per_share,
            Decimal("-2"),
        )


def test_apply_stock_splits_sequence() -> None:
    """qa4 — chained splits compose with preserved total basis."""
    lot = _sample_lot()
    before_total = _total_basis(lot)
    actions = [
        StockSplitAction(security_id="sec_aapl", ratio=Decimal("2")),
        StockSplitAction(security_id="sec_aapl", ratio=Decimal("0.5")),
    ]
    result = apply_stock_splits([lot], actions)[0]
    assert result.quantity == lot.quantity
    assert result.cost_basis_per_share == lot.cost_basis_per_share
    assert _total_basis(result) == before_total


# --- property-based invariants (ST6) -----------------------------------------


_SPLIT_RATIO = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("100"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

_LOT_STRATEGY = st.builds(
    Lot,
    lot_id=st.uuids().map(lambda u: f"lot_{u.hex[:8]}"),
    account_id=st.sampled_from(("acct_a", "acct_b")),
    security_id=st.sampled_from(("sec_x", "sec_y")),
    quantity=st.decimals(
        min_value=Decimal("1"),
        max_value=Decimal("10000"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
    cost_basis_per_share=st.decimals(
        min_value=Decimal("0.01"),
        max_value=Decimal("10000"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
    acquisition_date=st.dates(
        min_value=date(2015, 1, 1),
        max_value=date(2025, 12, 31),
    ),
)


@given(lot=_LOT_STRATEGY, ratio=_SPLIT_RATIO)
def test_stock_split_preserves_total_basis_property(
    lot: Lot,
    ratio: Decimal,
) -> None:
    """qa4/ST6 — random lots: production output matches independent oracle."""
    action = StockSplitAction(security_id=lot.security_id, ratio=ratio)
    result = apply_stock_split([lot], action)[0]
    expected_qty, expected_cost = oracle_stock_split_basis(
        lot.quantity,
        lot.cost_basis_per_share,
        ratio,
    )
    assert result.quantity == expected_qty
    assert result.cost_basis_per_share == expected_cost
    assert result.quantity == lot.quantity * ratio
