"""Sim / backtest harness — historical prices + lot state → after-tax outcomes."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class BacktestResult:
    """After-tax outcome vs baseline — net of implementation shortfall."""

    run_id: str
    start_date: date
    end_date: date
    after_tax_return: Decimal
    baseline_after_tax_return: Decimal
    tax_delta: Decimal
    config_hash: str
    input_snapshot_id: str


class WalkForwardError(ValueError):
    """Raised when a backtest violates walk-forward / purge discipline."""
