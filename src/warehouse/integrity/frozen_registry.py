"""Registry of types that must reject in-place mutation (no silent no-ops)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ValidationError

from warehouse.config import Settings
from warehouse.models.events import Event, EventType
from warehouse.research.backtest import BacktestResult

# Append new audit/replay-critical immutable types here.
FROZEN_TYPES: tuple[type[Any], ...] = (
    BacktestResult,
    Event,
    Settings,
)


def _sample_instance(cls: type[Any]) -> Any:
    if cls is BacktestResult:
        return BacktestResult(
            run_id="run_test",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            after_tax_return=Decimal("0.05"),
            baseline_after_tax_return=Decimal("0.04"),
            tax_delta=Decimal("0.01"),
            config_hash="abc123",
            input_snapshot_id="snap_test",
        )
    if cls is Event:
        return Event(
            event_id="evt_test",
            account_id="acct_test",
            event_type=EventType.TRADE,
            occurred_at=datetime(2024, 6, 1, tzinfo=UTC),
        )
    if cls is Settings:
        return Settings()
    raise TypeError(f"No sample factory for frozen type {cls!r}")


def _mutation_probe_attr(instance: Any) -> str:
    if isinstance(instance, BacktestResult):
        return "run_id"
    if isinstance(instance, Event):
        return "event_id"
    if isinstance(instance, Settings):
        return "app_env"
    raise TypeError(f"No mutation probe for {type(instance)!r}")


def assert_rejects_mutation(instance: Any, attr: str | None = None, value: Any = "mutated") -> None:
    """Raise AssertionError if setattr succeeds (silent mutation)."""
    field = attr or _mutation_probe_attr(instance)
    try:
        setattr(instance, field, value)
    except (FrozenInstanceError, ValidationError, TypeError):
        return
    raise AssertionError(
        f"{type(instance).__name__}.{field} accepted mutation — type must be frozen "
        f"(frozen dataclass or pydantic ConfigDict(frozen=True))"
    )


def frozen_type_samples() -> list[tuple[type[Any], Any]]:
    return [(cls, _sample_instance(cls)) for cls in FROZEN_TYPES]


def is_registered_frozen_type(cls: type[Any]) -> bool:
    if cls in FROZEN_TYPES:
        return True
    if is_dataclass(cls) and cls.__dataclass_params__.frozen:
        return True
    if issubclass(cls, BaseModel) and cls.model_config.get("frozen"):
        return True
    return False
