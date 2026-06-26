"""Persist optimization runs and trades."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from warehouse.config import get_settings
from warehouse.data.ledger.views import list_lot_positions
from warehouse.decision.approval.service import create_approval_request
from warehouse.decision.ips.store import load_ips
from warehouse.decision.optimizer import OptimizationResult, TradeProposal
from warehouse.decision.optimizer.heuristics import run_tax_aware_optimizer
from warehouse.infra.audit.store import write_audit
from warehouse.infra.db.models import OptimizationRunRow, OptimizationTradeRow


class OptimizationRunView(BaseModel):
    run_id: str
    household_id: str
    config_version: str
    estimated_tax_delta: str
    binding_constraints: list[str]
    input_snapshot_id: str
    created_at: datetime
    trades: list[TradeProposal]


def persist_optimization(
    session: Session,
    result: OptimizationResult,
    *,
    input_snapshot_id: str,
    actor_id: str = "system:optimizer",
    solver_type: str = "heuristic",
    runtime_ms: int | None = None,
    queue_approval: bool = True,
) -> OptimizationRunView:
    run_id = f"opt_{uuid4().hex[:12]}"
    created = datetime.now(UTC)
    session.add(
        OptimizationRunRow(
            run_id=run_id,
            household_id=result.household_id,
            config_version=result.config_version,
            estimated_tax_delta=result.estimated_tax_delta,
            binding_constraints_json=json.dumps(result.binding_constraints),
            input_snapshot_id=input_snapshot_id,
            status="complete",
            solver_type=solver_type,
            runtime_ms=runtime_ms,
            created_at=created,
        )
    )
    for trade in result.trades:
        session.add(
            OptimizationTradeRow(
                run_id=run_id,
                lot_id=trade.lot_id,
                security_id=trade.security_id,
                account_id=trade.account_id,
                side=trade.side,
                quantity=trade.quantity,
                rationale=trade.rationale,
            )
        )
    write_audit(
        session,
        actor_id=actor_id,
        action="optimization_complete",
        resource_type="optimization_run",
        resource_id=run_id,
        household_id=result.household_id,
        details={
            "trades": str(len(result.trades)),
            "tax_delta": str(result.estimated_tax_delta),
        },
    )
    if queue_approval:
        create_approval_request(session, run_id, result.household_id)
    session.flush()
    return OptimizationRunView(
        run_id=run_id,
        household_id=result.household_id,
        config_version=result.config_version,
        estimated_tax_delta=str(result.estimated_tax_delta),
        binding_constraints=result.binding_constraints,
        input_snapshot_id=input_snapshot_id,
        created_at=created,
        trades=result.trades,
    )


def run_and_persist_optimizer(
    session: Session,
    household_id: str,
    *,
    input_snapshot_id: str | None = None,
) -> OptimizationRunView:
    ips = load_ips(session, household_id)
    if ips is None:
        raise ValueError(f"No IPS for household {household_id}")
    positions = list_lot_positions(session, household_id=household_id)
    snapshot = input_snapshot_id or f"snap_{uuid4().hex[:8]}"
    result = run_tax_aware_optimizer(
        household_id, positions, ips, settings=get_settings()
    )
    return persist_optimization(session, result, input_snapshot_id=snapshot)


def list_optimization_runs(
    session: Session, household_id: str, limit: int = 5
) -> list[OptimizationRunView]:
    runs = session.scalars(
        select(OptimizationRunRow)
        .where(OptimizationRunRow.household_id == household_id)
        .order_by(OptimizationRunRow.created_at.desc())
        .limit(limit)
    ).all()
    views: list[OptimizationRunView] = []
    for run in runs:
        trades = session.scalars(
            select(OptimizationTradeRow).where(
                OptimizationTradeRow.run_id == run.run_id
            )
        ).all()
        views.append(
            OptimizationRunView(
                run_id=run.run_id,
                household_id=run.household_id,
                config_version=run.config_version,
                estimated_tax_delta=str(run.estimated_tax_delta),
                binding_constraints=json.loads(run.binding_constraints_json),
                input_snapshot_id=run.input_snapshot_id,
                created_at=run.created_at,
                trades=[
                    TradeProposal(
                        lot_id=t.lot_id,
                        security_id=t.security_id,
                        account_id=t.account_id,
                        side=t.side,
                        quantity=t.quantity,
                        rationale=t.rationale,
                    )
                    for t in trades
                ],
            )
        )
    return views
