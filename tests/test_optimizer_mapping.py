"""po0 sleeve→risk mapping — total + raises (silent-success regression §A.1).

``IpsSleeve`` and ``research.risk.AssetClass`` are value-identical
``StrEnum``s, so a naive ``class_expected_return[sleeve]`` join *silently
succeeds* and would mis-price μ/Σ the instant either enum drifts. The explicit
raising map is the guard; this test is its regression.
"""

from __future__ import annotations

import pytest

from warehouse.decision.ips.sleeves import IpsSleeve
from warehouse.decision.optimizer.models import OptimizerMappingError
from warehouse.decision.optimizer.rebalance import (
    _SLEEVE_TO_RISK,
    risk_class_for,
)
from warehouse.research.risk.models import AssetClass as RiskClass


def test_sleeve_to_risk_is_total() -> None:
    """Every IpsSleeve maps to a risk class — no member left unmapped."""
    for sleeve in IpsSleeve:
        assert isinstance(risk_class_for(sleeve), RiskClass)
    assert set(_SLEEVE_TO_RISK) == set(IpsSleeve)


def test_risk_class_for_raises_on_unmapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Future enum drift fails loudly, never a silent zero-μ."""
    monkeypatch.delitem(_SLEEVE_TO_RISK, IpsSleeve.EQUITY)
    with pytest.raises(OptimizerMappingError, match="no risk-class mapping"):
        risk_class_for(IpsSleeve.EQUITY)
