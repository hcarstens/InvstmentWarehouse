"""ST6 property-based invariants for lot ledger math (st5b).

Independent oracles (ST2): date arithmetic and Decimal sums — never copied
from production aggregation helpers under test.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from warehouse.data.ingest.schwab_csv import parse_custodian_csv
from warehouse.data.ledger import Lot

# --- independent oracles -----------------------------------------------------


def _position_qty(
    lots: list[Lot],
    *,
    account_id: str,
    security_id: str,
) -> Decimal:
    return sum(
        (
            lot.quantity
            for lot in lots
            if lot.account_id == account_id and lot.security_id == security_id
        ),
        Decimal("0"),
    )


def _holding_days(acquisition: date, as_of: date) -> int:
    return (as_of - acquisition).days


def _lot_total_basis(lot: Lot) -> Decimal:
    return lot.quantity * lot.cost_basis_per_share


_LOT_STRATEGY = st.builds(
    Lot,
    lot_id=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N")),
        min_size=3,
        max_size=12,
    ),
    account_id=st.sampled_from(("acct_a", "acct_b")),
    security_id=st.sampled_from(("sec_x", "sec_y")),
    quantity=st.decimals(
        min_value=Decimal("0.01"),
        max_value=Decimal("10000"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
    cost_basis_per_share=st.decimals(
        min_value=Decimal("0"),
        max_value=Decimal("10000"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
    acquisition_date=st.dates(
        min_value=date(2018, 1, 1),
        max_value=date(2025, 12, 31),
    ),
)


@given(lot=_LOT_STRATEGY)
def test_lot_basis_non_negative(lot: Lot) -> None:
    assert lot.cost_basis_per_share >= Decimal("0")
    assert _lot_total_basis(lot) >= Decimal("0")


@given(lots=st.lists(_LOT_STRATEGY, min_size=1, max_size=12))
def test_lot_quantities_sum_to_position_qty(lots: list[Lot]) -> None:
    keys = {(lot.account_id, lot.security_id) for lot in lots}
    for account_id, security_id in keys:
        expected = _position_qty(
            lots,
            account_id=account_id,
            security_id=security_id,
        )
        actual = sum(
            (
                lot.quantity
                for lot in lots
                if lot.account_id == account_id
                and lot.security_id == security_id
            ),
            Decimal("0"),
        )
        assert actual == expected


@given(
    acquisition=st.dates(
        min_value=date(2018, 1, 1),
        max_value=date(2024, 12, 31),
    ),
    day_steps=st.lists(
        st.integers(min_value=0, max_value=120),
        min_size=2,
        max_size=8,
    ),
)
def test_holding_period_monotonic_in_as_of(
    acquisition: date,
    day_steps: list[int],
) -> None:
    as_ofs: list[date] = []
    cursor = acquisition
    for step in day_steps:
        cursor = cursor + timedelta(days=step)
        as_ofs.append(cursor)
    periods = [_holding_days(acquisition, as_of) for as_of in as_ofs]
    assert periods == sorted(periods)


# --- ingest error propagation (§4.1 gaps) ----------------------------------


def test_parse_custodian_csv_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.csv"
    with pytest.raises(FileNotFoundError, match="not found"):
        parse_custodian_csv(missing)


def test_parse_custodian_csv_missing_columns(tmp_path: Path) -> None:
    path = tmp_path / "bad_columns.csv"
    path.write_text("account_id,ticker\nacct_a,VTI\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Missing columns"):
        parse_custodian_csv(path)


def test_parse_custodian_csv_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="Empty custodian file"):
        parse_custodian_csv(path)


def test_parse_custodian_csv_invalid_row_surfaces_line(tmp_path: Path) -> None:
    path = tmp_path / "bad_row.csv"
    path.write_text(
        "account_id,ticker,quantity,as_of_date\n"
        "acct_a,VTI,not-a-number,2026-06-24\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Invalid row 2"):
        parse_custodian_csv(path)


def test_parse_custodian_csv_no_rows(tmp_path: Path) -> None:
    path = tmp_path / "headers_only.csv"
    path.write_text(
        "account_id,ticker,quantity,as_of_date\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="No position rows"):
        parse_custodian_csv(path)
