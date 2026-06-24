"""Advisor approval workflow."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from warehouse.decision.approval import ApprovalStatus
from warehouse.execution.oms.service import stage_orders_from_approval
from warehouse.infra.audit.store import write_audit
from warehouse.infra.db.models import ApprovalRequestRow


class ApprovalRequestView(BaseModel):
    request_id: str
    optimization_run_id: str
    household_id: str
    status: str
    reviewer_id: str | None
    reviewed_at: datetime | None
    created_at: datetime


def create_approval_request(
    session: Session,
    optimization_run_id: str,
    household_id: str,
) -> ApprovalRequestView:
    request_id = f"appr_{uuid4().hex[:12]}"
    created = datetime.now(UTC)
    session.add(
        ApprovalRequestRow(
            request_id=request_id,
            optimization_run_id=optimization_run_id,
            household_id=household_id,
            status=ApprovalStatus.PENDING.value,
            created_at=created,
        )
    )
    write_audit(
        session,
        actor_id="system:approval",
        action="approval_requested",
        resource_type="approval_request",
        resource_id=request_id,
        household_id=household_id,
        details={"optimization_run_id": optimization_run_id},
    )
    return ApprovalRequestView(
        request_id=request_id,
        optimization_run_id=optimization_run_id,
        household_id=household_id,
        status=ApprovalStatus.PENDING.value,
        reviewer_id=None,
        reviewed_at=None,
        created_at=created,
    )


def list_approval_requests(
    session: Session,
    *,
    household_id: str | None = None,
    limit: int = 20,
) -> list[ApprovalRequestView]:
    stmt = select(ApprovalRequestRow).order_by(ApprovalRequestRow.created_at.desc()).limit(limit)
    if household_id:
        stmt = stmt.where(ApprovalRequestRow.household_id == household_id)
    rows = session.scalars(stmt).all()
    return [_row_to_view(r) for r in rows]


def update_approval_status(
    session: Session,
    request_id: str,
    *,
    status: ApprovalStatus,
    reviewer_id: str,
) -> ApprovalRequestView:
    row = session.get(ApprovalRequestRow, request_id)
    if row is None:
        raise ValueError(f"Approval request not found: {request_id}")
    if row.status != ApprovalStatus.PENDING.value:
        raise ValueError(f"Approval request {request_id} is already {row.status}")
    row.status = status.value
    row.reviewer_id = reviewer_id
    row.reviewed_at = datetime.now(UTC)
    write_audit(
        session,
        actor_id=reviewer_id,
        action=f"approval_{status.value}",
        resource_type="approval_request",
        resource_id=request_id,
        household_id=row.household_id,
        details={"optimization_run_id": row.optimization_run_id},
    )
    if status == ApprovalStatus.APPROVED:
        stage_orders_from_approval(session, request_id, actor_id=reviewer_id)
    return _row_to_view(row)


def _row_to_view(row: ApprovalRequestRow) -> ApprovalRequestView:
    return ApprovalRequestView(
        request_id=row.request_id,
        optimization_run_id=row.optimization_run_id,
        household_id=row.household_id,
        status=row.status,
        reviewer_id=row.reviewer_id,
        reviewed_at=row.reviewed_at,
        created_at=row.created_at,
    )
