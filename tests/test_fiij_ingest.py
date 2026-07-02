"""FIIJ finance-view ingest (pv2) — signal-sourced views, honest confidence.

Falsifiers: views are ``fiij``-sourced with ``expected_excess`` signed like the
FIIJ ``value`` and a ``confidence`` traceable to a FIIJ threshold/Brier (never
invented); a failing-OOS-Brier signal is ingested BELOW the floor and never
upgraded (§2 #9); an unmapped signal RAISES ``FiijMappingError``; a snapshot
dated after ``as_of`` RAISES ``WalkForwardError`` (M3 guard live); the op
returns a frozen snapshot and is the only new ``ingest.fiij`` op.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

import warehouse.messaging.handlers  # noqa: F401 — register ops
from warehouse.config import get_settings
from warehouse.data.ingest.fiij import (
    FiijFinanceViewSnapshot,
    FiijMappingError,
    default_fiij_export_path,
    ingest_fiij_finance_view,
    load_fiij_snapshot,
)
from warehouse.decision.beliefs.models import ViewSource
from warehouse.messaging import (
    REGISTRY,
    DispatchContext,
    Kind,
    Message,
    dispatch_message,
)
from warehouse.messaging.payloads import FiijIngestPayload
from warehouse.research.backtest import WalkForwardError

_FIXTURES = Path(__file__).parent / "fixtures"
_AS_OF = date(2026, 6, 30)


def test_fiij_confidence_from_calibration() -> None:
    snapshot = load_fiij_snapshot(_AS_OF, path=default_fiij_export_path())
    assert snapshot.regime_class == "neutral"  # captured on the snapshot (#11)
    by_sleeve = {v.sleeve.value: v for v in snapshot.views}

    equity = by_sleeve["equity"]
    assert equity.source == ViewSource.FIIJ
    assert equity.source.value == "fiij"
    assert equity.source_ref == "silk_equity@2026-06-30"
    # expected_excess signed like the FIIJ value (+0.42 → positive tilt).
    assert equity.expected_excess > 0
    # Confidence traces to the passing OOS Brier — at/above the pinned floor.
    floor = Decimal(str(get_settings().fiij_confidence_floor))
    assert equity.confidence >= floor
    assert "oos_brier=0.18" in equity.calibration
    assert "pass" in equity.calibration


def test_fiij_expected_excess_scaled_and_signed() -> None:
    views = ingest_fiij_finance_view(default_fiij_export_path(), _AS_OF)
    scale = Decimal(str(get_settings().fiij_value_excess_scale))
    by_sleeve = {v.sleeve.value: v for v in views}
    # silk_commodity_etf value -0.30 → negative tilt = scale * value.
    commodity = by_sleeve["commodities"]
    assert commodity.expected_excess < 0
    assert commodity.expected_excess == (scale * Decimal("-0.30")).quantize(
        Decimal("0.00000001")
    )


def test_failing_brier_low_confidence() -> None:
    """A failing-OOS-Brier signal ingests below the floor, never upgraded."""
    views = ingest_fiij_finance_view(default_fiij_export_path(), _AS_OF)
    floor = Decimal(str(get_settings().fiij_confidence_floor))
    by_sleeve = {v.sleeve.value: v for v in views}
    for key in ("commodities", "alternatives"):
        v = by_sleeve[key]
        assert v.confidence < floor, f"{key} upgraded above the floor"
        assert "fail" in v.calibration


def test_fiij_unmapped_signal_raises() -> None:
    """An unmapped FIIJ signal RAISES — never a silent drop (mirrors po0)."""
    with pytest.raises(FiijMappingError, match="silk_structured_exotic"):
        ingest_fiij_finance_view(_FIXTURES / "fiij_unmapped", _AS_OF)


def test_fiij_future_snapshot_raises() -> None:
    """Walk-forward falsifier: only a future-dated snapshot raises."""
    with pytest.raises(WalkForwardError):
        load_fiij_snapshot(_AS_OF, path=_FIXTURES / "fiij_future")


def test_fiij_selects_snapshot_at_or_before_as_of() -> None:
    """as_of on the earlier snapshot date picks it, not the later one."""
    snapshot = load_fiij_snapshot(
        date(2026, 6, 29), path=default_fiij_export_path()
    )
    assert snapshot.as_of_date == date(2026, 6, 29)
    # The 06-29 slice carries only the equity sheet.
    assert {v.sleeve.value for v in snapshot.views} == {"equity"}


def test_ingest_fiij_is_new_op_and_returns_snapshot() -> None:
    ingest_ops = {op for op in REGISTRY if op.startswith("ingest.")}
    assert "ingest.fiij" in ingest_ops
    pm_ops = {op for op in REGISTRY if op.startswith("pm.")}
    assert pm_ops == {"pm.advise"}
    beliefs_ops = {op for op in REGISTRY if op.startswith("beliefs.")}
    assert beliefs_ops == {"beliefs.update"}

    ctx = DispatchContext(session=_Poison())  # type: ignore[arg-type]
    out = dispatch_message(
        ctx,
        Message(
            op="ingest.fiij",
            kind=Kind.EVALUATE,
            payload=FiijIngestPayload(
                as_of_date=_AS_OF, export_path=str(default_fiij_export_path())
            ),
            correlation_id="fiij-trace",
        ),
    )
    assert isinstance(out, FiijFinanceViewSnapshot)
    assert out.views  # the pure leg never touched the poisoned session


class _Poison:
    def __getattribute__(self, name: str) -> object:
        raise AssertionError(f"ingest.fiij touched session.{name}")
