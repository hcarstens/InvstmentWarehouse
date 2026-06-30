"""OMS — stage orders from approved optimizations, route execution state."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from warehouse.decision.approval import ApprovalStatus
from warehouse.execution.oms import OrderStatus
from warehouse.infra.audit.store import write_audit
from warehouse.infra.db.models import (
    ApprovalRequestRow,
    OptimizationTradeRow,
    StagedOrderRow,
)
from warehouse.messaging import DispatchContext, Kind, Message, emit_event
from warehouse.messaging.models import OrderFilled


class StagedOrderView(BaseModel):
    order_id: str
    approval_request_id: str
    optimization_run_id: str
    household_id: str
    lot_id: str | None
    security_id: str
    account_id: str
    side: str
    quantity: str
    status: str
    created_at: datetime
    updated_at: datetime


def stage_orders_from_approval(
    session: Session,
    approval_request_id: str,
    *,
    actor_id: str = "system:oms",
) -> list[StagedOrderView]:
    approval = session.get(ApprovalRequestRow, approval_request_id)
    if approval is None:
        raise ValueError(f"Approval request not found: {approval_request_id}")
    # Human approval gate — enforce at the OMS boundary, not just the caller.
    # No order reaches staging without an APPROVED sign-off
    # (CLAUDE.md: gates dominate).
    if approval.status != ApprovalStatus.APPROVED.value:
        raise ValueError(
            f"Cannot stage orders for {approval_request_id}: "
            f"approval status is '{approval.status}', "
            f"expected '{ApprovalStatus.APPROVED.value}'"
        )
    # rw6: approvals are now subject-typed. Only optimization subjects carry an
    # optimization_run_id and can stage orders; a report-document approval must
    # never reach the OMS boundary.
    run_id = approval.optimization_run_id
    if run_id is None:
        raise ValueError(
            f"Cannot stage orders for {approval_request_id}: approval subject "
            f"is '{approval.subject_type}', not an optimization run"
        )

    existing = session.scalar(
        select(StagedOrderRow.order_id)
        .where(StagedOrderRow.approval_request_id == approval_request_id)
        .limit(1)
    )
    if existing:
        return list_staged_orders(session, household_id=approval.household_id)

    trades = session.scalars(
        select(OptimizationTradeRow).where(
            OptimizationTradeRow.run_id == run_id
        )
    ).all()
    now = datetime.now(UTC)
    views: list[StagedOrderView] = []
    for trade in trades:
        order_id = f"ord_{uuid4().hex[:12]}"
        session.add(
            StagedOrderRow(
                order_id=order_id,
                approval_request_id=approval_request_id,
                optimization_run_id=run_id,
                household_id=approval.household_id,
                lot_id=trade.lot_id,
                security_id=trade.security_id,
                account_id=trade.account_id,
                side=trade.side,
                quantity=trade.quantity,
                status=OrderStatus.STAGED.value,
                created_at=now,
                updated_at=now,
            )
        )
        views.append(
            StagedOrderView(
                order_id=order_id,
                approval_request_id=approval_request_id,
                optimization_run_id=run_id,
                household_id=approval.household_id,
                lot_id=trade.lot_id,
                security_id=trade.security_id,
                account_id=trade.account_id,
                side=trade.side,
                quantity=str(trade.quantity),
                status=OrderStatus.STAGED.value,
                created_at=now,
                updated_at=now,
            )
        )

    write_audit(
        session,
        actor_id=actor_id,
        action="orders_staged",
        resource_type="approval_request",
        resource_id=approval_request_id,
        household_id=approval.household_id,
        details={"orders": str(len(views))},
    )
    session.flush()
    return views


def list_staged_orders(
    session: Session,
    *,
    household_id: str | None = None,
    status: OrderStatus | None = None,
    limit: int = 50,
) -> list[StagedOrderView]:
    stmt = (
        select(StagedOrderRow)
        .order_by(StagedOrderRow.created_at.desc())
        .limit(limit)
    )
    if household_id:
        stmt = stmt.where(StagedOrderRow.household_id == household_id)
    if status:
        stmt = stmt.where(StagedOrderRow.status == status.value)
    return [_row_to_view(row) for row in session.scalars(stmt).all()]


def update_order_status(
    session: Session,
    order_id: str,
    *,
    status: OrderStatus,
    actor_id: str = "system:oms",
) -> StagedOrderView:
    row = session.get(StagedOrderRow, order_id)
    if row is None:
        raise ValueError(f"Order not found: {order_id}")
    row.status = status.value
    row.updated_at = datetime.now(UTC)
    write_audit(
        session,
        actor_id=actor_id,
        action=f"order_{status.value}",
        resource_type="staged_order",
        resource_id=order_id,
        household_id=row.household_id,
        details={"approval_request_id": row.approval_request_id},
    )
    if status is OrderStatus.FILLED:
        emit_event(
            DispatchContext(session=session, actor_id=actor_id),
            Message(
                op="order.filled",
                kind=Kind.EVENT,
                payload=OrderFilled(
                    household_id=row.household_id, order_id=order_id
                ),
                correlation_id=row.approval_request_id,
                household_id=row.household_id,
            ),
        )
    return _row_to_view(row)


def _row_to_view(row: StagedOrderRow) -> StagedOrderView:
    return StagedOrderView(
        order_id=row.order_id,
        approval_request_id=row.approval_request_id,
        optimization_run_id=row.optimization_run_id,
        household_id=row.household_id,
        lot_id=row.lot_id,
        security_id=row.security_id,
        account_id=row.account_id,
        side=row.side,
        quantity=str(row.quantity),
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
