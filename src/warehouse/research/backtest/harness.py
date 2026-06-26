"""Backtest harness — walk-forward safe after-tax outcomes."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from warehouse.config import Settings, get_settings
from warehouse.data.ledger.views import list_lot_positions
from warehouse.infra.db.models import BacktestRunRow
from warehouse.research.backtest import BacktestResult, WalkForwardError


class BacktestRunView(BaseModel):
    run_id: str
    household_id: str
    start_date: date
    end_date: date
    after_tax_return: Decimal
    baseline_after_tax_return: Decimal
    tax_delta: Decimal
    config_hash: str
    input_snapshot_id: str
    created_at: datetime


def _config_hash(settings: Settings) -> str:
    payload = json.dumps(
        {
            "tax_config_version": settings.tax_config_version,
            "fed_stcg_rate": settings.fed_stcg_rate,
            "fed_ltcg_rate": settings.fed_ltcg_rate,
            "purge_days": settings.walk_forward_purge_days,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def run_backtest(
    session: Session,
    household_id: str,
    *,
    start_date: date,
    end_date: date,
    input_snapshot_id: str | None = None,
    settings: Settings | None = None,
) -> BacktestRunView:
    cfg = settings or get_settings()
    purge_days = cfg.walk_forward_purge_days
    if (end_date - start_date).days < purge_days:
        window_days = (end_date - start_date).days
        raise WalkForwardError(f"{window_days}d < {purge_days}d purge min")

    positions = list_lot_positions(session, household_id=household_id)
    if not positions:
        raise ValueError(f"No positions for household {household_id}")

    start_value = sum((p.total_cost_basis for p in positions), Decimal("0"))
    end_value = sum(
        (p.market_value or Decimal("0") for p in positions),
        Decimal("0"),
    )
    if start_value <= 0:
        raise ValueError("Backtest start value must be positive")

    gross_return = (end_value - start_value) / start_value
    net_gain = end_value - start_value
    taxable = max(net_gain, Decimal("0"))
    ltcg = Decimal(str(cfg.fed_ltcg_rate))
    tax_drag = taxable * ltcg / start_value
    # Baseline matches after-tax until harvest replay lowers taxable gains.
    after_tax_return = gross_return - tax_drag
    baseline_after_tax_return = gross_return - tax_drag
    tax_delta = after_tax_return - baseline_after_tax_return

    snapshot = input_snapshot_id or f"snap_{uuid4().hex[:8]}"
    config_hash = _config_hash(cfg)
    run_id = f"bt_{uuid4().hex[:12]}"
    created = datetime.now(UTC)

    session.add(
        BacktestRunRow(
            run_id=run_id,
            household_id=household_id,
            start_date=start_date,
            end_date=end_date,
            after_tax_return=after_tax_return,
            baseline_after_tax_return=baseline_after_tax_return,
            tax_delta=tax_delta,
            config_hash=config_hash,
            input_snapshot_id=snapshot,
            created_at=created,
        )
    )

    return BacktestRunView(
        run_id=run_id,
        household_id=household_id,
        start_date=start_date,
        end_date=end_date,
        after_tax_return=after_tax_return,
        baseline_after_tax_return=baseline_after_tax_return,
        tax_delta=tax_delta,
        config_hash=config_hash,
        input_snapshot_id=snapshot,
        created_at=created,
    )


def list_backtest_runs(
    session: Session, household_id: str, limit: int = 5
) -> list[BacktestRunView]:
    rows = session.scalars(
        select(BacktestRunRow)
        .where(BacktestRunRow.household_id == household_id)
        .order_by(BacktestRunRow.created_at.desc())
        .limit(limit)
    ).all()
    return [
        BacktestRunView(
            run_id=r.run_id,
            household_id=r.household_id,
            start_date=r.start_date,
            end_date=r.end_date,
            after_tax_return=r.after_tax_return,
            baseline_after_tax_return=r.baseline_after_tax_return,
            tax_delta=r.tax_delta,
            config_hash=r.config_hash,
            input_snapshot_id=r.input_snapshot_id,
            created_at=r.created_at,
        )
        for r in rows
    ]


def to_frozen_result(view: BacktestRunView) -> BacktestResult:
    return BacktestResult(
        run_id=view.run_id,
        start_date=view.start_date,
        end_date=view.end_date,
        after_tax_return=view.after_tax_return,
        baseline_after_tax_return=view.baseline_after_tax_return,
        tax_delta=view.tax_delta,
        config_hash=view.config_hash,
        input_snapshot_id=view.input_snapshot_id,
    )
