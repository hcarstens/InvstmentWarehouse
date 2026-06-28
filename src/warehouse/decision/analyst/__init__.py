"""Portfolio Analyst — position-level research & attribution (decision plane).

Advisory and pure: never mutates, never trades. pa0 ships attribution +
residual decomposition; pa1 adds thesis/kill-criteria; pa2 adds NPA flags.
"""

from __future__ import annotations

from warehouse.decision.analyst.attribution import (
    AttributionError,
    evaluate_attribution,
    risk_class_for,
)
from warehouse.decision.analyst.models import (
    ACTIVE_RETURN_LABEL,
    AnalystCheckpoint,
    AnalystCheckpointScore,
    AnalystReview,
    AttributionReport,
    KillBreach,
    KillCriteria,
    KillCriterion,
    PositionAttribution,
    PositionThesis,
)
from warehouse.decision.analyst.review import (
    analyst_checkpoint_rows,
    position_active_score,
    score_analyst_checkpoints,
)
from warehouse.decision.analyst.thesis import (
    ThesisError,
    ThesisStore,
    breaches_for_attribution,
    evaluate_kill_criteria,
    instrument_key,
)

__all__ = [
    "ACTIVE_RETURN_LABEL",
    "AnalystCheckpoint",
    "AnalystCheckpointScore",
    "AnalystReview",
    "AttributionError",
    "AttributionReport",
    "KillBreach",
    "KillCriteria",
    "KillCriterion",
    "PositionAttribution",
    "PositionThesis",
    "ThesisError",
    "ThesisStore",
    "analyst_checkpoint_rows",
    "breaches_for_attribution",
    "evaluate_attribution",
    "evaluate_kill_criteria",
    "instrument_key",
    "position_active_score",
    "risk_class_for",
    "score_analyst_checkpoints",
]
