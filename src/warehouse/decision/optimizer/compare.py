"""Run heuristic vs MIP and persist solver comparison."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from warehouse.config import get_settings
from warehouse.data.ledger.views import list_lot_positions
from warehouse.decision.ips.store import load_ips
from warehouse.decision.optimizer.heuristics import run_tax_aware_optimizer
from warehouse.decision.optimizer.mip import run_mip_optimizer
from warehouse.decision.optimizer.runner import persist_optimization
from warehouse.infra.db.models import OptimizationTradeRow, SolverComparisonRow


class SolverComparisonView(BaseModel):
    comparison_id: str
    household_id: str
    heuristic_run_id: str
    mip_run_id: str
    heuristic_tax_delta: Decimal
    mip_tax_delta: Decimal
    heuristic_runtime_ms: int
    mip_runtime_ms: int
    heuristic_trade_count: int
    mip_trade_count: int
    created_at: datetime


def run_solver_comparison(session: Session, household_id: str) -> SolverComparisonView:
    ips = load_ips(session, household_id)
    if ips is None:
        raise ValueError(f"No IPS for household {household_id}")
    positions = list_lot_positions(session, household_id=household_id)
    settings = get_settings()
    snapshot = f"snap_{uuid4().hex[:8]}"

    t0 = time.perf_counter()
    heuristic_result = run_tax_aware_optimizer(
        household_id, positions, ips, settings=settings
    )
    heuristic_ms = int((time.perf_counter() - t0) * 1000)
    heuristic_view = persist_optimization(
        session,
        heuristic_result,
        input_snapshot_id=snapshot,
        actor_id="system:compare",
        solver_type="heuristic",
        runtime_ms=heuristic_ms,
        queue_approval=False,
    )

    t1 = time.perf_counter()
    mip_result = run_mip_optimizer(
        household_id, positions, ips, settings=settings)
    mip_ms = int((time.perf_counter() - t1) * 1000)
    mip_view = persist_optimization(
        session,
        mip_result,
        input_snapshot_id=snapshot,
        actor_id="system:compare",
        solver_type="mip",
        runtime_ms=mip_ms,
        queue_approval=False,
    )

    comparison_id = f"cmp_{uuid4().hex[:12]}"
    created = datetime.now(UTC)
    session.add(
        SolverComparisonRow(
            comparison_id=comparison_id,
            household_id=household_id,
            heuristic_run_id=heuristic_view.run_id,
            mip_run_id=mip_view.run_id,
            heuristic_tax_delta=heuristic_result.estimated_tax_delta,
            mip_tax_delta=mip_result.estimated_tax_delta,
            heuristic_runtime_ms=heuristic_ms,
            mip_runtime_ms=mip_ms,
            created_at=created,
        )
    )

    return SolverComparisonView(
        comparison_id=comparison_id,
        household_id=household_id,
        heuristic_run_id=heuristic_view.run_id,
        mip_run_id=mip_view.run_id,
        heuristic_tax_delta=heuristic_result.estimated_tax_delta,
        mip_tax_delta=mip_result.estimated_tax_delta,
        heuristic_runtime_ms=heuristic_ms,
        mip_runtime_ms=mip_ms,
        heuristic_trade_count=len(heuristic_result.trades),
        mip_trade_count=len(mip_result.trades),
        created_at=created,
    )


def list_solver_comparisons(
    session: Session, household_id: str, limit: int = 5
) -> list[SolverComparisonView]:
    rows = session.scalars(
        select(SolverComparisonRow)
        .where(SolverComparisonRow.household_id == household_id)
        .order_by(SolverComparisonRow.created_at.desc())
        .limit(limit)
    ).all()
    views: list[SolverComparisonView] = []
    for row in rows:
        h_trades = session.scalars(
            select(OptimizationTradeRow).where(
                OptimizationTradeRow.run_id == row.heuristic_run_id)
        ).all()
        m_trades = session.scalars(
            select(OptimizationTradeRow).where(
                OptimizationTradeRow.run_id == row.mip_run_id)
        ).all()
        views.append(
            SolverComparisonView(
                comparison_id=row.comparison_id,
                household_id=row.household_id,
                heuristic_run_id=row.heuristic_run_id,
                mip_run_id=row.mip_run_id,
                heuristic_tax_delta=row.heuristic_tax_delta,
                mip_tax_delta=row.mip_tax_delta,
                heuristic_runtime_ms=row.heuristic_runtime_ms,
                mip_runtime_ms=row.mip_runtime_ms,
                heuristic_trade_count=len(h_trades),
                mip_trade_count=len(m_trades),
                created_at=row.created_at,
            )
        )
    return views
