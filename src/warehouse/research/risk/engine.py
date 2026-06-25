"""Portfolio risk engine — class + duration decomposition."""

from __future__ import annotations

from decimal import Decimal

from warehouse.config import get_settings
from warehouse.research.risk.by_class import aggregate_class_risk, evaluate_class_risk
from warehouse.research.risk.by_duration import evaluate_duration_risk
from warehouse.research.risk.fingerprint import portfolio_fingerprint
from warehouse.research.risk.models import (
    AssetPortfolio,
    MeasurementMode,
    MeasurementSummary,
    PortfolioRiskReport,
    RiskHorizon,
)


def evaluate_portfolio_risk(
    portfolio: AssetPortfolio,
    horizon: RiskHorizon,
) -> PortfolioRiskReport:
    settings = get_settings()
    diversification = Decimal(str(settings.risk_diversification_factor))

    by_class = [evaluate_class_risk(slot, horizon) for slot in portfolio.allocations]
    total_risk = aggregate_class_risk(by_class, diversification)
    by_duration = evaluate_duration_risk(portfolio.allocations, horizon, by_class)

    expected_return = sum((c.expected_return for c in by_class), Decimal("0"))
    measurable_weight = sum(
        (c.weight for c in by_class if c.measurement == MeasurementMode.MEASURABLE),
        Decimal("0"),
    )
    fermi_weight = Decimal("1") - measurable_weight
    fermi_risk = sum(
        (c.risk_contribution for c in by_class if c.measurement == MeasurementMode.FERMI),
        Decimal("0"),
    )
    fermi_share = fermi_risk / total_risk if total_risk > 0 else Decimal("0")

    fermi_band = Decimal(str(settings.risk_fermi_confidence_width))
    confidence_low = max(total_risk * (Decimal("1") - fermi_band * fermi_share), Decimal("0"))
    confidence_high = total_risk * (Decimal("1") + fermi_band * fermi_share)

    return PortfolioRiskReport(
        portfolio_id=portfolio.portfolio_id,
        horizon_years=horizon.years,
        total_risk=total_risk,
        expected_return=expected_return,
        confidence_low=confidence_low,
        confidence_high=confidence_high,
        diversification_factor=diversification,
        by_class=by_class,
        by_duration=by_duration,
        measurement_summary=MeasurementSummary(
            measurable_weight=measurable_weight,
            fermi_weight=fermi_weight,
            fermi_risk_share=fermi_share,
        ),
        model_version=settings.risk_model_version,
        input_fingerprint=portfolio_fingerprint(portfolio, horizon),
    )
