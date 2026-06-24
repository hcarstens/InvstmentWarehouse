"""Advisor approval gates — human sign-off before execution."""

from enum import StrEnum

from pydantic import BaseModel


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalRequest(BaseModel):
    request_id: str
    household_id: str
    optimization_run_id: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    reviewer_id: str | None = None
