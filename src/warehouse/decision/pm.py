"""Portfolio Manager — 7-axiom diagnostic over specialist legs.

Advisory only: coordinates via ``dispatch_message``; never mutates state.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from warehouse.config import Settings, get_settings
from warehouse.data.alternatives.service import list_alternative_holdings
from warehouse.data.ledger.views import LotPositionView, list_lot_positions
from warehouse.decision.ips.store import load_ips
from warehouse.messaging.payloads import (
    AdviceBundle,
    AxiomScore,
    PmAdvisePayload,
    PmNarrative,
)
from warehouse.research.risk.models import (
    RiskHorizon,
    RiskRequest,
    ScenarioSet,
)
from warehouse.research.risk.portfolio_builder import (
    build_portfolio_from_holdings,
)
from warehouse.research.synthetic.fixture_views import (
    lot_positions_from_fixture,
)
from warehouse.research.synthetic.models import SyntheticHouseholdBundle

AXIOM_IDS: tuple[str, ...] = tuple(f"axiom_{i}" for i in range(1, 8))

SPECIALIST_STATUS: dict[str, str] = {
    "risk": "live",
    "analyst": "live",
    "optimizer": "live",
    "tax": "stub",
}


def score_pm_axioms(
    bundle: AdviceBundle,
    payload: PmAdvisePayload,
    *,
    correlation_id: str,
) -> PmNarrative:
    """Score the 7-axiom ℍ_Allocation checklist from specialist leg outputs."""
    del payload  # reserved for cohort/as_of provenance in pm1+
    settings = get_settings()
    scores = {
        "axiom_1": _score_axiom_1(bundle),
        "axiom_2": _score_axiom_2(bundle, settings),
        "axiom_3": _score_axiom_3(bundle),
        "axiom_4": _score_axiom_4(bundle, settings),
        "axiom_5": AxiomScore.NOT_COMPUTED,
        "axiom_6": _score_axiom_6(bundle, settings),
        "axiom_7": _score_axiom_7(bundle, settings),
    }
    return PmNarrative(
        correlation_id=correlation_id,
        axioms_scored=scores,
        headline=_build_headline(scores),
        specialist_status=dict(SPECIALIST_STATUS),
    )


def _score_axiom_1(bundle: AdviceBundle) -> AxiomScore:
    report = bundle.risk.report
    if report.level_1_portfolio.annualized_volatility.value > 0:
        return AxiomScore.PASS
    return AxiomScore.NOT_COMPUTED


def _score_axiom_2(bundle: AdviceBundle, settings: Settings) -> AxiomScore:
    contribs = bundle.risk.report.level_2_contributions.by_class
    if not contribs:
        return AxiomScore.NOT_COMPUTED
    # pct_variance_contribution is a fraction in [0, 1] summing to 1.0
    # (covariance.py: mv / portfolio_variance), not a 0-100 percentage.
    shares = [float(c.pct_variance_contribution) for c in contribs]
    hhi = sum(s * s for s in shares)
    if hhi <= 0:
        return AxiomScore.NOT_COMPUTED
    effective_bets = 1.0 / hhi
    if effective_bets >= settings.pm_effective_bets_pass:
        return AxiomScore.PASS
    if effective_bets >= settings.pm_effective_bets_warn:
        return AxiomScore.WARN
    return AxiomScore.BREACH


def _score_axiom_3(bundle: AdviceBundle) -> AxiomScore:
    if bundle.drift.concentration_alerts:
        return AxiomScore.BREACH
    return AxiomScore.PASS


def _score_axiom_4(bundle: AdviceBundle, settings: Settings) -> AxiomScore:
    scenarios = bundle.risk.report.level_4_stress.scenarios
    if not scenarios:
        return AxiomScore.NOT_COMPUTED
    worst = min(s.portfolio_return.value for s in scenarios)
    if worst <= Decimal(str(settings.pm_stress_breach)):
        return AxiomScore.BREACH
    if worst <= Decimal(str(settings.pm_stress_warn)):
        return AxiomScore.WARN
    return AxiomScore.PASS


def _score_axiom_6(bundle: AdviceBundle, settings: Settings) -> AxiomScore:
    if len(bundle.proposal.binding_constraints) > (
        settings.pm_binding_constraint_warn
    ):
        return AxiomScore.WARN
    return AxiomScore.PASS


def _score_axiom_7(bundle: AdviceBundle, settings: Settings) -> AxiomScore:
    if bundle.drift.alerts:
        return AxiomScore.BREACH
    if not bundle.drift.rows:
        return AxiomScore.NOT_COMPUTED
    max_drift = max(abs(row.drift) for row in bundle.drift.rows)
    if max_drift > Decimal(str(settings.pm_drift_warn)):
        return AxiomScore.WARN
    return AxiomScore.PASS


def _build_headline(scores: dict[str, AxiomScore]) -> str:
    breaches = sum(1 for s in scores.values() if s == AxiomScore.BREACH)
    warns = sum(1 for s in scores.values() if s == AxiomScore.WARN)
    not_computed = sum(
        1 for s in scores.values() if s == AxiomScore.NOT_COMPUTED
    )
    if breaches:
        return f"{breaches} axiom breach(es) — whole-book review required"
    if warns:
        return f"{warns} axiom warn(s) — monitor limits and drift"
    if not_computed:
        return (
            "book within measured tolerance; margin-of-safety not yet scored"
        )
    return "whole-book diagnostic within tolerance"


def build_working_set(
    session: Session,
    household_id: str,
    *,
    positions: list[LotPositionView] | None = None,
    as_of_date: date | None = None,
) -> PmAdvisePayload:
    """Assemble the PM working set from ledger positions + IPS + manifest."""
    pos = (
        positions
        if positions is not None
        else list_lot_positions(session, household_id=household_id)
    )
    ips = load_ips(session, household_id)
    if ips is None:
        raise ValueError(f"No IPS found for household {household_id}")

    alts = list_alternative_holdings(session, household_id=household_id)
    manifest = build_portfolio_from_holdings(household_id, pos, alts)
    manifest = manifest.model_copy(update={"source": "ledger"})

    settings = get_settings()
    notional = sum(
        (p.market_value for p in pos if p.market_value is not None),
        Decimal("0"),
    )
    notional += sum((a.current_nav for a in alts), Decimal("0"))

    request = RiskRequest(
        horizon=RiskHorizon.parse(settings.risk_dashboard_horizon_years),
        notional_usd=notional if notional > 0 else None,
        run_scenarios=ScenarioSet.NONE,
    )
    return PmAdvisePayload(
        household_id=household_id,
        positions=pos,
        ips=ips,
        manifest=manifest,
        request=request,
        as_of_date=as_of_date,
    )


def build_working_set_from_bundle(
    bundle: SyntheticHouseholdBundle,
    *,
    as_of_date: date | None = None,
) -> PmAdvisePayload:
    """In-process HNW path — reuses ``lot_positions_from_fixture`` (no DB)."""
    fixture = bundle.fixture
    restricted = frozenset(bundle.ips.restricted_securities)
    positions = lot_positions_from_fixture(
        fixture, restricted_tickers=restricted
    )
    manifest = fixture.asset_portfolio
    if manifest is None:
        raise ValueError(
            f"fixture {fixture.household_id} missing asset_portfolio"
        )

    settings = get_settings()
    request = RiskRequest(
        horizon=RiskHorizon.parse(settings.risk_dashboard_horizon_years),
        notional_usd=fixture.total_nav_usd,
        run_scenarios=ScenarioSet.NONE,
    )
    prov = fixture.provenance
    return PmAdvisePayload(
        household_id=fixture.household_id,
        positions=positions,
        ips=bundle.ips,
        manifest=manifest,
        request=request,
        cohort_id=prov.cohort_id,
        as_of_date=as_of_date,
    )
