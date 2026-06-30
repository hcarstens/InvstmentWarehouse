"""PM workout (pmw) — drive ``pm.advise`` over synthetic cohorts, no DB.

The Portfolio Manager *workout* exercises the whole decision stack the way a
PM would in production: for each HNW cohort it generates a synthetic portfolio
+ IPS, packages them as a ``pm.advise`` process message, dispatches it through
the live messaging coordinator, and renders the returned ``AdviceBundle``
(report + recommendation) as a Markdown workout.

Pure + advisory — like ``pm.advise`` itself it mutates nothing and needs no
session (``DispatchContext(session=None)``; every leg is EVALUATE). A leg that
raises is **not** swallowed: ``dispatch_typed`` re-raises with the op /
correlation_id note attached (CLAUDE.md errors-bubble), so the run fails loud.

Message vocabulary exercised (see ``docs/messaging_protocol.md`` §5):
``pm.advise`` (EVALUATE composite) → ``risk.evaluate`` · ``policy.check`` ·
``optimizer.propose`` · ``attribution.evaluate`` · ``tax.scenario``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel

import warehouse.messaging.handlers  # noqa: F401 — populate REGISTRY
from warehouse.config import repo_root
from warehouse.decision.pm import build_working_set_from_bundle
from warehouse.messaging import (
    DispatchContext,
    Kind,
    Message,
    dispatch_typed,
)
from warehouse.messaging.payloads import AdviceBundle, PmAdvisePayload
from warehouse.research.synthetic.models import SyntheticHouseholdBundle
from warehouse.research.synthetic.pipeline import emit_synthetic_household

DEFAULT_SEED = 42

# The replicated workflow — one representative household per HNW cohort.
# concentrated_stress runs at rung 4 (the others at rung 3), matching the
# shared HNW fixture matrix (§9) and the e2e smoke combos.
DEFAULT_PMW_COMBOS: tuple[tuple[str, int], ...] = (
    ("general_hnw", 3),
    ("uhnw_inherited", 3),
    ("founder_executive", 3),
    ("concentrated_stress", 4),
)

# Default artifact path — generated, not committed (runs/ is gitignored).
DEFAULT_WORKOUT_NAME = "portfolio_manager_workout.md"


def default_workout_path() -> Path:
    return repo_root() / "runs" / "pm_workout" / DEFAULT_WORKOUT_NAME


class PmWorkoutCase(BaseModel):
    """One cohort run: the generated inputs + the PM advisory output.

    A transient driver container (not an audit snapshot) — the immutable
    records it *holds* via ``advice`` (``AdviceBundle``, ``PmNarrative``,
    ``RebalanceProposal``) are frozen + registered; this wrapper is not
    (mirrors the unfrozen ``WorkflowSmokeResult``).
    """

    cohort_id: str
    rung: int
    seed: int
    correlation_id: str
    bundle: SyntheticHouseholdBundle
    advice: AdviceBundle


def run_pm_workout_case(
    cohort_id: str,
    rung: int,
    *,
    seed: int = DEFAULT_SEED,
    as_of: date | None = None,
) -> PmWorkoutCase:
    """Generate (portfolio, IPS), dispatch ``pm.advise``, capture bundle."""
    bundle = emit_synthetic_household(
        cohort_id=cohort_id, seed=seed, rung=rung, validate=False
    )
    payload = build_working_set_from_bundle(bundle, as_of_date=as_of)
    correlation_id = f"pmw-{cohort_id}-s{seed}"
    msg = Message(
        op="pm.advise",
        kind=Kind.EVALUATE,
        payload=PmAdvisePayload.model_validate(payload.model_dump()),
        correlation_id=correlation_id,
        household_id=payload.household_id,
    )
    ctx = DispatchContext(session=None)  # type: ignore[arg-type] — pure leg
    advice = dispatch_typed(ctx, msg, AdviceBundle)
    return PmWorkoutCase(
        cohort_id=cohort_id,
        rung=rung,
        seed=seed,
        correlation_id=correlation_id,
        bundle=bundle,
        advice=advice,
    )


def run_pm_workout(
    combos: tuple[tuple[str, int], ...] | None = None,
    *,
    seed: int = DEFAULT_SEED,
    as_of: date | None = None,
) -> list[PmWorkoutCase]:
    """Run the workout over each (cohort, rung) — deterministic for a seed."""
    chosen = combos or DEFAULT_PMW_COMBOS
    return [
        run_pm_workout_case(cohort, rung, seed=seed, as_of=as_of)
        for cohort, rung in chosen
    ]


# --- rendering --------------------------------------------------------------


def _pct(x: object) -> str:
    return f"{float(x) * 100:.2f}%"  # type: ignore[arg-type]


def _usd(x: object) -> str:
    return f"${float(x):,.0f}"  # type: ignore[arg-type]


def _dec(x: object, n: int = 4) -> str:
    return f"{float(x):.{n}f}"  # type: ignore[arg-type]


def _fixture_alloc(bundle: SyntheticHouseholdBundle) -> dict[str, Decimal]:
    ap = bundle.fixture.asset_portfolio
    if ap is None:
        return {}
    return {s.asset_class.value: s.weight for s in ap.allocations}


_AXIOM_NAMES: dict[str, str] = {
    "axiom_1": "1 · Portfolio is the unit of account (risk measured)",
    "axiom_2": "2 · Diversification — effective bets",
    "axiom_3": "3 · Position sizing / concentration",
    "axiom_4": "4 · Survive to compound (stress tails)",
    "axiom_5": "5 · Margin of safety (deferred)",
    "axiom_6": "6 · Control exposure (binding constraints)",
    "axiom_7": "7 · Rebalance on calibrated evidence (drift)",
}


def render_pm_workout(
    cases: list[PmWorkoutCase],
    *,
    as_of: date,
    seed: int,
) -> str:
    """Render the workout cases as a single Markdown document."""
    out: list[str] = []
    w = out.append

    w("# Portfolio Manager Workout")
    w("")
    w(
        "End-to-end run of the Investment Warehouse decision stack, driven "
        "from the **Portfolio Manager** tier. For each synthetic household "
        "the harness generates a portfolio and an IPS, packages them as a "
        "`pm.advise` process message, and dispatches it through the live "
        "messaging coordinator. The PM fans the working set out to the "
        "specialist legs (risk → policy → optimizer → attribution → tax) and "
        "returns one immutable `AdviceBundle` — the report and the "
        "recommendation."
    )
    w("")
    w(f"- **As-of:** {as_of.isoformat()}")
    w(f"- **Seed:** {seed} (deterministic, replayable)")
    w("- **Dispatch:** `op=pm.advise` · `kind=EVALUATE` (pure, no mutation)")
    w(
        "- **Persona lens:** [Persona of The Portfolio Manager]"
        "(docs/heuristics/Persona%20of%20The%20Portfolio%20Manager.md) "
        "— the 7-axiom ℍ_Allocation diagnostic"
    )
    w(
        "- **Track:** `pm_workout` (pmw) — see "
        "[docs/pm_workout_implementation.md]"
        "(docs/pm_workout_implementation.md)"
    )
    w(f"- **Households run:** {len(cases)} (one per HNW cohort)")
    w("")

    _render_ledger(out, cases)
    for case in cases:
        _render_case(out, case)
    _render_footer(out)
    return "\n".join(out)


def _render_ledger(out: list[str], cases: list[PmWorkoutCase]) -> None:
    w = out.append
    w("## Run ledger")
    w("")
    w(
        "| Cohort | Household | NAV | Risk vol | Stress worst | "
        "TLH trades | Tax Δ | Drift alerts | Conc. alerts | PM headline |"
    )
    w("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for c in cases:
        o = c.advice
        rep = o.risk.report
        vol = rep.level_1_portfolio.annualized_volatility.value
        scen = rep.level_4_stress.scenarios
        worst = min((s.portfolio_return.value for s in scen), default=None)
        nar = o.narrative
        head = nar.headline if nar is not None else "—"
        w(
            f"| {c.cohort_id} | `{c.bundle.fixture.household_id}` | "
            f"{_usd(c.bundle.fixture.total_nav_usd)} | {_pct(vol)} | "
            f"{_pct(worst) if worst is not None else '—'} | "
            f"{len(o.proposal.trades)} | {_dec(o.tax.tax_delta, 2)} | "
            f"{len(o.drift.alerts)} | {len(o.drift.concentration_alerts)} | "
            f"{head} |"
        )
    w("")


def _render_case(out: list[str], case: PmWorkoutCase) -> None:
    w = out.append
    bundle = case.bundle
    o = case.advice
    fx = bundle.fixture
    ips = bundle.ips
    rep = o.risk.report

    w("---")
    w("")
    w(f"## {case.cohort_id} — `{fx.household_id}`")
    w("")
    w(
        f"NAV **{_usd(fx.total_nav_usd)}** · rung {case.rung} · "
        f"correlation_id `{case.correlation_id}` · "
        f"IPS `{ips.ips_id}` (v{ips.version}, eff. {ips.effective_date})"
    )
    w("")

    _render_policy_table(out, case)
    _render_risk(out, rep)
    _render_recommendation(out, o)
    _render_drift(out, o)
    _render_tax(out, o)
    _render_attribution(out, o)
    _render_narrative(out, o)


def _render_policy_table(out: list[str], case: PmWorkoutCase) -> None:
    w = out.append
    bundle = case.bundle
    o = case.advice
    ips = bundle.ips
    alloc = _fixture_alloc(bundle)
    targets = {t.asset_class.value: t for t in ips.allocation_targets}
    drift_rows = {row.asset_class: row for row in o.drift.rows}

    w("### 1 · Synthetic portfolio vs IPS policy")
    w("")
    w(
        "_Portfolio wt is the asset_portfolio manifest (incl. alternatives "
        "sub-ledger); the IPS drift column is computed on **lot positions "
        "only**, so alternatives held outside the lot ledger read as 0% and "
        "the lot denominator differs._"
    )
    w("")
    w("| Asset class | Portfolio wt | IPS target | Band | Lot drift |")
    w("| --- | --- | --- | --- | --- |")
    for c in sorted(set(alloc) | set(targets)):
        pw = alloc.get(c)
        t = targets.get(c)
        d = drift_rows.get(c)
        band = f"{_pct(t.min_weight)}–{_pct(t.max_weight)}" if t else "—"
        tgt = _pct(t.target_weight) if t else "—"
        drift = _pct(d.drift) if d else "—"
        w(
            f"| {c} | {_pct(pw) if pw is not None else '—'} | {tgt} | "
            f"{band} | {drift} |"
        )
    w("")

    extra: list[str] = []
    if ips.concentration_limit_pct is not None:
        extra.append(
            f"single-name concentration limit "
            f"**{_pct(ips.concentration_limit_pct)}**"
        )
    if ips.liquidity_tier_min_pct is not None:
        extra.append(
            f"min liquid (tier 1–2) **{_pct(ips.liquidity_tier_min_pct)}**"
        )
    if ips.turnover_budget_pct is not None:
        extra.append(f"turnover budget **{_pct(ips.turnover_budget_pct)}**")
    if ips.restricted_securities:
        names = ", ".join(f"`{s}`" for s in ips.restricted_securities)
        extra.append("restricted: " + names)
    if extra:
        w("IPS constraints: " + "; ".join(extra) + ".")
        w("")


def _render_risk(out: list[str], rep: object) -> None:
    w = out.append
    l1 = rep.level_1_portfolio  # type: ignore[attr-defined]
    w("### 2 · Risk report (whole-book)")
    w("")
    w(f"- Annualized volatility: **{_pct(l1.annualized_volatility.value)}**")
    w(f"- Expected return: **{_pct(l1.expected_return.value)}**")
    w(
        f"- Parametric VaR: {_pct(l1.parametric_var.value)} · "
        f"ES: {_pct(l1.parametric_es.value)}"
    )
    if l1.dollar_var is not None:
        line = f"- Dollar VaR: {_usd(l1.dollar_var.value)}"
        if l1.dollar_es is not None:
            line += f" · Dollar ES: {_usd(l1.dollar_es.value)}"
        w(line)
    w("")

    contribs = rep.level_2_contributions.by_class  # type: ignore[attr-defined]
    if contribs:
        shares = [float(c.pct_variance_contribution) for c in contribs]
        hhi = sum(s * s for s in shares)
        eff = (1.0 / hhi) if hhi > 0 else float("nan")
        w(f"Variance contribution by class (effective bets ≈ {eff:.2f}):")
        w("")
        w("| Class | Weight | Ann. vol | % variance | % ES |")
        w("| --- | --- | --- | --- | --- |")
        for c in sorted(
            contribs,
            key=lambda c: c.pct_variance_contribution,
            reverse=True,
        ):
            w(
                f"| {c.asset_class} | {_pct(c.weight)} | "
                f"{_pct(c.annual_volatility)} | "
                f"{_pct(c.pct_variance_contribution)} | "
                f"{_pct(c.pct_es_contribution)} |"
            )
        w("")

    scen = rep.level_4_stress.scenarios  # type: ignore[attr-defined]
    if scen:
        w("Stress replay (named scenarios):")
        w("")
        w("| Scenario | Portfolio return |")
        w("| --- | --- |")
        for s in sorted(scen, key=lambda s: s.portfolio_return.value):
            w(f"| {s.name} | {_pct(s.portfolio_return.value)} |")
        w("")


def _render_recommendation(out: list[str], o: AdviceBundle) -> None:
    w = out.append
    prop = o.proposal
    w("### 3 · Recommendation (optimizer)")
    w("")
    w(
        f"TLH / rebalance trades: **{len(prop.trades)}** · "
        f"estimated tax Δ: **{_dec(prop.estimated_tax_delta, 2)}** · "
        f"binding constraints: {len(prop.binding_constraints)}"
    )
    w("")
    if prop.trades:
        w("| Side | Qty | Security | Rationale |")
        w("| --- | --- | --- | --- |")
        for t in prop.trades[:25]:
            w(
                f"| {t.side} | {_dec(t.quantity, 2)} | `{t.security_id}` | "
                f"{t.rationale} |"
            )
        if len(prop.trades) > 25:
            w(f"| … | | | {len(prop.trades) - 25} more |")
        w("")
    else:
        w("_No tax-loss / rebalance trades proposed at this seed._")
        w("")
    if prop.binding_constraints:
        names = ", ".join(f"`{b}`" for b in prop.binding_constraints)
        w("Binding constraints: " + names)
        w("")

    rb = prop.rebalance
    if rb is not None:
        w(
            f"**MV rebalance (advisory w\\*)** — turnover L1 "
            f"{_dec(rb.turnover_l1)} · μ source `{rb.mu_source}` · "
            f"stress regime `{rb.stress_regime}` · regime gap "
            f"{_dec(rb.regime_gap_l1)}"
        )
        w("")
        w("| Sleeve | Target w\\* | Stress w\\* |")
        w("| --- | --- | --- |")
        st = rb.stress_target_weights or {}
        for sleeve, tw in sorted(
            rb.target_weights.items(), key=lambda kv: kv[1], reverse=True
        ):
            sname = getattr(sleeve, "value", str(sleeve))
            sw = st.get(sleeve)
            w(
                f"| {sname} | {_pct(tw)} | "
                f"{_pct(sw) if sw is not None else '—'} |"
            )
        w("")
        if rb.binding_bounds:
            names = ", ".join(f"`{b}`" for b in rb.binding_bounds)
            w("Binding IPS bounds on w\\*: " + names)
            w("")


def _render_drift(out: list[str], o: AdviceBundle) -> None:
    w = out.append
    w("### 4 · Policy monitoring (IPS drift)")
    w("")
    if o.drift.alerts:
        w("**Allocation-band alerts:**")
        for a in o.drift.alerts:
            w(f"- {a}")
        w("")
    if o.drift.concentration_alerts:
        w("**Concentration alerts:**")
        for a in o.drift.concentration_alerts:
            w(f"- {a}")
        w("")
    if not o.drift.alerts and not o.drift.concentration_alerts:
        w("_Within all IPS bands — no drift or concentration alerts._")
        w("")


def _render_tax(out: list[str], o: AdviceBundle) -> None:
    w = out.append
    w("### 5 · Tax overlay")
    w("")
    w(
        f"Scenario tax Δ: **{_dec(o.tax.tax_delta, 2)}** (NIIT/AMT overlay "
        "seam wired; estimate deferred — honesty axiom #5 stays "
        "`not_computed`)."
    )
    w("")


def _render_attribution(out: list[str], o: AdviceBundle) -> None:
    if o.attribution is None:
        return
    w = out.append
    attr = o.attribution
    w("### 6 · Attribution")
    w("")
    w(
        f"Per-position attribution: **{len(attr.positions)}** positions · "
        f"portfolio active return **{_pct(attr.portfolio_active_return)}** "
        f"(MV-weighted) · config `{attr.config_version}`."
    )
    if attr.limitations:
        w("")
        w("Limitations: " + "; ".join(attr.limitations))
    w("")


def _render_narrative(out: list[str], o: AdviceBundle) -> None:
    nar = o.narrative
    if nar is None:
        return
    w = out.append
    w("### 7 · Portfolio Manager diagnostic (ℍ_Allocation 7-axiom)")
    w("")
    w(f"**Headline:** {nar.headline}")
    w("")
    w("| Axiom | Score |")
    w("| --- | --- |")
    for k in sorted(nar.axioms_scored):
        sc = nar.axioms_scored[k]
        score = getattr(sc, "value", str(sc))
        w(f"| {_AXIOM_NAMES.get(k, k)} | `{score}` |")
    w("")
    legs = ", ".join(
        f"{k}=`{v}`" for k, v in sorted(nar.specialist_status.items())
    )
    w("Specialist legs: " + legs)
    w("")


def _render_footer(out: list[str]) -> None:
    w = out.append
    w("---")
    w("")
    w("## How the stack was driven")
    w("")
    w(
        "1. **Generate portfolio** — `emit_synthetic_household(cohort, seed, "
        "rung)` emits a Shape-B fixture (accounts, lots, alternatives, "
        "asset-class manifest) sized to the cohort sleeve ranges."
    )
    w(
        "2. **Generate IPS** — co-generated in the same call: allocation "
        "targets with min/max bands, concentration limit, restricted names, "
        "validated against the fixture."
    )
    w(
        "3. **Process message** — `build_working_set_from_bundle(...)` slices "
        "`{positions, ips, manifest, risk request}` into a `PmAdvisePayload`, "
        'wrapped in a `Message(op="pm.advise", kind=EVALUATE)`.'
    )
    w(
        "4. **Dispatch from the PM** — `dispatch_typed(ctx, msg, "
        "AdviceBundle)` routes through `warehouse.messaging.core`; the "
        "`pm.advise` coordinator nest-dispatches each specialist leg under "
        "the same `correlation_id`."
    )
    w(
        "5. **Result** — one frozen `AdviceBundle` carrying the risk report, "
        "the optimizer recommendation (TLH trades + MV rebalance), the tax "
        "scenario, the IPS drift report, attribution, and the PM narrative."
    )
    w("")
    w(
        "Re-run: `warehouse pm-workout` (in-process, no database, no "
        "external services)."
    )
    w("")


def write_pm_workout(
    *,
    combos: tuple[tuple[str, int], ...] | None = None,
    seed: int = DEFAULT_SEED,
    as_of: date | None = None,
    out_path: Path | None = None,
) -> tuple[Path, list[PmWorkoutCase]]:
    """Run the workout, write the Markdown artifact; return (path, cases)."""
    resolved_as_of = as_of or date.today()
    cases = run_pm_workout(combos, seed=seed, as_of=resolved_as_of)
    markdown = render_pm_workout(cases, as_of=resolved_as_of, seed=seed)
    path = out_path or default_workout_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return path, cases
