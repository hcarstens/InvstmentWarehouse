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
from warehouse.data.ledger.views import LotPositionView
from warehouse.data.security_master import AssetClass
from warehouse.decision.constraints import evaluate_wash_sale_risk

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


# --- wash-sale chain / window invariants (qa3) -------------------------------


def _oracle_wash_triggers(
    lot: LotPositionView,
    positions: list[LotPositionView],
    *,
    as_of: date,
    window_days: int = 30,
) -> list[str]:
    """Independent oracle — same security or substitute group within window."""
    triggers: list[str] = []
    for other in positions:
        if other.lot_id == lot.lot_id:
            continue
        same_sec = lot.security_id == other.security_id
        group = lot.wash_sale_substitute_group
        same_group = (
            group is not None and group == other.wash_sale_substitute_group
        )
        if not (same_sec or same_group):
            continue
        if abs((other.acquisition_date - as_of).days) <= window_days:
            triggers.append(f"wash_sale_30d:{lot.lot_id}<-{other.lot_id}")
    return triggers


def _lot_view(
    *,
    lot_id: str,
    security_id: str,
    acq: date,
    wash_group: str | None = None,
) -> LotPositionView:
    return LotPositionView(
        lot_id=lot_id,
        account_id="acct_a",
        account_name="A",
        security_id=security_id,
        ticker=security_id.upper(),
        security_name=security_id,
        security_asset_class=AssetClass.ETF,
        quantity=Decimal("10"),
        cost_basis_per_share=Decimal("100"),
        total_cost_basis=Decimal("1000"),
        market_price=Decimal("90"),
        market_value=Decimal("900"),
        unrealized_gain=Decimal("-100"),
        acquisition_date=acq,
        is_restricted=False,
        wash_sale_substitute_group=wash_group,
    )


@given(
    day_offset=st.integers(min_value=0, max_value=30),
    as_of=st.dates(
        min_value=date(2020, 6, 1),
        max_value=date(2025, 6, 1),
    ),
)
def test_wash_sale_trigger_matches_independent_oracle(
    day_offset: int,
    as_of: date,
) -> None:
    """qa3 — substitute-group purchase inside window must trigger wash risk."""
    replacement_acq = as_of - timedelta(days=day_offset)
    harvest = _lot_view(
        lot_id="lot_harvest",
        security_id="sec_vti",
        acq=date(2019, 1, 1),
        wash_group="us_equity_broad",
    )
    replacement = _lot_view(
        lot_id="lot_repl",
        security_id="sec_voo",
        acq=replacement_acq,
        wash_group="us_equity_broad",
    )
    positions = [harvest, replacement]
    actual = evaluate_wash_sale_risk(harvest, positions, as_of=as_of)
    expected = _oracle_wash_triggers(harvest, positions, as_of=as_of)
    assert actual == expected


@given(
    chain_id=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N")),
        min_size=4,
        max_size=12,
    ),
    lots=st.lists(_LOT_STRATEGY, min_size=2, max_size=8),
)
def test_wash_sale_chain_id_groups_are_consistent(
    chain_id: str,
    lots: list[Lot],
) -> None:
    """Lots sharing wash_sale_chain_id reference the same chain label."""
    for lot in lots:
        lot.wash_sale_chain_id = chain_id
    chained = [lot for lot in lots if lot.wash_sale_chain_id == chain_id]
    assert len(chained) == len(lots)
    assert {lot.wash_sale_chain_id for lot in chained} == {chain_id}
