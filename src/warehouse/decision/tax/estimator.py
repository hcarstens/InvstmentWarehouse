"""Tax estimator seam for the after-tax μ overlay (po1-tax, §14 Addendum C).

The optimizer's after-tax μ overlay is gated on a tax engine that does not
exist. Rather than block the whole non-tax pipeline (po2 stress, execution,
reporting) on it, po1-tax splits into a **seam now** + **estimates later**
against this swappable ``TaxEstimator``. The default ``ZeroTaxEstimator``
returns ``$0`` drag, so the overlay is an **identity** (after-tax μ ≡ pre-tax
μ): the seam is structurally live but numerically zero.

**Honesty rule (do not fake — §2):** under the ``$0`` seam honesty matrix #5
(after-tax effective μ) stays ``not_computed``. A trivially-zero overlay
claiming "after-tax" *is* the "pre-tax MV on an after-tax mandate" failure
mode. #5 flips to ``computed`` only when a non-trivial estimator
(``QuantileTaxEstimator``, then ``LLMTaxEstimator``) drops in behind this same
interface and the drag actually moves w*.

Granularity is **per-sleeve** (finer than the portfolio-level
``evaluate_tax_scenario``) so the seam is not reshaped when real estimates land
(§C.3).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol, runtime_checkable

from warehouse.config import Settings
from warehouse.decision.ips.sleeves import IpsSleeve


@runtime_checkable
class TaxEstimator(Protocol):
    """Per-sleeve after-tax μ drag (subtracted from the ex-ante class μ).

    ``is_zero`` marks an identity overlay: when ``True`` the optimizer skips
    the overlay entirely (w* byte-identical to the pre-overlay path) and keeps
    honesty matrix #5 ``not_computed``. A real estimator sets it ``False``.
    """

    is_zero: bool

    def sleeve_mu_drag(
        self,
        universe: list[IpsSleeve],
        *,
        settings: Settings | None = None,
    ) -> dict[IpsSleeve, Decimal]:
        """After-tax μ adjustment per sleeve, subtracted from ex-ante μ."""
        ...


class ZeroTaxEstimator:
    """Identity overlay — ``$0`` drag on every sleeve (the seam default).

    Keeps honesty matrix #5 ``not_computed``: the overlay is structurally
    present but does nothing. Swapped for ``QuantileTaxEstimator`` /
    ``LLMTaxEstimator`` later (§14 Addendum C ladder).
    """

    is_zero: bool = True

    def sleeve_mu_drag(
        self,
        universe: list[IpsSleeve],
        *,
        settings: Settings | None = None,
    ) -> dict[IpsSleeve, Decimal]:
        del settings  # reserved for threshold-aware estimators
        return {sleeve: Decimal("0") for sleeve in universe}
