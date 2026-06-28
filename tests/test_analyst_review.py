"""pa0 — 7-checkpoint scoring + not_computed/not_documented honesty (§7)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from warehouse.data.ledger.views import LotPositionView
from warehouse.data.security_master import AssetClass as SecClass
from warehouse.decision.analyst import (
    AnalystCheckpointScore,
    analyst_checkpoint_rows,
    evaluate_attribution,
    risk_class_for,
    score_analyst_checkpoints,
)
from warehouse.decision.analyst.models import AttributionReport
from warehouse.research.risk.scenarios import assumptions_for

AS_OF = date(2026, 6, 28)
EXPECTED = assumptions_for("base").class_expected_return
_S = AnalystCheckpointScore


def _lot(
    *,
    lot_id: str,
    asset_class: SecClass,
    acq: date,
    cost: Decimal,
    mv: Decimal,
) -> LotPositionView:
    return LotPositionView(
        lot_id=lot_id,
        account_id="acct",
        account_name="Account",
        security_id=f"sec_{lot_id}",
        ticker="TST",
        security_name="Test",
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


def _report(positions: list[LotPositionView]) -> AttributionReport:
    return evaluate_attribution(
        positions,
        EXPECTED,
        household_id="hh_test",
        as_of=AS_OF,
        config_version="2026.06",
        min_holding_years=Decimal("0.5"),
    )


def test_honest_gaps_are_not_computed() -> None:
    report = _report(
        [
            _lot(
                lot_id="eq",
                asset_class=SecClass.EQUITY,
                acq=AS_OF - timedelta(days=400),
                cost=Decimal("100"),
                mv=Decimal("107"),
            )
        ]
    )
    review = score_analyst_checkpoints(report)
    assert review.checkpoints["checkpoint_3"] == _S.NOT_COMPUTED
    assert review.checkpoints["checkpoint_4"] == _S.NOT_COMPUTED
    assert review.checkpoints["checkpoint_6"] == _S.NOT_COMPUTED


def test_checkpoint_1_not_documented_without_thesis() -> None:
    report = _report(
        [
            _lot(
                lot_id="eq",
                asset_class=SecClass.EQUITY,
                acq=AS_OF - timedelta(days=400),
                cost=Decimal("100"),
                mv=Decimal("107"),
            )
        ]
    )
    review = score_analyst_checkpoints(report, theses=None)
    assert review.checkpoints["checkpoint_1"] == _S.NOT_DOCUMENTED


def test_checkpoint_7_satisfied_when_positions_present() -> None:
    report = _report(
        [
            _lot(
                lot_id="eq",
                asset_class=SecClass.EQUITY,
                acq=AS_OF - timedelta(days=400),
                cost=Decimal("100"),
                mv=Decimal("120"),
            )
        ]
    )
    review = score_analyst_checkpoints(report)
    assert review.checkpoints["checkpoint_7"] == _S.PASS
    assert review.checkpoints["checkpoint_5"] == _S.PASS


def test_checkpoint_2_passes_on_zero_active() -> None:
    cost = Decimal("100")
    eq = EXPECTED[risk_class_for(SecClass.EQUITY)]
    report = _report(
        [
            _lot(
                lot_id="par",
                asset_class=SecClass.EQUITY,
                acq=AS_OF - timedelta(days=365),
                cost=cost,
                mv=cost * (Decimal("1") + eq),
            )
        ]
    )
    review = score_analyst_checkpoints(report)
    assert review.checkpoints["checkpoint_2"] == _S.PASS


def test_checkpoint_2_breaches_on_large_divergence() -> None:
    report = _report(
        [
            _lot(
                lot_id="big",
                asset_class=SecClass.EQUITY,
                acq=AS_OF - timedelta(days=365 * 5),
                cost=Decimal("100"),
                mv=Decimal("500"),
            )
        ]
    )
    review = score_analyst_checkpoints(report)
    assert review.checkpoints["checkpoint_2"] == _S.BREACH


def test_empty_report_checkpoint_2_not_computed() -> None:
    report = _report([])
    review = score_analyst_checkpoints(report)
    assert review.checkpoints["checkpoint_2"] == _S.NOT_COMPUTED
    assert review.checkpoints["checkpoint_7"] == _S.NOT_COMPUTED


def test_checkpoint_rows_cover_all_seven() -> None:
    report = _report([])
    review = score_analyst_checkpoints(report)
    rows = analyst_checkpoint_rows(review)
    assert len(rows) == 7
    assert {r.checkpoint_id for r in rows} == {
        f"checkpoint_{i}" for i in range(1, 8)
    }
