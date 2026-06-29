"""Month-end reporting — fan-out ``report.build`` per household."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

import warehouse.messaging.handlers  # noqa: F401 — register catalog ops
from warehouse.infra.db.models import EntityRow
from warehouse.messaging import (
    DispatchContext,
    Kind,
    Message,
    dispatch_message,
)
from warehouse.messaging.payloads import ReportBuildPayload
from warehouse.models.entities import EntityType
from warehouse.reporting.report_writer.models import WrittenHouseholdReport
from warehouse.reporting.report_writer.writer import resolve_report_as_of


class MonthEndHouseholdOutcome(BaseModel):
    """Per-household month-end report build outcome."""

    model_config = ConfigDict(frozen=True)

    household_id: str
    status: str  # "completed" | "failed"
    written: WrittenHouseholdReport | None = None
    error: str | None = None


class MonthEndReportingResult(BaseModel):
    """Batch month-end reporting result — one row per household."""

    model_config = ConfigDict(frozen=True)

    as_of_date: date
    correlation_id: str
    started_at: datetime
    finished_at: datetime
    outcomes: tuple[MonthEndHouseholdOutcome, ...]

    @property
    def completed_count(self) -> int:
        return sum(
            1 for outcome in self.outcomes if outcome.status == "completed"
        )

    @property
    def failed_count(self) -> int:
        return sum(
            1 for outcome in self.outcomes if outcome.status == "failed"
        )


def list_household_ids(session: Session) -> tuple[str, ...]:
    """Return all household entity ids from the graph."""
    rows = session.scalars(
        select(EntityRow.entity_id)
        .where(EntityRow.entity_type == EntityType.HOUSEHOLD)
        .order_by(EntityRow.entity_id)
    ).all()
    return tuple(rows)


def run_month_end_reporting(
    session: Session,
    household_id: str,
    *,
    as_of_date: date | None = None,
    period_label: str | None = None,
    correlation_id: str | None = None,
    actor_id: str = "system:month_end_reporting",
) -> WrittenHouseholdReport:
    """Build month-end report packs for one household via ``report.build``."""
    as_of = resolve_report_as_of(session, as_of_date)
    corr = correlation_id or f"month_end_{uuid4().hex[:12]}"
    ctx = DispatchContext(
        session=session,
        actor_id=actor_id,
        correlation_id=corr,
    )
    try:
        result = dispatch_message(
            ctx,
            Message(
                op="report.build",
                kind=Kind.COMMAND,
                payload=ReportBuildPayload(
                    household_id=household_id,
                    period_label=period_label,
                    as_of_date=as_of,
                ),
                correlation_id=corr,
                household_id=household_id,
            ),
        )
    except Exception as err:
        raise RuntimeError(
            f"month-end reporting failed for {household_id} "
            f"(as_of={as_of.isoformat()}, correlation_id={corr}): {err}"
        ) from err
    if not isinstance(result, WrittenHouseholdReport):
        raise RuntimeError(
            f"month-end reporting returned unexpected type for "
            f"{household_id} (as_of={as_of.isoformat()}, "
            f"correlation_id={corr})"
        )
    return result


def run_month_end_reporting_batch(
    session: Session,
    *,
    as_of_date: date | None = None,
    period_label: str | None = None,
    household_ids: list[str] | None = None,
    actor_id: str = "system:month_end_reporting",
) -> MonthEndReportingResult:
    """Fan out month-end ``report.build`` with isolated failures."""
    as_of = resolve_report_as_of(session, as_of_date)
    correlation_id = f"month_end_batch_{uuid4().hex[:12]}"
    started_at = datetime.now(UTC)
    hh_ids = (
        list(household_ids)
        if household_ids is not None
        else list(list_household_ids(session))
    )

    outcomes: list[MonthEndHouseholdOutcome] = []
    for household_id in hh_ids:
        try:
            written = run_month_end_reporting(
                session,
                household_id,
                as_of_date=as_of,
                period_label=period_label,
                correlation_id=correlation_id,
                actor_id=actor_id,
            )
            outcomes.append(
                MonthEndHouseholdOutcome(
                    household_id=household_id,
                    status="completed",
                    written=written,
                )
            )
        except Exception as err:
            outcomes.append(
                MonthEndHouseholdOutcome(
                    household_id=household_id,
                    status="failed",
                    error=str(err),
                )
            )

    return MonthEndReportingResult(
        as_of_date=as_of,
        correlation_id=correlation_id,
        started_at=started_at,
        finished_at=datetime.now(UTC),
        outcomes=tuple(outcomes),
    )
