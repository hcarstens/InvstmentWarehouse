"""Black–Litterman blend correctness (pv1).

Falsifiers: zero-view identity (byte-identical prior), directional view,
confidence-monotonicity, singular-Σ raise, view-outside-universe raise, and a
hand-checkable "posterior lies between prior and view target" bound.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from warehouse.decision.beliefs import (
    SingularCovarianceError,
    View,
    ViewMappingError,
    ViewSource,
    _build_sigma,
    black_litterman,
)
from warehouse.decision.ips.sleeves import IpsSleeve as S
from warehouse.decision.optimizer.rebalance import risk_class_for
from warehouse.research.risk.scenarios import assumptions_for

_TAU = Decimal("0.05")


def _prior_and_sigma(
    sleeves: list[S],
) -> tuple[dict[S, Decimal], list[list[float]]]:
    priors = assumptions_for("base")
    prior_mu = {
        s: priors.class_expected_return[risk_class_for(s)] for s in sleeves
    }
    return prior_mu, _build_sigma(sleeves, priors)


def _view(sleeve: S, excess: str, conf: str) -> View:
    return View(
        sleeve=sleeve,
        expected_excess=Decimal(excess),
        confidence=Decimal(conf),
        source=ViewSource.MANUAL,
        rationale="test",
    )


def test_zero_view_identity_byte_identical() -> None:
    sleeves = [S.EQUITY, S.FIXED_INCOME, S.COMMODITIES]
    prior_mu, sigma = _prior_and_sigma(sleeves)
    post = black_litterman(prior_mu, sigma, (), tau=_TAU)
    # Byte-identical — the exact prior Decimals, no float round-trip.
    assert post.mu == prior_mu
    for s in sleeves:
        assert post.mu[s] == prior_mu[s]
    assert post.method == "black_litterman"
    assert post.tau == _TAU


def test_positive_view_raises_that_sleeves_posterior_mu() -> None:
    sleeves = [S.EQUITY, S.FIXED_INCOME, S.COMMODITIES]
    prior_mu, sigma = _prior_and_sigma(sleeves)
    post = black_litterman(
        prior_mu, sigma, (_view(S.EQUITY, "0.05", "0.5"),), tau=_TAU
    )
    assert post.mu[S.EQUITY] > prior_mu[S.EQUITY]


def test_negative_view_lowers_that_sleeves_posterior_mu() -> None:
    sleeves = [S.EQUITY, S.FIXED_INCOME]
    prior_mu, sigma = _prior_and_sigma(sleeves)
    post = black_litterman(
        prior_mu, sigma, (_view(S.EQUITY, "-0.05", "0.5"),), tau=_TAU
    )
    assert post.mu[S.EQUITY] < prior_mu[S.EQUITY]


def test_confidence_monotone_moves_toward_view() -> None:
    sleeves = [S.EQUITY, S.FIXED_INCOME, S.COMMODITIES]
    prior_mu, sigma = _prior_and_sigma(sleeves)
    lo = black_litterman(
        prior_mu, sigma, (_view(S.EQUITY, "0.05", "0.2"),), tau=_TAU
    ).mu[S.EQUITY]
    hi = black_litterman(
        prior_mu, sigma, (_view(S.EQUITY, "0.05", "0.9"),), tau=_TAU
    ).mu[S.EQUITY]
    # Higher confidence → posterior further from prior, toward the view.
    assert prior_mu[S.EQUITY] < lo < hi


def test_posterior_between_prior_and_view_target() -> None:
    # Hand-checkable bound: an absolute view Q = prior + excess; the posterior
    # for the viewed sleeve must sit strictly between prior and Q.
    sleeves = [S.EQUITY, S.FIXED_INCOME]
    prior_mu, sigma = _prior_and_sigma(sleeves)
    excess = Decimal("0.04")
    post = black_litterman(
        prior_mu, sigma, (_view(S.EQUITY, "0.04", "0.5"),), tau=_TAU
    )
    q = prior_mu[S.EQUITY] + excess
    assert prior_mu[S.EQUITY] < post.mu[S.EQUITY] < q


def test_singular_sigma_raises_no_silent_pinv() -> None:
    prior_mu = {S.EQUITY: Decimal("0.07"), S.FIXED_INCOME: Decimal("0.04")}
    singular = [[0.0, 0.0], [0.0, 0.0]]  # τΣ is singular
    with pytest.raises(SingularCovarianceError):
        black_litterman(
            prior_mu, singular, (_view(S.EQUITY, "0.05", "0.5"),), tau=_TAU
        )


def test_view_outside_universe_raises() -> None:
    prior_mu, sigma = _prior_and_sigma([S.EQUITY])
    with pytest.raises(ViewMappingError):
        black_litterman(
            prior_mu, sigma, (_view(S.FIXED_INCOME, "0.05", "0.5"),), tau=_TAU
        )
