"""IPS ↔ fixture validation — SDG1 gate before sealing synthetic households."""

from __future__ import annotations

from decimal import Decimal

from warehouse.decision.ips import InvestmentPolicyStatement
from warehouse.decision.ips.sleeves import IpsSleeve
from warehouse.research.risk.models import AssetClass, AssetPortfolio
from warehouse.research.synthetic.manifest import project_to_asset_portfolio
from warehouse.research.synthetic.models import (
    HouseholdFixture,
    IpsValidationResult,
    SyntheticLot,
)

_SLEEVE_PROXY_TICKERS = frozenset({"VTI", "BND", "CASH", "DBC", "SYNPE"})


class IpsValidationError(ValueError):
    """Raised when ``validate_ips`` fails for a co-generated household pair."""

    def __init__(self, result: IpsValidationResult) -> None:
        self.result = result
        detail = ", ".join(result.binding_constraints or result.warnings)
        super().__init__(f"IPS validation failed: {detail or 'unknown'}")


def _lot_liquidity_tier(lot: SyntheticLot) -> int:
    asset_class = AssetClass(lot.asset_class)
    if asset_class == AssetClass.ALTERNATIVES:
        return 3
    if asset_class in (AssetClass.COMMODITIES, AssetClass.FX):
        return 2
    return 1


def _shape_a_sleeve_weights(
    portfolio: AssetPortfolio,
) -> dict[IpsSleeve, Decimal]:
    return {
        IpsSleeve(slot.asset_class.value): slot.weight
        for slot in portfolio.allocations
    }


def _issuer_weights(fixture: HouseholdFixture) -> dict[str, Decimal]:
    nav = fixture.total_nav_usd
    if nav <= 0:
        return {}
    by_issuer: dict[str, Decimal] = {}
    for lot in fixture.lots:
        if lot.concentration_issuer:
            issuer = lot.concentration_issuer
        elif lot.ticker in _SLEEVE_PROXY_TICKERS:
            continue
        else:
            issuer = lot.ticker
        mv = lot.quantity * lot.market_price
        by_issuer[issuer] = by_issuer.get(issuer, Decimal("0")) + mv
    return {issuer: weight / nav for issuer, weight in by_issuer.items()}


def _liquid_tier_share(fixture: HouseholdFixture) -> Decimal:
    unfunded = sum(
        (alt.unfunded_capital for alt in fixture.alternative_holdings),
        Decimal("0"),
    )
    denominator = fixture.total_nav_usd + unfunded
    if denominator <= 0:
        return Decimal("0")
    liquid_mv = Decimal("0")
    for lot in fixture.lots:
        if _lot_liquidity_tier(lot) <= 2:
            liquid_mv += lot.quantity * lot.market_price
    return liquid_mv / denominator


def _sleeve_binding_constraints(
    weights: dict[IpsSleeve, Decimal],
    ips: InvestmentPolicyStatement,
) -> list[str]:
    bindings: list[str] = []
    for target in ips.allocation_targets:
        current = weights.get(target.asset_class, Decimal("0"))
        if current < target.min_weight:
            bindings.append(
                f"sleeve_below_min:{target.asset_class.value}="
                f"{current:.4f}<{target.min_weight:.4f}"
            )
        if current > target.max_weight:
            bindings.append(
                f"sleeve_above_max:{target.asset_class.value}="
                f"{current:.4f}>{target.max_weight:.4f}"
            )
    return bindings


def _concentration_binding_constraints(
    fixture: HouseholdFixture,
    ips: InvestmentPolicyStatement,
) -> list[str]:
    cap = ips.concentration_limit_pct
    bindings: list[str] = []
    for issuer, weight in _issuer_weights(fixture).items():
        if weight > cap:
            bindings.append(f"concentration:{issuer}={weight:.4f}>{cap:.4f}")
    return bindings


def _liquidity_binding_constraints(
    fixture: HouseholdFixture,
    ips: InvestmentPolicyStatement,
) -> list[str]:
    floor = ips.liquidity_tier_min_pct
    if floor is None:
        return []
    share = _liquid_tier_share(fixture)
    if share < floor:
        return [f"liquidity_tier_1_2={share:.4f}<{floor:.4f}"]
    return []


def validate_ips(
    fixture: HouseholdFixture,
    ips: InvestmentPolicyStatement,
) -> IpsValidationResult:
    """Check Shape A sleeves, concentration, and liquidity vs IPS policy."""
    warnings: list[str] = []
    if ips.household_id != fixture.household_id:
        return IpsValidationResult(
            ok=False,
            warnings=[f"household_id mismatch: {ips.household_id}"],
        )

    portfolio = fixture.asset_portfolio
    if portfolio is None:
        portfolio = project_to_asset_portfolio(fixture)

    weights = _shape_a_sleeve_weights(portfolio)
    binding_constraints: list[str] = []
    binding_constraints.extend(_sleeve_binding_constraints(weights, ips))
    binding_constraints.extend(
        _concentration_binding_constraints(fixture, ips)
    )
    binding_constraints.extend(_liquidity_binding_constraints(fixture, ips))

    cohort_id = fixture.provenance.cohort_id
    if cohort_id == "concentrated_stress":
        if not binding_constraints:
            return IpsValidationResult(
                ok=False,
                binding_constraints=binding_constraints,
                warnings=["concentrated_stress requires binding constraints"],
            )
        return IpsValidationResult(
            ok=True,
            binding_constraints=binding_constraints,
            warnings=warnings,
        )

    if binding_constraints:
        return IpsValidationResult(
            ok=False,
            binding_constraints=binding_constraints,
            warnings=warnings,
        )
    return IpsValidationResult(
        ok=True,
        binding_constraints=binding_constraints,
        warnings=warnings,
    )
