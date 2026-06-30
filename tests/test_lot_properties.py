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
from warehouse.data.ledger import (
    Lot,
    WashSaleSellEvent,
    assign_wash_sale_chain_ids,
)
from warehouse.data.ledger.views import LotPositionView
from warehouse.data.ledger.wash_chains import linked_lot_ids_for_sell
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


# --- wash-sale chain merge under random lot streams (qa3) --------------------


_SECURITY_GROUPS: dict[str, str | None] = {
    "sec_x": "grp_equity",
    "sec_y": "grp_bond",
    "sec_vti": "us_equity_broad",
    "sec_voo": "us_equity_broad",
}


def _oracle_chain_ids(
    lots: list[Lot],
    *,
    security_groups: dict[str, str | None],
    sells: list[WashSaleSellEvent],
    window_days: int = 30,
) -> dict[str, str | None]:
    """ST2 independent oracle — union-find on loss harvest adjacency."""
    if not lots:
        return {}
    parent = {lot.lot_id: lot.lot_id for lot in lots}
    lot_by_id = {lot.lot_id: lot for lot in lots}

    def find(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(left: str, right: str) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for sell in sells:
        if not sell.at_loss:
            continue
        sold = lot_by_id[sell.lot_id]
        linked = linked_lot_ids_for_sell(
            sold,
            lots,
            security_groups=security_groups,
            sell_date=sell.sell_date,
            window_days=window_days,
        )
        members = sorted(linked)
        for other in members[1:]:
            union(members[0], other)

    components: dict[str, list[str]] = {}
    for lot_id in lot_by_id:
        root = find(lot_id)
        components.setdefault(root, []).append(lot_id)

    chain_for_lot: dict[str, str | None] = {}
    for members in components.values():
        if len(members) < 2:
            for member in members:
                chain_for_lot[member] = None
        else:
            chain_id = min(members)
            for member in members:
                chain_for_lot[member] = chain_id
    return chain_for_lot


def _assert_chain_merge_invariants(
    lots: list[Lot],
    *,
    security_groups: dict[str, str | None],
    sells: list[WashSaleSellEvent],
) -> None:
    """qa3 invariants: merge matches oracle; chains are consistent."""
    merged = assign_wash_sale_chain_ids(
        lots,
        security_groups=security_groups,
        sells=sells,
    )
    expected = _oracle_chain_ids(
        lots,
        security_groups=security_groups,
        sells=sells,
    )
    for lot in merged:
        assert lot.wash_sale_chain_id == expected[lot.lot_id]

    # same chain_id iff same connected component
    by_chain: dict[str | None, list[str]] = {}
    for lot in merged:
        by_chain.setdefault(lot.wash_sale_chain_id, []).append(lot.lot_id)
    for chain_id, members in by_chain.items():
        if chain_id is None:
            for lot_id in members:
                assert expected[lot_id] is None
            continue
        roots = {expected[lot_id] for lot_id in members}
        assert roots == {chain_id}
        assert len(members) >= 2


def test_wash_chain_transitive_merge_abc() -> None:
    """qa3 — A sold → B replacement → B sold → C links all three."""
    lots = [
        Lot(
            lot_id="lot_a",
            account_id="acct_a",
            security_id="sec_vti",
            quantity=Decimal("10"),
            cost_basis_per_share=Decimal("100"),
            acquisition_date=date(2024, 1, 1),
        ),
        Lot(
            lot_id="lot_b",
            account_id="acct_a",
            security_id="sec_voo",
            quantity=Decimal("10"),
            cost_basis_per_share=Decimal("105"),
            acquisition_date=date(2024, 2, 1),
        ),
        Lot(
            lot_id="lot_c",
            account_id="acct_a",
            security_id="sec_vti",
            quantity=Decimal("10"),
            cost_basis_per_share=Decimal("110"),
            acquisition_date=date(2024, 3, 15),
        ),
    ]
    groups = {
        "sec_vti": "us_equity_broad",
        "sec_voo": "us_equity_broad",
    }
    sells = [
        WashSaleSellEvent(lot_id="lot_a", sell_date=date(2024, 2, 5)),
        WashSaleSellEvent(lot_id="lot_b", sell_date=date(2024, 3, 20)),
    ]
    _assert_chain_merge_invariants(lots, security_groups=groups, sells=sells)
    merged = assign_wash_sale_chain_ids(
        lots,
        security_groups=groups,
        sells=sells,
    )
    chain_ids = {lot.wash_sale_chain_id for lot in merged}
    assert chain_ids == {"lot_a"}


def test_wash_chain_day_31_no_merge() -> None:
    """ST6 — replacement acquired day 31 after sell stays unchained."""
    lots = [
        Lot(
            lot_id="lot_a",
            account_id="acct_a",
            security_id="sec_vti",
            quantity=Decimal("10"),
            cost_basis_per_share=Decimal("100"),
            acquisition_date=date(2024, 1, 1),
        ),
        Lot(
            lot_id="lot_b",
            account_id="acct_a",
            security_id="sec_voo",
            quantity=Decimal("10"),
            cost_basis_per_share=Decimal("105"),
            acquisition_date=date(2024, 3, 3),
        ),
    ]
    groups = {"sec_vti": "us_equity_broad", "sec_voo": "us_equity_broad"}
    sells = [WashSaleSellEvent(lot_id="lot_a", sell_date=date(2024, 2, 1))]
    merged = assign_wash_sale_chain_ids(
        lots,
        security_groups=groups,
        sells=sells,
    )
    assert all(lot.wash_sale_chain_id is None for lot in merged)


def test_wash_chain_gain_sell_does_not_link() -> None:
    """qa3 — harvest at gain (at_loss=False) must not open a chain."""
    lots = [
        Lot(
            lot_id="lot_a",
            account_id="acct_a",
            security_id="sec_vti",
            quantity=Decimal("10"),
            cost_basis_per_share=Decimal("100"),
            acquisition_date=date(2024, 1, 1),
        ),
        Lot(
            lot_id="lot_b",
            account_id="acct_a",
            security_id="sec_voo",
            quantity=Decimal("10"),
            cost_basis_per_share=Decimal("105"),
            acquisition_date=date(2024, 1, 15),
        ),
    ]
    groups = {"sec_vti": "us_equity_broad", "sec_voo": "us_equity_broad"}
    sells = [
        WashSaleSellEvent(
            lot_id="lot_a",
            sell_date=date(2024, 1, 10),
            at_loss=False,
        )
    ]
    merged = assign_wash_sale_chain_ids(
        lots,
        security_groups=groups,
        sells=sells,
    )
    assert all(lot.wash_sale_chain_id is None for lot in merged)


def test_wash_chain_unknown_sell_raises() -> None:
    """Errors bubble — unknown sell lot_id is not silently ignored."""
    lots = [
        Lot(
            lot_id="lot_a",
            account_id="acct_a",
            security_id="sec_vti",
            quantity=Decimal("1"),
            cost_basis_per_share=Decimal("1"),
            acquisition_date=date(2024, 1, 1),
        )
    ]
    with pytest.raises(ValueError, match="unknown sell lot_id"):
        assign_wash_sale_chain_ids(
            lots,
            security_groups={"sec_vti": "grp"},
            sells=[
                WashSaleSellEvent(
                    lot_id="missing",
                    sell_date=date(2024, 2, 1),
                )
            ],
        )


_UNIQUE_LOT_STRATEGY = st.builds(
    Lot,
    lot_id=st.uuids().map(lambda u: f"lot_{u.hex[:8]}"),
    account_id=st.sampled_from(("acct_a", "acct_b")),
    security_id=st.sampled_from(("sec_x", "sec_y")),
    quantity=st.decimals(
        min_value=Decimal("0.01"),
        max_value=Decimal("1000"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
    cost_basis_per_share=st.decimals(
        min_value=Decimal("0"),
        max_value=Decimal("1000"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
    acquisition_date=st.dates(
        min_value=date(2018, 1, 1),
        max_value=date(2025, 6, 1),
    ),
)


@given(
    lots=st.lists(
        _UNIQUE_LOT_STRATEGY,
        min_size=1,
        max_size=8,
        unique_by=lambda lot: lot.lot_id,
    ),
    sell_specs=st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=7),
            st.integers(min_value=0, max_value=45),
            st.booleans(),
        ),
        max_size=6,
    ),
)
def test_wash_chain_merge_random_lot_streams_match_oracle(
    lots: list[Lot],
    sell_specs: list[tuple[int, int, bool]],
) -> None:
    """qa3/ST6 — random lot streams: chain merge matches independent oracle."""
    sells: list[WashSaleSellEvent] = []
    for lot_index, day_offset, at_loss in sell_specs:
        lot = lots[lot_index % len(lots)]
        sell_date = lot.acquisition_date + timedelta(days=day_offset)
        sells.append(
            WashSaleSellEvent(
                lot_id=lot.lot_id,
                sell_date=sell_date,
                at_loss=at_loss,
            )
        )
    _assert_chain_merge_invariants(
        lots,
        security_groups=_SECURITY_GROUPS,
        sells=sells,
    )


# --- wash-sale chain / window invariants (qa3 triggers) --------------------


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
    account_id: str = "acct_a",
    quantity: Decimal = Decimal("10"),
    unrealized_gain: Decimal = Decimal("-100"),
) -> LotPositionView:
    cost_per = Decimal("100")
    total_cost = quantity * cost_per
    market_value = total_cost + unrealized_gain
    market_price = market_value / quantity if quantity > 0 else Decimal("0")
    return LotPositionView(
        lot_id=lot_id,
        account_id=account_id,
        account_name=account_id,
        security_id=security_id,
        ticker=security_id.upper(),
        security_name=security_id,
        security_asset_class=AssetClass.ETF,
        quantity=quantity,
        cost_basis_per_share=cost_per,
        total_cost_basis=total_cost,
        market_price=market_price,
        market_value=market_value,
        unrealized_gain=unrealized_gain,
        acquisition_date=acq,
        is_restricted=False,
        wash_sale_substitute_group=wash_group,
    )


def _oracle_wash_disallowed_loss(
    lot: LotPositionView,
    *,
    sell_qty: Decimal,
) -> Decimal:
    """ST2 oracle — pro-rated disallowed loss on partial harvest (H2).

    Invariant: when a loss lot is harvested and wash sale applies, the
    disallowed loss scales linearly with ``sell_qty / lot.quantity``.
    Trigger detection is quantity-invariant; only the disallowed amount
    scales with partial sells.
    """
    if lot.unrealized_gain is None or lot.unrealized_gain >= 0:
        return Decimal("0")
    if sell_qty <= 0 or lot.quantity <= 0:
        raise ValueError("sell_qty and lot.quantity must be positive")
    if sell_qty > lot.quantity:
        raise ValueError("sell_qty cannot exceed lot.quantity")
    return abs(lot.unrealized_gain) * (sell_qty / lot.quantity)


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
    """Assigned chain labels are uniform within a pre-linked component."""
    for lot in lots:
        lot.wash_sale_chain_id = chain_id
    chained = [lot for lot in lots if lot.wash_sale_chain_id == chain_id]
    assert len(chained) == len(lots)
    assert {lot.wash_sale_chain_id for lot in chained} == {chain_id}


# --- qa3 H2 + ST6 boundary falsifiers (extension; core qa3 unchanged) ------


@given(
    day_offset=st.integers(min_value=0, max_value=30),
    as_of=st.dates(
        min_value=date(2020, 6, 1),
        max_value=date(2025, 6, 1),
    ),
)
def test_wash_sale_same_security_oracle_matches_production(
    day_offset: int,
    as_of: date,
) -> None:
    """qa3/ST1 — same security replacement inside window triggers wash risk."""
    replacement_acq = as_of - timedelta(days=day_offset)
    harvest = _lot_view(
        lot_id="lot_harvest",
        security_id="sec_vti",
        acq=date(2019, 1, 1),
        wash_group=None,
    )
    replacement = _lot_view(
        lot_id="lot_repl",
        security_id="sec_vti",
        acq=replacement_acq,
        wash_group=None,
        account_id="acct_b",
    )
    positions = [harvest, replacement]
    actual = evaluate_wash_sale_risk(harvest, positions, as_of=as_of)
    expected = _oracle_wash_triggers(harvest, positions, as_of=as_of)
    assert actual == expected


def test_wash_sale_day_31_outside_window_no_trigger() -> None:
    """ST6 — day 31 is outside the inclusive 30-day wash window."""
    as_of = date(2025, 6, 30)
    harvest = _lot_view(
        lot_id="lot_harvest",
        security_id="sec_vti",
        acq=date(2019, 1, 1),
        wash_group="us_equity_broad",
    )
    replacement = _lot_view(
        lot_id="lot_repl",
        security_id="sec_voo",
        acq=as_of - timedelta(days=31),
        wash_group="us_equity_broad",
    )
    positions = [harvest, replacement]
    assert evaluate_wash_sale_risk(harvest, positions, as_of=as_of) == []
    assert _oracle_wash_triggers(harvest, positions, as_of=as_of) == []


def test_wash_sale_different_substitute_group_no_trigger() -> None:
    """ST1 — different wash-sale groups must not cross-trigger."""
    as_of = date(2025, 6, 30)
    harvest = _lot_view(
        lot_id="lot_harvest",
        security_id="sec_vti",
        acq=date(2019, 1, 1),
        wash_group="us_equity_broad",
    )
    replacement = _lot_view(
        lot_id="lot_repl",
        security_id="sec_bnd",
        acq=as_of - timedelta(days=5),
        wash_group="us_bond_broad",
    )
    positions = [harvest, replacement]
    assert evaluate_wash_sale_risk(harvest, positions, as_of=as_of) == []


def test_wash_sale_null_substitute_group_no_cross_security_match() -> None:
    """ST6 — None substitute group blocks cross-security wash identity."""
    as_of = date(2025, 6, 30)
    harvest = _lot_view(
        lot_id="lot_harvest",
        security_id="sec_a",
        acq=date(2019, 1, 1),
        wash_group=None,
    )
    replacement = _lot_view(
        lot_id="lot_repl",
        security_id="sec_b",
        acq=as_of - timedelta(days=10),
        wash_group=None,
    )
    positions = [harvest, replacement]
    assert evaluate_wash_sale_risk(harvest, positions, as_of=as_of) == []


def test_wash_sale_empty_positions_no_trigger() -> None:
    """ST6 — empty book must not raise; returns no triggers."""
    as_of = date(2025, 6, 30)
    harvest = _lot_view(
        lot_id="lot_only",
        security_id="sec_vti",
        acq=date(2019, 1, 1),
        wash_group="us_equity_broad",
    )
    assert evaluate_wash_sale_risk(harvest, [], as_of=as_of) == []


def test_wash_sale_single_lot_book_no_trigger() -> None:
    """ST6 — lone harvest lot with no replacements is clear."""
    as_of = date(2025, 6, 30)
    harvest = _lot_view(
        lot_id="lot_only",
        security_id="sec_vti",
        acq=date(2019, 1, 1),
        wash_group="us_equity_broad",
    )
    assert evaluate_wash_sale_risk(harvest, [harvest], as_of=as_of) == []


def test_wash_sale_multiple_replacements_all_triggered() -> None:
    """ST1 — each offending replacement yields its own trigger tag."""
    as_of = date(2025, 6, 30)
    harvest = _lot_view(
        lot_id="lot_harvest",
        security_id="sec_vti",
        acq=date(2019, 1, 1),
        wash_group="us_equity_broad",
    )
    repl_a = _lot_view(
        lot_id="lot_repl_a",
        security_id="sec_voo",
        acq=as_of - timedelta(days=3),
        wash_group="us_equity_broad",
    )
    repl_b = _lot_view(
        lot_id="lot_repl_b",
        security_id="sec_itot",
        acq=as_of - timedelta(days=20),
        wash_group="us_equity_broad",
    )
    positions = [harvest, repl_a, repl_b]
    actual = evaluate_wash_sale_risk(harvest, positions, as_of=as_of)
    expected = _oracle_wash_triggers(harvest, positions, as_of=as_of)
    assert actual == expected
    assert len(actual) == 2


def test_wash_sale_partial_qty_does_not_suppress_triggers_h2() -> None:
    """H2 — partial harvest qty must not suppress wash-sale triggers."""
    as_of = date(2025, 6, 30)
    replacement = _lot_view(
        lot_id="lot_repl",
        security_id="sec_voo",
        acq=as_of - timedelta(days=7),
        wash_group="us_equity_broad",
    )
    full = _lot_view(
        lot_id="lot_full",
        security_id="sec_vti",
        acq=date(2019, 1, 1),
        wash_group="us_equity_broad",
        quantity=Decimal("100"),
        unrealized_gain=Decimal("-500"),
    )
    partial = _lot_view(
        lot_id="lot_partial",
        security_id="sec_vti",
        acq=date(2019, 1, 1),
        wash_group="us_equity_broad",
        quantity=Decimal("25"),
        unrealized_gain=Decimal("-125"),
    )
    for harvest in (full, partial):
        positions = [harvest, replacement]
        actual = evaluate_wash_sale_risk(harvest, positions, as_of=as_of)
        expected = _oracle_wash_triggers(harvest, positions, as_of=as_of)
        assert actual == expected
        assert len(actual) == 1


@given(
    sell_fraction=st.decimals(
        min_value=Decimal("0.01"),
        max_value=Decimal("1"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
)
def test_wash_disallowed_loss_scales_with_partial_qty_h2(
    sell_fraction: Decimal,
) -> None:
    """H2 — basis adjustment: disallowed loss is pro-rated by sell_qty."""
    lot_qty = Decimal("100")
    sell_qty = (lot_qty * sell_fraction).quantize(Decimal("0.01"))
    if sell_qty <= 0:
        return
    lot = _lot_view(
        lot_id="lot_harvest",
        security_id="sec_vti",
        acq=date(2019, 1, 1),
        wash_group="us_equity_broad",
        quantity=lot_qty,
        unrealized_gain=Decimal("-1000"),
    )
    disallowed = _oracle_wash_disallowed_loss(lot, sell_qty=sell_qty)
    expected = Decimal("1000") * (sell_qty / lot_qty)
    assert disallowed == expected
