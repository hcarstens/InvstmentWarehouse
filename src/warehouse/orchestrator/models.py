"""Office Manager gate — external request/response models (ℍ_OM).

Thin boundary types only; routing lives in ``gate.py``.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from warehouse.messaging.payloads import AdviceBundle


class OrchestratorIntent(StrEnum):
    """Caller intent — routing is deterministic from this alone (OM2)."""

    REBALANCE_ADVISORY = "rebalance.advisory"


class OrchestratorRequest(BaseModel):
    """External request entering the single gate (OM1)."""

    intent: OrchestratorIntent
    household_id: str
    correlation_id: str | None = None
    actor_id: str = "system:orchestrator"
    cohort_id: str | None = None
    as_of_date: date | None = None


class OrchestratorError(BaseModel):
    """Caller-facing failure — no internal actor or stack detail (OM6)."""

    model_config = ConfigDict(frozen=True)

    correlation_id: str
    message: str


class OrchestratorResponse(BaseModel):
    """Unified gate response — one voice to callers (OM4, OM7)."""

    model_config = ConfigDict(frozen=True)

    correlation_id: str
    intent: OrchestratorIntent
    household_id: str
    status: str  # completed | failed
    assigned_actor: str | None = None
    result: AdviceBundle | None = None
    error: OrchestratorError | None = None
    elapsed_ms: int = Field(ge=0)


class InFlightStage(StrEnum):
    ROUTING = "routing"
    DISPATCHING = "dispatching"
    COMPLETED = "completed"
    FAILED = "failed"


class InFlightRecord(BaseModel):
    """Observable gate register entry (OM8)."""

    correlation_id: str
    intent: OrchestratorIntent
    household_id: str
    assigned_actor: str | None = None
    stage: InFlightStage
    started_at: str
    finished_at: str | None = None
    elapsed_ms: int | None = Field(default=None, ge=0)
