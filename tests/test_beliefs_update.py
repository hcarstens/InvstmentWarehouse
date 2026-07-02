"""Belief engine wiring (pv1) — prior assembly, QP feed, journal, op surface.

Falsifiers: prior labelled ``class_assumption`` (not equilibrium), zero-view
w* == po0 baseline w* (byte-identical), a positive view raises the sleeve's w*
on a loose-bound book, journal fields + view-source labelling, the
``beliefs.update`` op is pure and is the only new op, and τ/config are pinned.
"""

from __future__ import annotations

from decimal import Decimal

import warehouse.messaging.handlers  # noqa: F401 — register ops
from warehouse.config import get_settings
from warehouse.decision.beliefs import (
    View,
    ViewSource,
    rebalance_on_posterior,
    update_beliefs,
)
from warehouse.decision.ips import AllocationTarget
from warehouse.decision.ips.sleeves import IpsSleeve
from warehouse.decision.optimizer.rebalance import run_mv_rebalance
from warehouse.decision.pm import build_working_set_from_bundle
from warehouse.messaging import (
    REGISTRY,
    DispatchContext,
    Kind,
    Message,
    dispatch_message,
)
from warehouse.messaging.payloads import BeliefsUpdatePayload
from warehouse.research.synthetic import emit_synthetic_household


def _book(as_of=None):  # type: ignore[no-untyped-def]
    bundle = emit_synthetic_household(cohort_id="general_hnw", seed=42, rung=3)
    return build_working_set_from_bundle(bundle, as_of_date=as_of)


def _loosen_ips(book):  # type: ignore[no-untyped-def]
    """Widen every sleeve box to [0, 1] so no bound pins the QP corner."""
    loose = [
        AllocationTarget(
            asset_class=t.asset_class,
            min_weight=Decimal("0"),
            max_weight=Decimal("1"),
            target_weight=t.target_weight,
        )
        for t in book.ips.allocation_targets
    ]
    ips = book.ips.model_copy(update={"allocation_targets": loose})
    return book.model_copy(update={"ips": ips})


def test_prior_labelled_class_assumption_not_equilibrium() -> None:
    book = _book()
    belief = update_beliefs(book, ())
    assert belief.prior.prior_source == "class_assumption"
    assert belief.prior.assumptions_version  # pinned to the risk model version
    assert belief.posterior.method == "black_litterman"


def test_zero_view_w_star_equals_po0_baseline() -> None:
    book = _book()
    belief = update_beliefs(book, ())
    # Zero-view posterior == prior byte-identical.
    assert belief.posterior.mu == belief.prior.mu
    baseline = run_mv_rebalance(book.positions, book.ips, compute_stress=False)
    posterior_rebal = rebalance_on_posterior(
        book, belief.posterior, compute_stress=False
    )
    # No view → no move: w* byte-identical to the po0 baseline.
    assert posterior_rebal.target_weights == baseline.target_weights


def test_positive_view_raises_sleeve_weight_on_loose_bounds() -> None:
    book = _loosen_ips(_book())
    view = View(
        sleeve=IpsSleeve.EQUITY,
        expected_excess=Decimal("0.06"),
        confidence=Decimal("0.8"),
        source=ViewSource.MANUAL,
        rationale="strong equity tilt",
    )
    belief = update_beliefs(book, (view,))
    baseline = run_mv_rebalance(book.positions, book.ips, compute_stress=False)
    posterior_rebal = rebalance_on_posterior(
        book, belief.posterior, compute_stress=False
    )
    # Posterior μ up on equity → equity w* up (box caps still bind at 1).
    assert (
        belief.posterior.mu[IpsSleeve.EQUITY]
        > (belief.prior.mu[IpsSleeve.EQUITY])
    )
    assert (
        posterior_rebal.target_weights[IpsSleeve.EQUITY]
        > (baseline.target_weights[IpsSleeve.EQUITY])
    )


def test_journal_fields_and_view_source_labelled() -> None:
    book = _book()
    view = View(
        sleeve=IpsSleeve.EQUITY,
        expected_excess=Decimal("0.02"),
        confidence=Decimal("0.5"),
        source=ViewSource.MANUAL,
        rationale="demo",
    )
    belief = update_beliefs(book, (view,), correlation_id="trace-9")
    assert belief.correlation_id == "trace-9"
    assert isinstance(belief.views, tuple)
    assert belief.views[0].source == ViewSource.MANUAL
    assert belief.views[0].source.value == "manual"
    assert belief.views[0].calibration == "not_computed"
    # Calibration stays not_computed until a scored history exists (F8).
    assert belief.calibration == "not_computed"


def test_belief_config_pinned() -> None:
    book = _book()
    settings = get_settings()
    belief = update_beliefs(book, ())
    assert belief.belief_config_version == settings.belief_config_version
    assert belief.posterior.tau == Decimal(str(settings.black_litterman_tau))


class _Poison:
    def __getattribute__(self, name: str) -> object:
        raise AssertionError(f"beliefs.update touched session.{name}")


def test_beliefs_update_pure_via_dispatch() -> None:
    book = _book()
    view = View(
        sleeve=IpsSleeve.EQUITY,
        expected_excess=Decimal("0.02"),
        confidence=Decimal("0.5"),
        source=ViewSource.MANUAL,
        rationale="demo",
    )
    ctx = DispatchContext(session=_Poison())  # type: ignore[arg-type]
    out = dispatch_message(
        ctx,
        Message(
            op="beliefs.update",
            kind=Kind.EVALUATE,
            payload=BeliefsUpdatePayload(book=book, views=(view,)),
            correlation_id="trace-belief",
            household_id=book.household_id,
        ),
    )
    from warehouse.decision.beliefs import BeliefUpdate

    assert isinstance(out, BeliefUpdate)
    # The pure leg saw the inbound trace; nothing mutated (poisoned session).
    assert out.correlation_id == "trace-belief"


def test_beliefs_is_only_new_op() -> None:
    beliefs_ops = {op for op in REGISTRY if op.startswith("beliefs.")}
    assert beliefs_ops == {"beliefs.update"}
    # pm.* surface unchanged (no coordinator op added).
    pm_ops = {op for op in REGISTRY if op.startswith("pm.")}
    assert pm_ops == {"pm.advise"}
