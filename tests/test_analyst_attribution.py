"""pa0 — attribution mechanics, ordering, honesty, walk-forward, purity.

Falsifiers named in portfolio_analyst_implementation.md §6 / Addendum A.6.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from decimal import Decimal

import pytest

import warehouse.messaging.handlers  # noqa: F401 — register catalog ops
from warehouse.data.ledger.views import LotPositionView
from warehouse.data.security_master import AssetClass as SecClass
from warehouse.decision.analyst import (
    ACTIVE_RETURN_LABEL,
    AttributionError,
    PositionAttribution,
    evaluate_attribution,
    risk_class_for,
)
from warehouse.decision.analyst import attribution as attribution_mod
from warehouse.messaging import (
    REGISTRY,
    DispatchContext,
    Kind,
    Message,
    dispatch_message,
    observability,
)
from warehouse.messaging.payloads import AttributionEvaluatePayload
from warehouse.research.risk.scenarios import assumptions_for

AS_OF = date(2026, 6, 28)
CONFIG_VERSION = "2026.06"
MIN_HOLDING_YEARS = Decimal("0.5")
EXPECTED = assumptions_for("base").class_expected_return


@pytest.fixture(autouse=True)
def _restore_registry() -> Iterator[None]:
    snapshot = dict(REGISTRY)
    observability.clear()
    yield
    REGISTRY.clear()
    REGISTRY.update(snapshot)
    observability.clear()


def _lot(
    *,
    lot_id: str,
    asset_class: SecClass,
    acq: date,
    cost: Decimal,
    mv: Decimal,
    ticker: str = "TST",
) -> LotPositionView:
    return LotPositionView(
        lot_id=lot_id,
        account_id="acct",
        account_name="Account",
        security_id=f"sec_{lot_id}",
        ticker=ticker,
        security_name="Test Security",
        security_asset_class=asset_class,
        liquidity_tier=1,
        quantity=Decimal("1"),
        cost_basis_per_share=cost,
        total_cost_basis=cost,
        market_price=mv,
        market_value=mv,
        unrealized_gain=mv - cost,
        acquisition_date=acq,
        is_restricted=False,
        wash_sale_substitute_group=None,
    )


def _evaluate(positions: list[LotPositionView]):
    return evaluate_attribution(
        positions,
        EXPECTED,
        household_id="hh_test",
        as_of=AS_OF,
        config_version=CONFIG_VERSION,
        min_holding_years=MIN_HOLDING_YEARS,
    )


def test_residual_mechanics_decomposes_total_return() -> None:
    """total_return == expected_cumulative + active_return (no hidden term)."""
    lot = _lot(
        lot_id="eq1",
        asset_class=SecClass.EQUITY,
        acq=AS_OF - timedelta(days=730),
        cost=Decimal("100"),
        mv=Decimal("130"),
    )
    report = _evaluate([lot])
    pa = report.positions[0]
    assert pa.total_return == Decimal("0.300000")
    # Decomposition is exact to the rounding quantum (¬M7 / checkpoint 7).
    recombined = pa.expected_cumulative + pa.active_return
    assert abs(recombined - pa.total_return) <= Decimal("0.000001")


def test_zero_active_position_passes_checkpoint() -> None:
    """A lot returning ~the class assumption has near-zero active return."""
    cost = Decimal("100")
    lot = _lot(
        lot_id="eq_par",
        asset_class=SecClass.EQUITY,
        acq=AS_OF - timedelta(days=365),
        cost=cost,
        mv=cost * (Decimal("1") + EXPECTED[risk_class_for(SecClass.EQUITY)]),
    )
    report = _evaluate([lot])
    pa = report.positions[0]
    assert abs(pa.active_return) < Decimal("0.01")
    assert pa.active_annualized is not None
    assert abs(pa.active_annualized) < Decimal("0.01")


def test_report_orders_by_abs_active_return() -> None:
    near = _lot(
        lot_id="near",
        asset_class=SecClass.EQUITY,
        acq=AS_OF - timedelta(days=365),
        cost=Decimal("100"),
        mv=Decimal("107"),
    )
    divergent = _lot(
        lot_id="big",
        asset_class=SecClass.EQUITY,
        acq=AS_OF - timedelta(days=365 * 5),
        cost=Decimal("100"),
        mv=Decimal("500"),
    )
    report = _evaluate([near, divergent])
    assert [p.lot_id for p in report.positions] == ["big", "near"]
    assert abs(report.positions[0].active_return) >= abs(
        report.positions[1].active_return
    )


def test_components_present_for_every_position() -> None:
    lots = [
        _lot(
            lot_id="eq",
            asset_class=SecClass.EQUITY,
            acq=AS_OF - timedelta(days=400),
            cost=Decimal("100"),
            mv=Decimal("120"),
        ),
        _lot(
            lot_id="cash",
            asset_class=SecClass.CASH,
            acq=AS_OF - timedelta(days=400),
            cost=Decimal("100"),
            mv=Decimal("100"),
        ),
    ]
    report = _evaluate(lots)
    for pa in report.positions:
        assert isinstance(pa.expected_cumulative, Decimal)
        assert isinstance(pa.active_return, Decimal)


def test_portfolio_active_is_market_value_weighted() -> None:
    big = _lot(
        lot_id="big",
        asset_class=SecClass.EQUITY,
        acq=AS_OF - timedelta(days=400),
        cost=Decimal("1000"),
        mv=Decimal("1100"),
    )
    small = _lot(
        lot_id="small",
        asset_class=SecClass.EQUITY,
        acq=AS_OF - timedelta(days=400),
        cost=Decimal("10"),
        mv=Decimal("30"),
    )
    report = _evaluate([big, small])
    total_mv = big.market_value + small.market_value
    expected = sum(
        (p.market_value / total_mv) * p.active_return for p in report.positions
    )
    assert abs(report.portfolio_active_return - expected) <= Decimal(
        "0.000001"
    )


def test_attribution_walk_forward() -> None:
    """A lot acquired after as_of is a walk-forward violation — it raises."""
    future = _lot(
        lot_id="future",
        asset_class=SecClass.EQUITY,
        acq=AS_OF + timedelta(days=30),
        cost=Decimal("100"),
        mv=Decimal("110"),
    )
    with pytest.raises(AttributionError, match="walk-forward"):
        _evaluate([future])


def test_attribution_class_mapping_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unmapped class raises — never a silent zero-residual fallback (A.1)."""
    # Every security-master class is mapped in production (no raise normally).
    for member in SecClass:
        assert member in attribution_mod._SEC_TO_RISK
    monkeypatch.setattr(attribution_mod, "_SEC_TO_RISK", {})
    with pytest.raises(AttributionError, match="no risk-class mapping"):
        risk_class_for(SecClass.EQUITY)
    lot = _lot(
        lot_id="eq",
        asset_class=SecClass.EQUITY,
        acq=AS_OF - timedelta(days=400),
        cost=Decimal("100"),
        mv=Decimal("110"),
    )
    with pytest.raises(AttributionError):
        _evaluate([lot])


def test_attribution_short_holding_stable() -> None:
    """Two-week lot stays finite; active_annualized not_computed (A.2/A.5)."""
    lot = _lot(
        lot_id="fresh",
        asset_class=SecClass.EQUITY,
        acq=AS_OF - timedelta(days=14),
        cost=Decimal("100"),
        mv=Decimal("110"),
    )
    report = _evaluate([lot])
    pa = report.positions[0]
    assert pa.active_annualized is None
    assert pa.active_return.is_finite()
    # Near-zero expected over a 2-week window → active ≈ total return.
    assert abs(pa.active_return - pa.total_return) < Decimal("0.01")


def test_residual_not_named_alpha() -> None:
    """Active return is never labelled alpha/idiosyncratic/residual (A.3)."""
    banned = ("alpha", "idiosyncratic", "residual")
    label = ACTIVE_RETURN_LABEL.lower()
    assert all(term not in label for term in banned)
    for field in PositionAttribution.model_fields:
        assert all(term not in field.lower() for term in banned)


def test_attribution_evaluate_pure() -> None:
    """The leg never touches ctx.session — pure over its payload (§4.1)."""
    lot = _lot(
        lot_id="eq",
        asset_class=SecClass.EQUITY,
        acq=AS_OF - timedelta(days=400),
        cost=Decimal("100"),
        mv=Decimal("120"),
    )
    ctx = DispatchContext(session=None)  # type: ignore[arg-type]
    out = dispatch_message(
        ctx,
        Message(
            op="attribution.evaluate",
            kind=Kind.EVALUATE,
            payload=AttributionEvaluatePayload(
                household_id="hh_test", positions=[lot], as_of_date=AS_OF
            ),
            correlation_id="attr-pure",
            household_id="hh_test",
        ),
    )
    assert out.positions[0].lot_id == "eq"


def test_no_analyst_coordinator_op() -> None:
    """Exactly one new atomic analyst op; no coordinator (messaging S1)."""
    attribution_ops = {op for op in REGISTRY if op.startswith("attribution.")}
    assert attribution_ops == {"attribution.evaluate"}
    assert not any(op.startswith("analyst.") for op in REGISTRY)
    assert not any("coordinator" in op for op in REGISTRY)
