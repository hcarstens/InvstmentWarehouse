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
    PositionAttribution,
)
from warehouse.decision.analyst.review import (
    analyst_checkpoint_rows,
    position_active_score,
    score_analyst_checkpoints,
)

__all__ = [
    "ACTIVE_RETURN_LABEL",
    "AnalystCheckpoint",
    "AnalystCheckpointScore",
    "AnalystReview",
    "AttributionError",
    "AttributionReport",
    "PositionAttribution",
    "analyst_checkpoint_rows",
    "evaluate_attribution",
    "position_active_score",
    "risk_class_for",
    "score_analyst_checkpoints",
]
