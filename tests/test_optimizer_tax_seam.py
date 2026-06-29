"""po1-tax seam — TaxEstimator overlay (§14 Addendum C.4 falsifiers).

The seam is structurally live but numerically zero under ``ZeroTaxEstimator``:
the overlay is an identity (after-tax μ ≡ pre-tax μ), so w* is byte-identical
to the no-overlay path and honesty matrix #5 stays ``not_computed`` (not
faked). A non-zero stub proves the seam carries a drag without committing to
any tax magnitude — the Quantile/LLM estimators drop in behind it later.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from warehouse.data.ledger.views import LotPositionView
from warehouse.data.security_master import AssetClass as SecClass
from warehouse.decision.ips import AllocationTarget, InvestmentPolicyStatement
from warehouse.decision.ips.sleeves import IpsSleeve
from warehouse.decision.optimizer.models import RebalanceProposal
from warehouse.decision.optimizer.rebalance import run_mv_rebalance
from warehouse.decision.tax.estimator import TaxEstimator, ZeroTaxEstimator


def _lot(ticker: str, sec: SecClass, mv: Decimal) -> LotPositionView:
    return LotPositionView(
        lot_id=f"lot_{ticker}",
        account_id="acct_test",
        account_name="Test",
        security_id=ticker,
        ticker=ticker,
        security_name=ticker,
        security_asset_class=sec,
        liquidity_tier=1,
        quantity=Decimal("1"),
        cost_basis_per_share=mv,
        total_cost_basis=mv,
        market_price=mv,
        market_value=mv,
        unrealized_gain=Decimal("0"),
        acquisition_date=date(2019, 1, 1),
        is_restricted=False,
        wash_sale_substitute_group=None,
    )


def _ips() -> InvestmentPolicyStatement:
    return InvestmentPolicyStatement(
        ips_id="ips_test",
        household_id="hh_test",
        version=1,
        effective_date="2026-01-01",
        allocation_targets=[
            AllocationTarget(
                asset_class=ac,  # type: ignore[arg-type]
                min_weight=Decimal("0"),
                max_weight=Decimal("1"),
                target_weight=Decimal("0.5"),
            )
            for ac in ("equity", "fixed_income")
        ],
    )


def _positions() -> list[LotPositionView]:
    return [
        _lot("VTI", SecClass.EQUITY, Decimal("50")),
        _lot("BND", SecClass.FIXED_INCOME, Decimal("50")),
    ]


class _EquityDragEstimator:
    """Non-zero stub — taxes the equity sleeve's μ. Real numbers stay out."""

    is_zero = False

    def sleeve_mu_drag(
        self,
        universe: list[IpsSleeve],
        *,
        settings=None,  # type: ignore[no-untyped-def]
    ) -> dict[IpsSleeve, Decimal]:
        return {
            s: (Decimal("0.05") if s is IpsSleeve.EQUITY else Decimal("0"))
            for s in universe
        }


def test_zero_tax_estimator_is_noop() -> None:
    """ZeroTaxEstimator overlay is a strict no-op vs the default path."""
    positions = _positions()
    ips = _ips()
    default = run_mv_rebalance(positions, ips)
    explicit_zero = run_mv_rebalance(
        positions, ips, tax_estimator=ZeroTaxEstimator()
    )
    assert isinstance(explicit_zero, RebalanceProposal)
    assert explicit_zero.target_weights == default.target_weights
    assert explicit_zero.delta_w == default.delta_w
    assert explicit_zero.objective_value == default.objective_value
    assert explicit_zero.turnover_l1 == default.turnover_l1


def test_after_tax_mu_not_computed_under_zero() -> None:
    """Under the $0 seam μ stays the ex-ante class assumption."""
    proposal = run_mv_rebalance(
        _positions(), _ips(), tax_estimator=ZeroTaxEstimator()
    )
    # honesty #5 (after-tax μ) is not faked: the label is the ex-ante one.
    assert proposal.mu_source == "ex_ante_class_assumption"


def test_tax_estimator_drag_moves_w_star() -> None:
    """A non-zero stub moves w* — the seam transmits drag (no real numbers)."""
    positions = _positions()
    ips = _ips()
    base = run_mv_rebalance(positions, ips)
    tilted = run_mv_rebalance(
        positions, ips, tax_estimator=_EquityDragEstimator()
    )
    # Taxing equity μ lowers its after-tax appeal → less equity at w*.
    assert (
        tilted.target_weights[IpsSleeve.EQUITY]
        < base.target_weights[IpsSleeve.EQUITY]
    )


def test_zero_estimator_satisfies_protocol() -> None:
    """ZeroTaxEstimator is a structural TaxEstimator (runtime_checkable)."""
    assert isinstance(ZeroTaxEstimator(), TaxEstimator)
    assert ZeroTaxEstimator().is_zero is True
