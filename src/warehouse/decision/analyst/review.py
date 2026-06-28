"""Portfolio Analyst — 7-checkpoint diagnostic (pa0).

The analog of ``score_pm_axioms``: scores the ℍ_PortfolioAnalyst checkpoints
from the attribution snapshot, marking genuine gaps ``not_computed`` rather
than faking a pass (the analyst's own axiom 6 / Goodhart vigilance turned
inward). Checkpoint 2 is scorable on ``active_return`` (A.4); checkpoint 5 is a
weak partial (one causal hop, not beta-stripped); checkpoints 3/4/6 have no
engine and score ``not_computed``; checkpoint 7 is satisfied by construction;
checkpoint 1 is ``not_documented`` until the pa1 thesis store ships.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from warehouse.config import get_settings
from warehouse.decision.analyst.models import (
    ACTIVE_RETURN_LABEL,
    AnalystCheckpoint,
    AnalystCheckpointScore,
    AnalystReview,
    AttributionReport,
    PositionAttribution,
)

_S = AnalystCheckpointScore

_DETAILS: dict[str, str] = {
    "checkpoint_1": (
        "Thesis + kill criteria — no thesis store yet (pa1); "
        "not_documented, not a faked pass."
    ),
    "checkpoint_2": (
        f"Attribution reconciliation — scored on |{ACTIVE_RETURN_LABEL}| "
        "(annualized where the window clears the floor, cumulative "
        "otherwise). Beta-stripped idiosyncratic isolation is not_computed."
    ),
    "checkpoint_3": "Valuation scenario range — no valuation engine.",
    "checkpoint_4": "Out-of-sample validation — no signal/screen pipeline.",
    "checkpoint_5": (
        "Mechanism — the class assumption is one causal hop, but the gap is "
        "not beta-stripped; partial pass."
    ),
    "checkpoint_6": (
        "Goodhart audit — no fundamentals feed for reported-vs-economic "
        "divergence."
    ),
    "checkpoint_7": (
        "Composite decomposition — expected_cumulative + active_return are "
        "always present; satisfied by construction."
    ),
}


def position_active_score(
    pa: PositionAttribution, warn: Decimal, breach: Decimal
) -> AnalystCheckpointScore:
    """Holding-period-aware score for one lot (A.5).

    Uses the annualized active return where present (cross-position
    comparable), else the cumulative figure for short windows.
    """
    metric = pa.active_annualized if pa.active_annualized is not None else (
        pa.active_return
    )
    magnitude = abs(metric)
    if magnitude >= breach:
        return _S.BREACH
    if magnitude >= warn:
        return _S.WARN
    return _S.PASS


def score_analyst_checkpoints(
    report: AttributionReport, theses: Any | None = None
) -> AnalystReview:
    """Score the 7 ℍ_PortfolioAnalyst checkpoints from the report."""
    del theses  # pa1 thesis store flips checkpoint 1 — absent in pa0
    settings = get_settings()
    warn = Decimal(str(settings.analyst_residual_warn))
    breach = Decimal(str(settings.analyst_residual_breach))

    checkpoints: dict[str, AnalystCheckpointScore] = {
        "checkpoint_1": _S.NOT_DOCUMENTED,
        "checkpoint_2": _score_checkpoint_2(report, warn, breach),
        "checkpoint_3": _S.NOT_COMPUTED,
        "checkpoint_4": _S.NOT_COMPUTED,
        "checkpoint_5": (
            _S.PASS if report.positions else _S.NOT_COMPUTED
        ),
        "checkpoint_6": _S.NOT_COMPUTED,
        "checkpoint_7": _score_checkpoint_7(report),
    }
    return AnalystReview(
        config_version=report.config_version,
        checkpoints=checkpoints,
        details=dict(_DETAILS),
        headline=_build_headline(checkpoints),
    )


def analyst_checkpoint_rows(review: AnalystReview) -> list[AnalystCheckpoint]:
    """Flatten a review into ordered dashboard rows."""
    return [
        AnalystCheckpoint(
            checkpoint_id=cid,
            score=review.checkpoints[cid],
            detail=review.details.get(cid, ""),
        )
        for cid in sorted(review.checkpoints)
    ]


def _score_checkpoint_2(
    report: AttributionReport, warn: Decimal, breach: Decimal
) -> AnalystCheckpointScore:
    if not report.positions:
        return _S.NOT_COMPUTED
    worst = _S.PASS
    rank = {_S.PASS: 0, _S.WARN: 1, _S.BREACH: 2}
    for pa in report.positions:
        score = position_active_score(pa, warn, breach)
        if rank[score] > rank[worst]:
            worst = score
    return worst


def _score_checkpoint_7(report: AttributionReport) -> AnalystCheckpointScore:
    if not report.positions:
        return _S.NOT_COMPUTED
    # Invariant: both components present for every lot (¬M7). The fields are
    # non-optional Decimals, so construction already guarantees this; scoring
    # PASS makes the satisfied invariant visible in the diagnostic.
    return _S.PASS


def _build_headline(scores: dict[str, AnalystCheckpointScore]) -> str:
    breaches = sum(1 for s in scores.values() if s == _S.BREACH)
    warns = sum(1 for s in scores.values() if s == _S.WARN)
    if breaches:
        return (
            f"{breaches} checkpoint breach(es) — unexplained active return "
            "needs review"
        )
    if warns:
        return f"{warns} checkpoint warn(s) — monitor active return"
    return "attribution within tolerance; valuation/factor gaps not_computed"
