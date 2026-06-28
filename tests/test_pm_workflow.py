"""pm1 — rebalance advisory workflow + HNW rung-3 smoke."""

from collections.abc import Iterator

import pytest

import warehouse.messaging.handlers  # noqa: F401 — register catalog ops
from warehouse.decision.pm import build_working_set_from_bundle
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.bootstrap import bootstrap_database
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID
from warehouse.messaging import (
    REGISTRY,
    DispatchContext,
    Kind,
    Message,
    dispatch_message,
    observability,
)
from warehouse.messaging.payloads import (
    AdviceBundle,
    PmAdvisePayload,
    PolicyCheckPayload,
)
from warehouse.research.synthetic import emit_synthetic_household
from warehouse.workflows.rebalance_advisory import run_rebalance_advisory

DEMO = DEMO_HOUSEHOLD_ID


@pytest.fixture
def seeded() -> Iterator[None]:
    bootstrap_database(seed=True)
    yield


@pytest.fixture(autouse=True)
def _restore_registry() -> Iterator[None]:
    snapshot = dict(REGISTRY)
    observability.clear()
    yield
    REGISTRY.clear()
    REGISTRY.update(snapshot)
    observability.clear()


def test_rebalance_advisory_correlation(seeded: None) -> None:
    with session_scope() as session:
        bundle = run_rebalance_advisory(
            session, DEMO, correlation_id="rebalance-adv-1"
        )
    assert bundle.narrative is not None
    assert bundle.narrative.correlation_id == "rebalance-adv-1"
    assert bundle.drift.household_id == DEMO


def test_pm_workflow_hnw_rung3() -> None:
    bundle = emit_synthetic_household(cohort_id="general_hnw", seed=42, rung=3)
    payload = build_working_set_from_bundle(bundle)
    ctx = DispatchContext(session=None)  # type: ignore[arg-type]
    out = dispatch_message(
        ctx,
        Message(
            op="pm.advise",
            kind=Kind.EVALUATE,
            payload=PmAdvisePayload.model_validate(payload.model_dump()),
            correlation_id="hnw-rung3",
            household_id=payload.household_id,
        ),
    )
    assert isinstance(out, AdviceBundle)
    assert out.narrative is not None
    assert out.risk.report is not None
    # pm1 acceptance: whole-book HNW path surfaces concentration in drift.
    assert out.drift.concentration_alerts


def test_policy_check_concentration_live() -> None:
    """Analyst leg is live: drift + concentration on a real HNW book."""
    bundle = emit_synthetic_household(cohort_id="general_hnw", seed=42, rung=3)
    payload = build_working_set_from_bundle(bundle)
    ctx = DispatchContext(session=None)  # type: ignore[arg-type]
    report = dispatch_message(
        ctx,
        Message(
            op="policy.check",
            kind=Kind.EVALUATE,
            payload=PolicyCheckPayload(
                household_id=payload.household_id,
                positions=payload.positions,
                ips=payload.ips,
            ),
            correlation_id="policy-concentration",
            household_id=payload.household_id,
        ),
    )
    assert report.concentration_alerts


def test_pm_no_new_ops() -> None:
    """PM reaches specialists only via the shipped catalog."""
    from warehouse.messaging import REGISTRY as catalog

    pm_ops = {op for op in catalog if op.startswith("pm.")}
    assert pm_ops == {"pm.advise"}


def test_pm_bundle_carries_attribution() -> None:
    """pa0: PM nest-dispatches the attribution leg as a 5th specialist."""
    bundle = emit_synthetic_household(cohort_id="general_hnw", seed=42, rung=3)
    payload = build_working_set_from_bundle(bundle)
    ctx = DispatchContext(session=None)  # type: ignore[arg-type]
    out = dispatch_message(
        ctx,
        Message(
            op="pm.advise",
            kind=Kind.EVALUATE,
            payload=PmAdvisePayload.model_validate(payload.model_dump()),
            correlation_id="hnw-attribution",
            household_id=payload.household_id,
        ),
    )
    assert isinstance(out, AdviceBundle)
    assert out.attribution is not None
    assert out.attribution.positions
    # Components present for every lot (¬M7 / checkpoint 7).
    for pa in out.attribution.positions:
        assert pa.expected_cumulative is not None
        assert pa.active_return is not None


def test_pm_attribution_correlation() -> None:
    """correlation_id threads PM → the nested attribution leg (§4.1)."""
    bundle = emit_synthetic_household(cohort_id="general_hnw", seed=42, rung=3)
    payload = build_working_set_from_bundle(bundle)

    captured: dict[str, str] = {}
    payload_type, handler, kind = REGISTRY["attribution.evaluate"]

    def _spy(ctx: DispatchContext, p: object) -> object:
        captured["cid"] = ctx.correlation_id
        return handler(ctx, p)

    REGISTRY["attribution.evaluate"] = (payload_type, _spy, kind)
    ctx = DispatchContext(session=None)  # type: ignore[arg-type]
    out = dispatch_message(
        ctx,
        Message(
            op="pm.advise",
            kind=Kind.EVALUATE,
            payload=PmAdvisePayload.model_validate(payload.model_dump()),
            correlation_id="pm-attr-cid",
            household_id=payload.household_id,
        ),
    )
    assert out.narrative is not None
    assert out.narrative.correlation_id == "pm-attr-cid"
    assert captured["cid"] == "pm-attr-cid"
