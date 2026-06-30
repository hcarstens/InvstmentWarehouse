"""Advisor approval gates — human sign-off before execution."""

from enum import StrEnum

from pydantic import BaseModel


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalSubject(StrEnum):
    """What an approval request signs off on (rw6 — generalized subject)."""

    OPTIMIZATION = "optimization"
    REPORT = "report"


class ApprovalRequest(BaseModel):
    request_id: str
    household_id: str
    subject_type: ApprovalSubject = ApprovalSubject.OPTIMIZATION
    subject_id: str | None = None
    # Optimization subjects keep this populated; report subjects leave it None.
    optimization_run_id: str | None = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    reviewer_id: str | None = None
