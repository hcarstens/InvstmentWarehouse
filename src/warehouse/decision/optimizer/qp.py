"""Pure-Python constrained mean-variance QP solver (po0 §A.2).

Maximizes ``f(w) = wᵀμ − (λ/2)·wᵀΣw`` subject to ``1ᵀw = 1`` and
``w_min ≤ w ≤ w_max`` by **projected-gradient ascent**: each iterate is
projected onto ``{w : 1ᵀw = 1, w_min ≤ w ≤ w_max}`` via a closed-form
**capped-simplex / continuous quadratic-knapsack projection**
(Held–Wolfe–Crowder / Pardalos–Kovoor — the bounded-box generalization of the
unit-simplex projection; Michelot 1986 covers only the ``w ≥ 0`` case).

No external solver (CLAUDE.md Phases 0–4). Float64 throughout; the caller
quantizes to ``Decimal`` and re-asserts the budget (§A.2). A feasibility guard
runs **before** the solve and raises — never a silent clip (§A.3).
"""

from __future__ import annotations

from warehouse.decision.optimizer.models import OptimizerInfeasibleError

# Slack on the box∩simplex feasibility test — floating dust, not policy.
_FEASIBILITY_SLACK = 1e-9


def project_capped_simplex(
    v: list[float],
    w_min: list[float],
    w_max: list[float],
    *,
    total: float = 1.0,
    iters: int = 200,
) -> list[float]:
    """Public alias — Euclidean projection onto ``{Σw=total, lo≤w≤hi}``.

    po1 reuses the solver's box∩simplex projection to keep the budget-scaled
    convex step feasible when ``w_current`` itself breaches the IPS box (the
    projection is the identity on an already-feasible point).
    """
    return _project_capped_simplex(v, w_min, w_max, total=total, iters=iters)


def _project_capped_simplex(
    v: list[float],
    w_min: list[float],
    w_max: list[float],
    *,
    total: float = 1.0,
    iters: int = 200,
) -> list[float]:
    """Euclidean projection of ``v`` onto ``{w : Σw = total, lo ≤ w ≤ hi}``.

    Solves the continuous quadratic-knapsack dual by bisection on a single
    multiplier ``τ``: ``w_i(τ) = clip(v_i − τ, lo_i, hi_i)``. ``Σ w_i(τ)`` is
    monotone non-increasing in ``τ``, so a unique root exists whenever
    ``Σ lo ≤ total ≤ Σ hi`` (guaranteed by the feasibility guard).
    """
    n = len(v)

    def _summed(tau: float) -> tuple[list[float], float]:
        w = [min(max(v[i] - tau, w_min[i]), w_max[i]) for i in range(n)]
        return w, sum(w)

    # Bracket τ: at lo_tau every w hits its cap (max sum), at hi_tau its
    # floor (min sum). Generous bounds — bisection tightens to tol.
    lo_tau = min(v[i] - w_max[i] for i in range(n))
    hi_tau = max(v[i] - w_min[i] for i in range(n))
    w = [min(max(v[i], w_min[i]), w_max[i]) for i in range(n)]
    for _ in range(iters):
        tau = 0.5 * (lo_tau + hi_tau)
        w, s = _summed(tau)
        if abs(s - total) <= 1e-12:
            break
        if s > total:  # sum too high → raise τ to shrink it
            lo_tau = tau
        else:
            hi_tau = tau
    return w


def _spectral_bound(sigma: list[list[float]]) -> float:
    """Gershgorin row-sum upper bound on ρ(Σ) — cheap Lipschitz constant."""
    if not sigma:
        return 0.0
    return max(sum(abs(x) for x in row) for row in sigma)


def solve_qp(
    mu: list[float],
    sigma: list[list[float]],
    w_min: list[float],
    w_max: list[float],
    *,
    lam: float,
    tol: float,
    max_iters: int,
) -> list[float]:
    """Constrained MV ascent → target weights (float64).

    Raises ``OptimizerInfeasibleError`` if the box ∩ simplex is empty
    (``Σ w_min > 1`` or ``Σ w_max < 1``) — checked before the solve.
    """
    n = len(mu)
    if n == 0:
        raise OptimizerInfeasibleError(
            "empty sleeve universe — nothing to solve"
        )
    if not (len(sigma) == n and len(w_min) == n and len(w_max) == n):
        raise ValueError("solve_qp inputs disagree on dimension n")

    sum_min = sum(w_min)
    sum_max = sum(w_max)
    if sum_min > 1.0 + _FEASIBILITY_SLACK:
        raise OptimizerInfeasibleError(
            f"infeasible IPS bounds: Σ w_min = {sum_min:.6f} > 1 "
            "(box ∩ simplex empty); not silently clipped"
        )
    if sum_max < 1.0 - _FEASIBILITY_SLACK:
        raise OptimizerInfeasibleError(
            f"infeasible IPS bounds: Σ w_max = {sum_max:.6f} < 1 "
            "(box ∩ simplex empty); not silently clipped"
        )

    # Step size 1/L with L = λ·ρ(Σ). When L≈0 (λ=0 or Σ=0) the objective is
    # linear; a unit step still ascends toward the feasible corner.
    lipschitz = lam * _spectral_bound(sigma)
    step = 1.0 / lipschitz if lipschitz > 1e-12 else 1.0

    # Start from the projection of an interior guess (uniform mass).
    w = _project_capped_simplex([1.0 / n] * n, w_min, w_max)
    for _ in range(max_iters):
        # ∇f(w) = μ − λ·Σw (build Σ once upstream; never inside this loop).
        grad = [
            mu[i] - lam * sum(sigma[i][j] * w[j] for j in range(n))
            for i in range(n)
        ]
        candidate = [w[i] + step * grad[i] for i in range(n)]
        w_next = _project_capped_simplex(candidate, w_min, w_max)
        if max(abs(w_next[i] - w[i]) for i in range(n)) < tol:
            w = w_next
            break
        w = w_next
    return w
