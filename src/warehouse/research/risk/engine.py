"""Portfolio risk engine — unit hierarchy Levels 1–4."""

from __future__ import annotations

from decimal import Decimal

from warehouse.research.risk.assumptions import RiskAssumptions
from warehouse.research.risk.by_class import (
    build_sleeve_states,
    evaluate_class_contributions,
    portfolio_expected_return,
)
from warehouse.research.risk.by_duration import evaluate_duration_risk
from warehouse.research.risk.covariance import portfolio_covariance
from warehouse.research.risk.fingerprint import portfolio_fingerprint
from warehouse.research.risk.liquidity import evaluate_liquidity
from warehouse.research.risk.models import (
    AssetPortfolio,
    Level1PortfolioRisk,
    Level2Contributions,
    Level3Sensitivities,
    MeasurementMode,
    MeasurementSummary,
    PortfolioRiskReport,
    RiskHorizon,
    RiskManifestMeta,
    RiskMetric,
    RiskUnitType,
)
from warehouse.research.risk.scenarios import assumptions_for
from warehouse.research.risk.sensitivity import evaluate_sensitivities
from warehouse.research.risk.stress import evaluate_stress
from warehouse.research.risk.var_es import (
    dollar_tail,
    horizon_scale,
    parametric_es,
    parametric_var,
)


def evaluate_portfolio_risk(
    portfolio: AssetPortfolio,
    horizon: RiskHorizon,
    *,
    notional_usd: Decimal | None = None,
    assumptions: RiskAssumptions | None = None,
    stress_filter: str | None = None,
) -> PortfolioRiskReport:
    priors = assumptions or assumptions_for("base")
    mark_source = "model_prior"

    states = build_sleeve_states(portfolio.allocations, priors)
    cov = portfolio_covariance(states, priors)
    annual_return = portfolio_expected_return(states, priors)
    annual_vol = cov.portfolio_volatility
    horizon_vol = horizon_scale(annual_vol, horizon.years)
    horizon_return = annual_return * horizon.years

    var_metric = parametric_var(
        annual_vol,
        annual_return,
        horizon.years,
        priors.var_alpha,
        assumptions=priors,
        mark_source=mark_source,
    )
    es_metric = parametric_es(
        annual_vol,
        annual_return,
        horizon.years,
        priors.es_alpha,
        assumptions=priors,
        mark_source=mark_source,
    )

    by_class = evaluate_class_contributions(states, cov, priors)
    by_duration = evaluate_duration_risk(
        portfolio.allocations, horizon, by_class
    )

    measurable_weight = sum(
        (
            c.weight
            for c in by_class
            if c.measurement == MeasurementMode.MEASURABLE
        ),
        Decimal("0"),
    )
    fermi_weight = Decimal("1") - measurable_weight
    fermi_risk = sum(
        (
            c.pct_variance_contribution
            for c in by_class
            if c.measurement == MeasurementMode.FERMI
        ),
        Decimal("0"),
    )
    fermi_share = fermi_risk if fermi_risk <= Decimal("1") else Decimal("1")

    fermi_band = Decimal(str(priors.fermi_confidence_width))
    confidence_low = max(
        horizon_vol * (Decimal("1") - fermi_band * fermi_share), Decimal("0")
    )
    confidence_high = horizon_vol * (Decimal("1") + fermi_band * fermi_share)

    dollar_var = (
        dollar_tail(var_metric, notional_usd) if notional_usd else None
    )
    dollar_es = dollar_tail(es_metric, notional_usd) if notional_usd else None

    level_1 = Level1PortfolioRisk(
        annualized_volatility=RiskMetric(
            value=annual_vol,
            unit_type=RiskUnitType.SIGMA_ANNUALIZED,
            window_days=priors.vol_window_days,
            method="covariance_matrix",
            mark_source=mark_source,
        ),
        horizon_volatility=RiskMetric(
            value=horizon_vol,
            unit_type=RiskUnitType.SIGMA_HORIZON,
            horizon_years=horizon.years,
            window_days=priors.vol_window_days,
            method="covariance_matrix",
            mark_source=mark_source,
            approximation="sigma_annualized_times_sqrt_h",
        ),
        expected_return=RiskMetric(
            value=horizon_return,
            unit_type=RiskUnitType.RETURN_FRACTION,
            horizon_years=horizon.years,
            method="weighted_prior",
            mark_source=mark_source,
        ),
        parametric_var=var_metric,
        parametric_es=es_metric,
        dollar_var=dollar_var,
        dollar_es=dollar_es,
        confidence_low=RiskMetric(
            value=confidence_low,
            unit_type=RiskUnitType.SIGMA_HORIZON,
            horizon_years=horizon.years,
            method="fermi_band",
            mark_source=mark_source,
            approximation="widens_with_fermi_risk_share",
        ),
        confidence_high=RiskMetric(
            value=confidence_high,
            unit_type=RiskUnitType.SIGMA_HORIZON,
            horizon_years=horizon.years,
            method="fermi_band",
            mark_source=mark_source,
            approximation="widens_with_fermi_risk_share",
        ),
    )

    return PortfolioRiskReport(
        portfolio_id=portfolio.portfolio_id,
        horizon_years=horizon.years,
        model_version=priors.model_version,
        input_fingerprint=portfolio_fingerprint(
            portfolio,
            horizon,
            notional_usd=notional_usd,
            assumption_regime=priors.regime,
            model_version=priors.model_version,
        ),
        manifest=RiskManifestMeta(
            vol_window_days=priors.vol_window_days,
            stress_pack_version=priors.stress_pack_version,
            assumption_regime=priors.regime,
        ),
        level_1_portfolio=level_1,
        level_2_contributions=Level2Contributions(
            by_class=by_class, by_duration=by_duration
        ),
        level_3_sensitivities=Level3Sensitivities(
            by_sleeve=evaluate_sensitivities(portfolio.allocations)
        ),
        level_4_stress=evaluate_stress(
            portfolio.allocations,
            notional_usd=notional_usd,
            mark_source=mark_source,
            assumptions=priors,
            stress_filter=stress_filter,
        ),
        liquidity=evaluate_liquidity(portfolio.allocations),
        measurement_summary=MeasurementSummary(
            measurable_weight=measurable_weight,
            fermi_weight=fermi_weight,
            fermi_risk_share=fermi_share,
        ),
        aggregation_note=(
            "Level 1 uses covariance-matrix portfolio sigma with "
            "version-pinned correlations; "
            "Level 2 reports Euler variance shares; Level 4 is linear "
            "sleeve shock replay "
            "(2008/2020/2022) — no cross-gamma or regime correlation shock. "
            "Do not collapse levels without documenting approximation."
        ),
    )
