"""FIIJ finance-view ingest adapter (pv2) — the first LIVE signal source.

[The-FIIJ](https://github.com/hcarstens/The-FIIJ) is a daily 30-day forecast
engine that already performs the *daily-statistics → scored directional signal*
transform, so the warehouse **ingests** its output rather than re-deriving it
(§2 honesty rule: we ingest FIIJ's alpha, never fabricate our own). This is the
authoritative pv2 adapter (impl plan §11 Addendum A).

Boundaries (§11 A.3):

- **Read-only, one-way.** The adapter never writes back to FIIJ; it takes a
  path (transport-agnostic — a live git/HTTP pull is pv2b).
- **No fabricated alpha.** Every ``View`` traces to a FIIJ ``signal.id``
  (``source_ref``); an unmapped signal RAISES ``FiijMappingError`` (mirrors the
  optimizer's total ``_SLEEVE_TO_RISK`` map — never a silent drop); a FAILING-
  OOS-Brier strategy is ingested strictly BELOW the pinned confidence floor and
  is NEVER upgraded (§2 #9).
- **Walk-forward (M3).** ``assert_scenario_observations_not_after`` guards the
  snapshot dates: if the only snapshot available is dated AFTER ``as_of`` it
  RAISES ``WalkForwardError`` — a live call site for a previously dead guard.
- **Sleeve-level v0.** Macro-sheet + strategy-tag signals net to a tilt per
  6-sleeve; FIIJ's cross-sectional (name-picking) edge is discarded and the
  panels say so. Per-ticker ``breakouts.csv`` is the pv5 input, deferred here.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from warehouse.config import Settings, get_settings, repo_root
from warehouse.decision.beliefs.models import View, ViewSource
from warehouse.decision.ips.sleeves import IpsSleeve
from warehouse.research.backtest.walk_forward import (
    assert_scenario_observations_not_after,
)

_HISTORY_FILE = "finance_view_history.json"
_THRESHOLDS_FILE = "calibrated_thresholds.json"
_EXCESS_QUANTUM = Decimal("0.00000001")
_CONF_QUANTUM = Decimal("0.0001")
_CONF_EPS = Decimal("0.0001")  # keep a failing-Brier view strictly below floor

# Explicit, TOTAL, RAISING FIIJ-signal → IPS-sleeve map. Mirrors po0's
# ``_SLEEVE_TO_RISK`` discipline (portfolio_optimization_implementation.md
# §A.1): a naive dict-get would silently drop an unmapped signal the instant
# FIIJ adds a strategy tag. An unmapped ``signal.id`` RAISES a mapping error
# (see ``_sleeve_for_signal``) — never a silent drop. Keyed by FIIJ strategy
# tag / macro-sheet ``signal.id``.
_FIIJ_SIGNAL_TO_SLEEVE: dict[str, IpsSleeve] = {
    "silk_equity": IpsSleeve.EQUITY,
    "silk_commodity_etf": IpsSleeve.COMMODITIES,
    "silk_crypto": IpsSleeve.ALTERNATIVES,
    "cash_flow": IpsSleeve.EQUITY,
    "fx": IpsSleeve.FX,
    "rates": IpsSleeve.FIXED_INCOME,
}


class FiijIngestError(ValueError):
    """A FIIJ export is missing/malformed — errors bubble, never a silent."""


class FiijMappingError(ValueError):
    """A FIIJ signal maps to no IPS sleeve — a loud failure, never a drop.

    Mirrors the optimizer's ``OptimizerMappingError`` / ``_SLEEVE_TO_RISK``
    total-map discipline: an unmapped ``signal.id`` cannot be assigned a sleeve
    tilt, so the ingest raises rather than silently discarding the view.
    """


class FiijFinanceViewSnapshot(BaseModel):
    """One FIIJ daily finance-view snapshot ingested as ``fiij`` views.

    Frozen + registered (M1/M2): a snapshot is a replay fingerprint (the FIIJ
    file + the pinned value→excess scale + Brier map → versioned views). It
    carries ``regime_class`` — the free regime read pv3 uses to pick the Σ
    regime (#11) — alongside the human-facing ``regime_label``.
    """

    model_config = ConfigDict(frozen=True)

    as_of_date: date
    fetched_at: datetime
    regime_label: str
    regime_class: str
    views: tuple[View, ...]
    fiij_config_version: str


def default_fiij_export_path() -> Path:
    """Packaged FIIJ sample slice — used when ``fiij_export_path`` is empty."""
    return (
        repo_root() / "src" / "warehouse" / "data" / "ingest" / "fiij_sample"
    )


def _resolve_export_dir(path: str | Path | None, settings: Settings) -> Path:
    if path is not None:
        return Path(path)
    if settings.fiij_export_path:
        return Path(settings.fiij_export_path)
    return default_fiij_export_path()


def _load_json(path: Path) -> object:
    if not path.is_file():
        raise FiijIngestError(f"FIIJ export file not found: {path}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as err:
        raise FiijIngestError(f"malformed FIIJ export {path}: {err}") from err


def _snapshot_list(raw: object) -> list[dict[str, object]]:
    """Accept a top-level list (§11 A.1) or an object with ``snapshots``."""
    if isinstance(raw, list):
        return [s for s in raw if isinstance(s, dict)]
    if isinstance(raw, dict):
        for key in ("snapshots", "history"):
            inner = raw.get(key)
            if isinstance(inner, list):
                return [s for s in inner if isinstance(s, dict)]
    raise FiijIngestError(
        "FIIJ finance_view_history.json must be a list of snapshots "
        "(or an object with a 'snapshots'/'history' list)"
    )


def _parse_date(value: object, *, field: str) -> date:
    if not isinstance(value, str):
        raise FiijIngestError(f"FIIJ snapshot missing/invalid {field}")
    return date.fromisoformat(value[:10])


def _sleeve_for_signal(signal_id: str) -> IpsSleeve:
    try:
        return _FIIJ_SIGNAL_TO_SLEEVE[signal_id]
    except KeyError as err:  # bubble to surface, never silently drop the view
        raise FiijMappingError(
            f"no IPS-sleeve mapping for FIIJ signal id {signal_id!r}; "
            f"known signals: {sorted(_FIIJ_SIGNAL_TO_SLEEVE)}"
        ) from err


def _confidence_from_brier(
    brier: float, *, floor: Decimal, ceil: Decimal, passes: bool
) -> Decimal:
    """Ω-confidence traced to the OOS Brier — never invented (§2 #9).

    ``raw = 1 − brier`` is the evidence (lower Brier → higher confidence). A
    PASSING strategy earns at least the floor (clamped into ``[floor, ceil]``);
    a FAILING strategy is capped strictly BELOW the floor, never upgraded.
    """
    raw = Decimal(str(1.0 - brier))
    if passes:
        return max(floor, min(ceil, raw)).quantize(_CONF_QUANTUM)
    capped = min(raw, floor - _CONF_EPS)
    if capped < Decimal("0"):
        capped = Decimal("0")
    return capped.quantize(_CONF_QUANTUM)


def _threshold_for(
    thresholds: dict[str, object], signal_id: str
) -> dict[str, object] | None:
    entry = thresholds.get(signal_id)
    if isinstance(entry, dict):
        return entry
    return None


def _views_for_snapshot(
    snapshot: dict[str, object],
    thresholds_raw: dict[str, object],
    *,
    as_of_date: date,
    settings: Settings,
) -> tuple[View, ...]:
    thresholds = thresholds_raw.get("thresholds")
    if not isinstance(thresholds, dict):
        thresholds = {}
    scale = Decimal(str(settings.fiij_value_excess_scale))
    floor = Decimal(str(settings.fiij_confidence_floor))
    ceil = Decimal("1") - _CONF_EPS
    pass_max = float(settings.fiij_brier_pass_max)
    regime_label = str(snapshot.get("regime_label", ""))

    sheets = snapshot.get("sheets")
    if not isinstance(sheets, list):
        raise FiijIngestError("FIIJ snapshot has no 'sheets' list")

    views: list[View] = []
    for sheet in sheets:
        if not isinstance(sheet, dict):
            continue
        signals = sheet.get("signals")
        if not isinstance(signals, list):
            continue
        for sig in signals:
            if not isinstance(sig, dict):
                continue
            if not sig.get("available", True):
                continue
            signal_id = sig.get("id")
            if not isinstance(signal_id, str):
                raise FiijIngestError("FIIJ signal missing 'id'")
            value = sig.get("value")
            if not isinstance(value, (int, float)):
                raise FiijIngestError(
                    f"FIIJ signal {signal_id!r} missing numeric 'value'"
                )
            sleeve = _sleeve_for_signal(signal_id)
            expected_excess = (scale * Decimal(str(value))).quantize(
                _EXCESS_QUANTUM, rounding=ROUND_HALF_EVEN
            )
            entry = _threshold_for(thresholds, signal_id)
            brier = None
            if entry is not None:
                b = entry.get("oos_brier")
                if isinstance(b, (int, float)):
                    brier = float(b)
            if brier is None:
                # No calibration for this strategy → cannot claim confidence:
                # sit just below the floor; calibration not_computed.
                confidence = (floor - _CONF_EPS).quantize(_CONF_QUANTUM)
                calibration = "not_computed"
            else:
                passes = brier <= pass_max
                confidence = _confidence_from_brier(
                    brier, floor=floor, ceil=ceil, passes=passes
                )
                calibration = (
                    f"oos_brier={brier:g} ({'pass' if passes else 'fail'})"
                )
            detail = str(sig.get("detail", ""))
            views.append(
                View(
                    sleeve=sleeve,
                    expected_excess=expected_excess,
                    confidence=confidence,
                    source=ViewSource.FIIJ,
                    source_ref=f"{signal_id}@{as_of_date.isoformat()}",
                    calibration=calibration,
                    rationale=(
                        f"FIIJ {signal_id} value={value:g} "
                        f"(regime {regime_label or 'n/a'}); {detail}".strip()
                    ),
                )
            )
    return tuple(views)


def load_fiij_snapshot(
    as_of: date,
    *,
    path: str | Path | None = None,
    settings: Settings | None = None,
) -> FiijFinanceViewSnapshot:
    """Load the FIIJ snapshot AT OR BEFORE ``as_of`` → a frozen snapshot.

    Walk-forward (M3): if no snapshot is dated ≤ ``as_of`` but a later one
    exists, ``assert_scenario_observations_not_after`` RAISES a
    ``WalkForwardError`` (a live call site for a previously dead guard).
    Raises ``FiijIngestError``
    when the export is missing and ``FiijMappingError`` on an unmapped signal.
    """
    cfg = settings or get_settings()
    export_dir = _resolve_export_dir(path, cfg)
    raw = _load_json(export_dir / _HISTORY_FILE)
    snapshots = _snapshot_list(raw)
    if not snapshots:
        raise FiijIngestError(
            f"FIIJ finance-view history is empty: {export_dir}"
        )

    dated = [
        (_parse_date(s.get("as_of_date"), field="as_of_date"), s)
        for s in snapshots
    ]
    candidates = [(d, s) for d, s in dated if d <= as_of]
    if not candidates:
        # The only snapshots available are dated AFTER as_of → walk-forward
        # violation. Wire the guard (it names the future date) then bubble.
        assert_scenario_observations_not_after(
            [(d, "fiij snapshot") for d, _ in dated],
            as_of=as_of,
        )
        raise FiijIngestError(
            f"no FIIJ snapshot at or before {as_of.isoformat()}"
        )

    chosen_date, chosen = max(candidates, key=lambda row: row[0])

    thresholds_raw = _load_json(export_dir / _THRESHOLDS_FILE)
    if not isinstance(thresholds_raw, dict):
        raise FiijIngestError(
            f"{_THRESHOLDS_FILE} must be a JSON object at {export_dir}"
        )

    views = _views_for_snapshot(
        chosen, thresholds_raw, as_of_date=chosen_date, settings=cfg
    )
    fetched = chosen.get("fetched_at")
    fetched_at = (
        datetime.fromisoformat(str(fetched))
        if isinstance(fetched, str)
        else datetime.combine(chosen_date, datetime.min.time())
    )
    return FiijFinanceViewSnapshot(
        as_of_date=chosen_date,
        fetched_at=fetched_at,
        regime_label=str(chosen.get("regime_label", "")),
        regime_class=str(chosen.get("regime_class", "")),
        views=views,
        fiij_config_version=cfg.fiij_config_version,
    )


def ingest_fiij_finance_view(
    path: str | Path,
    as_of: date,
    *,
    settings: Settings | None = None,
) -> tuple[View, ...]:
    """Adapter entry point (§11 A.2): FIIJ export path + ``as_of`` → ``View``s.

    Thin wrapper over ``load_fiij_snapshot`` returning just the ``fiij`` views
    (the full snapshot — with ``regime_class`` — is the op's return).
    """
    return load_fiij_snapshot(as_of, path=path, settings=settings).views
