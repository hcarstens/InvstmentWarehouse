"""Black–Litterman posterior μ — pure-Python linalg (pv1).

The canonical blend

    μ_BL = [(τΣ)⁻¹ + PᵀΩ⁻¹P]⁻¹ · [(τΣ)⁻¹ π + PᵀΩ⁻¹ Q]

over the **6-sleeve class block** (small, well-conditioned). No external
solver (CLAUDE.md Phases 0–4): a Gauss–Jordan inverse with partial pivoting
that **raises** ``SingularCovarianceError`` on a singular Σ — never a silent
pseudo-inverse (errors bubble).

View convention (judgment leg — Persona ¬RM4 / ¬Opt3): each ``View`` is an
**absolute** view on one sleeve, ``Q_k = π[sleeve] + expected_excess`` (a tilt
vs the prior). The view uncertainty is

    Ω_kk = τ · (P Σ Pᵀ)_kk · (1 − c) / c

so confidence ``c → 1`` drives Ω → 0 (posterior → view) and ``c → 0`` drives
Ω → ∞ (posterior → prior). Confidence is clamped to ``(0, 1)`` to keep Ω finite
and positive; a single confident view still cannot license concentration —
the QP box caps remain the diversification defense (PO6). The zero-view case
short-circuits to the prior **byte-identical** (BL with no views *is* the
prior), so no float dust perturbs the identity.
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal

from warehouse.decision.beliefs.models import (
    PosteriorBelief,
    SingularCovarianceError,
    View,
    ViewMappingError,
)
from warehouse.decision.ips.sleeves import IpsSleeve

# Quantum for posterior μ — fine enough to preserve directional/monotone
# ordering; the zero-view path bypasses quantization entirely (byte-identical).
_MU_QUANTUM = Decimal("0.00000001")

# Confidence clamp: keep Ω strictly positive and finite (c=1 → Ω=0 → singular;
# c=0 → Ω=∞ → view dropped). Pinned to belief_config_version via the caller.
_CONF_FLOOR = 1e-6
_CONF_CEIL = 1.0 - 1e-6

# Pivot magnitude below which a matrix is treated as singular (raise, no pinv).
_SINGULAR_EPS = 1e-12


def _invert(matrix: list[list[float]]) -> list[list[float]]:
    """Gauss–Jordan inverse with partial pivoting; raise if singular."""
    n = len(matrix)
    # Augment [A | I].
    aug = [
        [float(matrix[i][j]) for j in range(n)]
        + [1.0 if i == k else 0.0 for k in range(n)]
        for i in range(n)
    ]
    for col in range(n):
        # Partial pivot — largest magnitude at/below the diagonal.
        pivot_row = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot_row][col]) < _SINGULAR_EPS:
            raise SingularCovarianceError(
                "covariance/precision matrix is singular "
                f"(pivot ~0 at column {col}); the sleeve block is "
                "degenerate — no silent pseudo-inverse"
            )
        aug[col], aug[pivot_row] = aug[pivot_row], aug[col]
        pivot = aug[col][col]
        aug[col] = [x / pivot for x in aug[col]]
        for r in range(n):
            if r == col:
                continue
            factor = aug[r][col]
            if factor == 0.0:
                continue
            aug[r] = [aug[r][j] - factor * aug[col][j] for j in range(2 * n)]
    return [row[n:] for row in aug]


def _matvec(a: list[list[float]], v: list[float]) -> list[float]:
    return [sum(a[i][k] * v[k] for k in range(len(v))) for i in range(len(a))]


def _matadd(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [
        [a[i][j] + b[i][j] for j in range(len(a[0]))] for i in range(len(a))
    ]


def black_litterman(
    prior_mu: dict[IpsSleeve, Decimal],
    sigma: list[list[float]],
    views: tuple[View, ...],
    *,
    tau: Decimal,
    settings: object | None = None,
) -> PosteriorBelief:
    """Blend a prior μ with confidence-weighted views into a posterior μ.

    ``prior_mu`` key order defines the sleeve universe; ``sigma`` rows/cols
    follow that same order (built via the po0 §A spec). ``views`` reference
    sleeves that must be in the universe (else ``ViewMappingError``). Raises
    ``SingularCovarianceError`` on a singular Σ — no silent pseudo-inverse.

    Zero views → the posterior μ **is** the prior μ, byte-identical (BL with no
    views returns the prior); the float linalg is skipped so the identity holds
    exactly (the PASS falsifier).
    """
    del settings  # reserved: pinned Ω convention travels via the caller's τ.
    universe = list(prior_mu.keys())

    # Zero-view identity — return the prior untouched (byte-identical).
    if not views:
        return PosteriorBelief(mu=dict(prior_mu), tau=tau)

    n = len(universe)
    index = {sleeve: i for i, sleeve in enumerate(universe)}
    tau_f = float(tau)
    pi = [float(prior_mu[s]) for s in universe]

    # τΣ and its inverse (raises on singular Σ).
    tau_sigma = [[tau_f * sigma[i][j] for j in range(n)] for i in range(n)]
    tau_sigma_inv = _invert(tau_sigma)

    # Build P (K×N one-hot picks), Q (absolute view targets), Ω⁻¹ (diagonal).
    k = len(views)
    p_mat = [[0.0] * n for _ in range(k)]
    q_vec = [0.0] * k
    omega_inv_diag = [0.0] * k
    for row, view in enumerate(views):
        if view.sleeve not in index:
            raise ViewMappingError(
                f"view on sleeve {view.sleeve!r} is outside the book's "
                f"sleeve universe {[s.value for s in universe]}"
            )
        col = index[view.sleeve]
        p_mat[row][col] = 1.0
        # Absolute view = prior + tilt (expected_excess is vs the prior).
        q_vec[row] = pi[col] + float(view.expected_excess)
        conf = min(max(float(view.confidence), _CONF_FLOOR), _CONF_CEIL)
        # View variance baseline = τ·(PΣPᵀ)_kk = τ·Σ[col,col] for a one-hot.
        view_var = tau_f * sigma[col][col]
        omega = view_var * (1.0 - conf) / conf
        if omega < _SINGULAR_EPS:
            omega = _SINGULAR_EPS
        omega_inv_diag[row] = 1.0 / omega

    # PᵀΩ⁻¹P (N×N) and PᵀΩ⁻¹Q (N) — Ω⁻¹ diagonal, so accumulate directly.
    pt_oinv_p = [[0.0] * n for _ in range(n)]
    pt_oinv_q = [0.0] * n
    for row in range(k):
        col = next(c for c in range(n) if p_mat[row][c] != 0.0)
        w = omega_inv_diag[row]
        pt_oinv_p[col][col] += w
        pt_oinv_q[col] += w * q_vec[row]

    # Posterior precision M = (τΣ)⁻¹ + PᵀΩ⁻¹P; RHS = (τΣ)⁻¹π + PᵀΩ⁻¹Q.
    precision = _matadd(tau_sigma_inv, pt_oinv_p)
    rhs = [_matvec(tau_sigma_inv, pi)[i] + pt_oinv_q[i] for i in range(n)]
    posterior = _matvec(_invert(precision), rhs)

    mu = {
        universe[i]: Decimal(str(posterior[i])).quantize(
            _MU_QUANTUM, rounding=ROUND_HALF_EVEN
        )
        for i in range(n)
    }
    return PosteriorBelief(mu=mu, tau=tau)
