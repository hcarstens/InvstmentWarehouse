"""ST6 property-based invariants for risk math (st5f).

Independent oracles (ST2): normal VaR/ES ordering, ρ bounds, wᵀΣw variance,
horizon √t scaling — never values copied from ``parametric_var`` output.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from warehouse.research.risk.assumptions import (
    ES_MULTIPLIERS,
    Z_SCORES,
    RiskAssumptions,
    build_assumptions,
)
from warehouse.research.risk.by_class import build_sleeve_states
from warehouse.research.risk.covariance import (
    SleeveRiskState,
    portfolio_covariance,
)
from warehouse.research.risk.models import (
    AllocationSlot,
    AssetClass,
    MeasurementMode,
)
from warehouse.research.risk.var_es import (
    horizon_scale,
    parametric_es,
    parametric_var,
)

_SUM_TOL = Decimal("0.0001")
_VOL_TOL = Decimal("1e-12")
_ALPHA_CHOICES = (0.95, 0.975)
_ALL_CLASSES = tuple(AssetClass)

# --- independent oracles -----------------------------------------------------


def _alpha_key(alpha: float) -> str:
    return f"{alpha:.3f}".rstrip("0").rstrip(".")


def _oracle_horizon_vol(
    annual_vol: Decimal,
    horizon_years: Decimal,
) -> Decimal:
    return annual_vol * horizon_years.sqrt()


def _oracle_pairwise_rho_bounds(rho: Decimal) -> bool:
    return Decimal("-1") <= rho <= Decimal("1")


def _oracle_wtw_variance(
    weights: list[Decimal],
    vols: list[Decimal],
    classes: list[AssetClass],
    assumptions: RiskAssumptions,
) -> Decimal:
    n = len(weights)
    variance = Decimal("0")
    for i in range(n):
        for j in range(n):
            rho = assumptions.pairwise_correlation(classes[i], classes[j])
            cov_ij = vols[i] * vols[j] * rho
            variance += weights[i] * weights[j] * cov_ij
    return variance


def _oracle_var_le_es(alpha: float) -> bool:
    key = _alpha_key(alpha)
    return Z_SCORES[key] <= ES_MULTIPLIERS[key]


def _oracle_es_exceeds_var(
    annual_vol: Decimal,
    annual_return: Decimal,
    horizon_years: Decimal,
    alpha: float,
    assumptions: RiskAssumptions,
) -> tuple[Decimal, Decimal]:
    """Independent normal-tail ordering: z·σ_h − μ_h ≤ es_mult·σ_h − μ_h."""
    sigma_h = _oracle_horizon_vol(annual_vol, horizon_years)
    mu_h = annual_return * horizon_years
    z = assumptions.z_scores[_alpha_key(alpha)]
    es_mult = assumptions.es_multipliers[_alpha_key(alpha)]
    return z * sigma_h - mu_h, es_mult * sigma_h - mu_h


# --- hypothesis strategies ---------------------------------------------------


@st.composite
def risk_assumptions(draw: st.DrawFn) -> RiskAssumptions:
    default_rho = draw(
        st.decimals(
            min_value=Decimal("-1"),
            max_value=Decimal("1"),
            places=3,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    vols = {
        asset: draw(
            st.decimals(
                min_value=Decimal("1e-8"),
                max_value=Decimal("0.5"),
                places=6,
                allow_nan=False,
                allow_infinity=False,
            )
        )
        for asset in _ALL_CLASSES
    }
    return build_assumptions(
        default_class_correlation=default_rho,
        class_annual_vol=vols,
    )


@st.composite
def allocation_slots(
    draw: st.DrawFn,
    *,
    min_size: int = 2,
    max_size: int = 6,
) -> list[AllocationSlot]:
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    raw = draw(
        st.lists(
            st.decimals(
                min_value=Decimal("0.01"),
                max_value=Decimal("1"),
                places=4,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=n,
            max_size=n,
        )
    )
    total = sum(raw, Decimal("0"))
    classes = draw(
        st.lists(
            st.sampled_from(_ALL_CLASSES),
            min_size=n,
            max_size=n,
        )
    )
    slots: list[AllocationSlot] = []
    for weight_raw, asset_class in zip(raw, classes, strict=True):
        slots.append(
            AllocationSlot(
                asset_class=asset_class,
                weight=weight_raw / total,
                liquidity_tier=1,
                measurement=MeasurementMode.MEASURABLE,
            )
        )
    return slots


@st.composite
def vol_horizon_alpha(
    draw: st.DrawFn,
) -> tuple[Decimal, Decimal, Decimal, float]:
    annual_vol = draw(
        st.decimals(
            min_value=Decimal("1e-8"),
            max_value=Decimal("0.5"),
            places=6,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    annual_return = draw(
        st.decimals(
            min_value=Decimal("-0.2"),
            max_value=Decimal("0.3"),
            places=4,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    horizon = draw(
        st.decimals(
            min_value=Decimal("0.25"),
            max_value=Decimal("10"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    alpha = draw(st.sampled_from(_ALPHA_CHOICES))
    return annual_vol, annual_return, horizon, alpha


def _split_states(
    states: list[SleeveRiskState],
    split_at: int,
) -> tuple[list[SleeveRiskState], list[SleeveRiskState]]:
    return states[:split_at], states[split_at:]


# --- property tests ----------------------------------------------------------


@given(assumptions=risk_assumptions())
def test_pairwise_correlation_within_bounds(
    assumptions: RiskAssumptions,
) -> None:
    for left in _ALL_CLASSES:
        for right in _ALL_CLASSES:
            rho = assumptions.pairwise_correlation(left, right)
            assert _oracle_pairwise_rho_bounds(rho)
            if left == right:
                assert rho == Decimal("1")


@given(params=vol_horizon_alpha(), assumptions=risk_assumptions())
def test_horizon_scale_matches_sqrt_t(
    params: tuple[Decimal, Decimal, Decimal, float],
    assumptions: RiskAssumptions,
) -> None:
    annual_vol, _annual_return, horizon, _alpha = params
    assume(annual_vol >= Decimal("0"))
    scaled = horizon_scale(annual_vol, horizon)
    expected = _oracle_horizon_vol(annual_vol, horizon)
    assert scaled == expected
    assert scaled >= Decimal("0")


@given(params=vol_horizon_alpha(), assumptions=risk_assumptions())
def test_parametric_var_le_es(
    params: tuple[Decimal, Decimal, Decimal, float],
    assumptions: RiskAssumptions,
) -> None:
    annual_vol, annual_return, horizon, alpha = params
    assume(_oracle_var_le_es(alpha))
    var_oracle, es_oracle = _oracle_es_exceeds_var(
        annual_vol,
        annual_return,
        horizon,
        alpha,
        assumptions,
    )
    var_metric = parametric_var(
        annual_vol,
        annual_return,
        horizon,
        alpha,
        assumptions=assumptions,
        mark_source="property_test",
    )
    es_metric = parametric_es(
        annual_vol,
        annual_return,
        horizon,
        alpha,
        assumptions=assumptions,
        mark_source="property_test",
    )
    assert var_metric.value == var_oracle
    assert es_metric.value == es_oracle
    assert var_metric.value <= es_metric.value


@given(slots=allocation_slots(), assumptions=risk_assumptions())
def test_portfolio_volatility_non_negative(
    slots: list[AllocationSlot],
    assumptions: RiskAssumptions,
) -> None:
    states = build_sleeve_states(slots, assumptions)
    result = portfolio_covariance(states, assumptions)
    assert result.portfolio_volatility >= Decimal("0")
    weights = [s.slot.weight for s in states]
    vols = [s.annual_volatility for s in states]
    classes = [s.slot.asset_class for s in states]
    oracle_var = _oracle_wtw_variance(weights, vols, classes, assumptions)
    if oracle_var > Decimal("0"):
        assert result.portfolio_variance == oracle_var
        assert result.portfolio_volatility == oracle_var.sqrt()
    else:
        assert result.portfolio_volatility == Decimal("0")


@given(slots=allocation_slots(min_size=3), assumptions=risk_assumptions())
def test_pct_variance_contributions_sum_to_one(
    slots: list[AllocationSlot],
    assumptions: RiskAssumptions,
) -> None:
    states = build_sleeve_states(slots, assumptions)
    result = portfolio_covariance(states, assumptions)
    assume(result.portfolio_variance > Decimal("0"))
    total = sum(result.pct_variance_contributions, Decimal("0"))
    assert abs(total - Decimal("1")) <= _SUM_TOL


@given(
    slots=allocation_slots(min_size=3, max_size=6),
    assumptions=risk_assumptions(),
    split_at=st.integers(min_value=1, max_value=5),
)
def test_volatility_subadditive_on_disjoint_sleeves(
    slots: list[AllocationSlot],
    assumptions: RiskAssumptions,
    split_at: int,
) -> None:
    states = build_sleeve_states(slots, assumptions)
    n = len(states)
    assume(n >= 3)
    k = min(split_at, n - 1)
    assume(k >= 1)
    g1, g2 = _split_states(states, k)
    assume(len(g1) >= 1 and len(g2) >= 1)

    merged = portfolio_covariance(states, assumptions)
    vol_g1 = portfolio_covariance(g1, assumptions).portfolio_volatility
    vol_g2 = portfolio_covariance(g2, assumptions).portfolio_volatility

    assert merged.portfolio_volatility <= vol_g1 + vol_g2 + _VOL_TOL


# --- boundary hunts (§4.2 gaps) --------------------------------------------


@pytest.fixture
def assumptions_for_base() -> RiskAssumptions:
    return build_assumptions()


def test_empty_states_zero_variance(
    assumptions_for_base: RiskAssumptions,
) -> None:
    result = portfolio_covariance([], assumptions_for_base)
    assert result.portfolio_variance == Decimal("0")
    assert result.portfolio_volatility == Decimal("0")
    assert result.pct_variance_contributions == []
    assert result.marginal_variance == []


def test_single_asset_vol_equals_sleeve_vol(
    assumptions_for_base: RiskAssumptions,
) -> None:
    slot = AllocationSlot(
        asset_class=AssetClass.EQUITY,
        weight=Decimal("1"),
        liquidity_tier=1,
        measurement=MeasurementMode.MEASURABLE,
    )
    states = build_sleeve_states([slot], assumptions_for_base)
    sleeve_vol = states[0].annual_volatility
    result = portfolio_covariance(states, assumptions_for_base)
    assert result.portfolio_volatility == sleeve_vol
    oracle_var = sleeve_vol * sleeve_vol
    assert result.portfolio_variance == oracle_var


def test_single_asset_var_es_consistent(
    assumptions_for_base: RiskAssumptions,
) -> None:
    slot = AllocationSlot(
        asset_class=AssetClass.FIXED_INCOME,
        weight=Decimal("1"),
        liquidity_tier=1,
        measurement=MeasurementMode.MEASURABLE,
    )
    states = build_sleeve_states([slot], assumptions_for_base)
    annual_vol = portfolio_covariance(
        states, assumptions_for_base
    ).portfolio_volatility
    horizon = Decimal("1")
    mu = assumptions_for_base.class_expected_return[AssetClass.FIXED_INCOME]
    alpha = assumptions_for_base.var_alpha
    var_oracle, es_oracle = _oracle_es_exceeds_var(
        annual_vol,
        mu,
        horizon,
        alpha,
        assumptions_for_base,
    )
    var_m = parametric_var(
        annual_vol,
        mu,
        horizon,
        alpha,
        assumptions=assumptions_for_base,
        mark_source="boundary",
    )
    es_m = parametric_es(
        annual_vol,
        mu,
        horizon,
        alpha,
        assumptions=assumptions_for_base,
        mark_source="boundary",
    )
    assert var_m.value == var_oracle
    assert es_m.value == es_oracle
    assert var_m.value <= es_m.value


def test_near_zero_vol_degenerate_covariance(
    assumptions_for_base: RiskAssumptions,
) -> None:
    assumptions = build_assumptions(
        class_annual_vol={
            AssetClass.EQUITY: Decimal("0"),
            **{
                c: assumptions_for_base.class_annual_vol[c]
                for c in _ALL_CLASSES
                if c != AssetClass.EQUITY
            },
        },
    )
    slot = AllocationSlot(
        asset_class=AssetClass.EQUITY,
        weight=Decimal("1"),
        liquidity_tier=1,
        measurement=MeasurementMode.MEASURABLE,
    )
    states = build_sleeve_states([slot], assumptions)
    result = portfolio_covariance(states, assumptions)
    assert result.portfolio_variance == Decimal("0")
    assert result.portfolio_volatility == Decimal("0")


@given(
    rho=st.decimals(
        min_value=Decimal("-1"),
        max_value=Decimal("1"),
        places=3,
        allow_nan=False,
        allow_infinity=False,
    ),
)
def test_correlation_at_bounds_pairwise(rho: Decimal) -> None:
    assumptions = build_assumptions(
        default_class_correlation=rho,
        class_correlations={},
    )
    for left in _ALL_CLASSES:
        for right in _ALL_CLASSES:
            got = assumptions.pairwise_correlation(left, right)
            assert _oracle_pairwise_rho_bounds(got)
            if left == right:
                assert got == Decimal("1")
            else:
                assert got == rho
