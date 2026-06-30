"""Advisor approval workflow."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from warehouse.decision.approval import ApprovalStatus, ApprovalSubject
from warehouse.infra.audit.store import write_audit
from warehouse.infra.db.models import ApprovalRequestRow


class ApprovalRequestView(BaseModel):
    request_id: str
    subject_type: str
    subject_id: str | None
    # Populated only for optimization subjects (OMS staging joins on it).
    optimization_run_id: str | None
    household_id: str
    status: str
    reviewer_id: str | None
    reviewed_at: datetime | None
    created_at: datetime


def _create_approval(
    session: Session,
    *,
    household_id: str,
    subject_type: ApprovalSubject,
    subject_id: str,
    optimization_run_id: str | None,
) -> ApprovalRequestView:
    request_id = f"appr_{uuid4().hex[:12]}"
    created = datetime.now(UTC)
    session.add(
        ApprovalRequestRow(
            request_id=request_id,
            subject_type=subject_type.value,
            subject_id=subject_id,
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
        details={
            "subject_type": subject_type.value,
            "subject_id": subject_id,
        },
    )
    # Flush so the request is queryable within the same transaction (a chained
    # caller may approval.decide it immediately) — matches stage_orders flush.
    session.flush()
    return ApprovalRequestView(
        request_id=request_id,
        subject_type=subject_type.value,
        subject_id=subject_id,
        optimization_run_id=optimization_run_id,
        household_id=household_id,
        status=ApprovalStatus.PENDING.value,
        reviewer_id=None,
        reviewed_at=None,
        created_at=created,
    )


def create_approval_request(
    session: Session,
    optimization_run_id: str,
    household_id: str,
) -> ApprovalRequestView:
    """Open an approval gate on an optimization run (OMS staging subject)."""
    return _create_approval(
        session,
        household_id=household_id,
        subject_type=ApprovalSubject.OPTIMIZATION,
        subject_id=optimization_run_id,
        optimization_run_id=optimization_run_id,
    )


def create_report_approval_request(
    session: Session,
    *,
    report_snapshot_id: str,
    household_id: str,
) -> ApprovalRequestView:
    """Open an advisor sign-off gate on a report snapshot (rw6).

    The client-of-record PDF is not rendered until this request is APPROVED —
    the costly-signal gate from the report-writer persona (T3).
    """
    return _create_approval(
        session,
        household_id=household_id,
        subject_type=ApprovalSubject.REPORT,
        subject_id=report_snapshot_id,
        optimization_run_id=None,
    )


def report_approval_status(
    session: Session,
    report_snapshot_id: str,
) -> str | None:
    """Latest status of the advisor gate for a report snapshot, or None.

    Returns the most recent request's status so a re-opened gate (rejected then
    re-requested) reflects the current decision.
    """
    row = session.scalars(
        select(ApprovalRequestRow)
        .where(
            ApprovalRequestRow.subject_type == ApprovalSubject.REPORT.value,
            ApprovalRequestRow.subject_id == report_snapshot_id,
        )
        .order_by(ApprovalRequestRow.created_at.desc())
        .limit(1)
    ).first()
    return row.status if row is not None else None


def list_approval_requests(
    session: Session,
    *,
    household_id: str | None = None,
    limit: int = 20,
) -> list[ApprovalRequestView]:
    stmt = (
        select(ApprovalRequestRow)
        .order_by(ApprovalRequestRow.created_at.desc())
        .limit(limit)
    )
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
        raise ValueError(
            f"Approval request {request_id} is already {row.status}"
        )
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
        details={
            "subject_type": row.subject_type,
            "subject_id": row.subject_id or "",
        },
    )
    # Decoupled (contract §5/§9.3): recording the decision does NOT stage
    # orders. The caller chains `orders.stage` after an APPROVED decision, by
    # correlation_id — staging venue/batching stays out of the approval gate.
    return _row_to_view(row)


def _row_to_view(row: ApprovalRequestRow) -> ApprovalRequestView:
    return ApprovalRequestView(
        request_id=row.request_id,
        subject_type=row.subject_type,
        subject_id=row.subject_id,
        optimization_run_id=row.optimization_run_id,
        household_id=row.household_id,
        status=row.status,
        reviewer_id=row.reviewer_id,
        reviewed_at=row.reviewed_at,
        created_at=row.created_at,
    )
