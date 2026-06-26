"""Compositional HNW generator pipeline — cohort → graph → lots → alts → seal."""

from __future__ import annotations

import hashlib
import random
from datetime import date
from decimal import Decimal

from warehouse.research.risk.models import AssetClass
from warehouse.research.synthetic.cohort import (
    AXIOM_SET_HASH,
    GENERATOR_VERSION,
    sample_sleeve_weights,
    tension_tags_for,
)
from warehouse.research.synthetic.manifest import project_to_asset_portfolio
from warehouse.research.synthetic.models import (
    HouseholdFixture,
    ProvenanceManifest,
    SyntheticAccount,
    SyntheticAltCall,
    SyntheticAltHolding,
    SyntheticLot,
)

_DEFAULT_NAV = Decimal("10000000")
_BASE_DATE = date(2024, 1, 15)


def _stage_hash(stage: str, payload: str) -> str:
    digest = hashlib.sha256(f"{stage}:{payload}".encode()).hexdigest()
    return digest[:12]


def _build_accounts(
    household_id: str, cohort_id: str
) -> list[SyntheticAccount]:
    accounts = [
        SyntheticAccount(
            account_id=f"{household_id}-taxable",
            household_id=household_id,
            name="Taxable",
            account_type="taxable",
        ),
    ]
    if cohort_id in ("uhnw_inherited", "founder_executive"):
        accounts.append(
            SyntheticAccount(
                account_id=f"{household_id}-trust",
                household_id=household_id,
                name="Irrevocable Trust",
                account_type="trust",
            )
        )
    accounts.append(
        SyntheticAccount(
            account_id=f"{household_id}-ira",
            household_id=household_id,
            name="IRA",
            account_type="ira",
        )
    )
    return accounts


def _split_public_lots(
    *,
    household_id: str,
    account_id: str,
    weights: dict[AssetClass, Decimal],
    nav: Decimal,
    seed: int,
    cohort_id: str,
) -> list[SyntheticLot]:
    rng = random.Random(seed + 1)
    lots: list[SyntheticLot] = []
    equity_nav = nav * weights.get(AssetClass.EQUITY, Decimal("0"))
    fi_nav = nav * weights.get(AssetClass.FIXED_INCOME, Decimal("0"))
    cash_nav = nav * weights.get(AssetClass.CASH, Decimal("0"))
    comm_nav = nav * weights.get(AssetClass.COMMODITIES, Decimal("0"))

    if equity_nav > 0:
        if cohort_id in ("founder_executive", "concentrated_stress"):
            concentrate = (
                Decimal("0.40")
                if cohort_id == "concentrated_stress"
                else Decimal("0.25")
            )
            concentrated_nav = equity_nav * concentrate
            diversified_nav = equity_nav - concentrated_nav
            lot_count = rng.randint(3, 5)
            per_lot = concentrated_nav / lot_count
            price = Decimal("180")
            for idx in range(lot_count):
                is_loss = idx == 0
                basis = Decimal("210") if is_loss else Decimal("150")
                lots.append(
                    SyntheticLot(
                        lot_id=f"{household_id}-aapl-{idx}",
                        account_id=account_id,
                        ticker="AAPL",
                        asset_class=AssetClass.EQUITY.value,
                        quantity=per_lot / price,
                        cost_basis_per_share=basis,
                        market_price=price,
                        acquisition_date=date(2020 + idx, 3, 1),
                        is_loss_lot=is_loss,
                        concentration_issuer="AAPL",
                    )
                )
            if diversified_nav > 0:
                vti_price = Decimal("220")
                lots.append(
                    SyntheticLot(
                        lot_id=f"{household_id}-vti-0",
                        account_id=account_id,
                        ticker="VTI",
                        asset_class=AssetClass.EQUITY.value,
                        quantity=diversified_nav / vti_price,
                        cost_basis_per_share=Decimal("200"),
                        market_price=vti_price,
                        acquisition_date=date(2021, 6, 1),
                    )
                )
        else:
            vti_price = Decimal("220")
            lots.append(
                SyntheticLot(
                    lot_id=f"{household_id}-vti-0",
                    account_id=account_id,
                    ticker="VTI",
                    asset_class=AssetClass.EQUITY.value,
                    quantity=equity_nav / vti_price,
                    cost_basis_per_share=Decimal("200"),
                    market_price=vti_price,
                    acquisition_date=date(2021, 6, 1),
                )
            )

    if fi_nav > 0:
        bnd_price = Decimal("75")
        lots.append(
            SyntheticLot(
                lot_id=f"{household_id}-bnd-0",
                account_id=account_id,
                ticker="BND",
                asset_class=AssetClass.FIXED_INCOME.value,
                quantity=fi_nav / bnd_price,
                cost_basis_per_share=Decimal("72"),
                market_price=bnd_price,
                acquisition_date=date(2022, 1, 1),
            )
        )

    if cash_nav > 0:
        lots.append(
            SyntheticLot(
                lot_id=f"{household_id}-cash-0",
                account_id=account_id,
                ticker="CASH",
                asset_class=AssetClass.CASH.value,
                quantity=cash_nav,
                cost_basis_per_share=Decimal("1"),
                market_price=Decimal("1"),
                acquisition_date=_BASE_DATE,
            )
        )

    if comm_nav > 0:
        lots.append(
            SyntheticLot(
                lot_id=f"{household_id}-comm-0",
                account_id=account_id,
                ticker="DBC",
                asset_class=AssetClass.COMMODITIES.value,
                quantity=comm_nav / Decimal("25"),
                cost_basis_per_share=Decimal("24"),
                market_price=Decimal("25"),
                acquisition_date=date(2023, 4, 1),
            )
        )

    return lots


def _build_alts(
    household_id: str,
    entity_id: str,
    weights: dict[AssetClass, Decimal],
    nav: Decimal,
    seed: int,
) -> list[SyntheticAltHolding]:
    alt_weight = weights.get(AssetClass.ALTERNATIVES, Decimal("0"))
    if alt_weight <= 0:
        return []

    rng = random.Random(seed + 2)
    committed = nav * alt_weight * Decimal("1.2")
    called = nav * alt_weight
    unfunded = committed - called
    calls: list[SyntheticAltCall] = []
    remaining = unfunded
    for idx, month_offset in enumerate(range(0, 24, 6)):
        if remaining <= 0 or rng.random() > 0.6:
            continue
        amount = min(remaining, committed * Decimal("0.10"))
        calls.append(
            SyntheticAltCall(
                event_id=f"{household_id}-call-{idx}",
                holding_id=f"{household_id}-pe-1",
                event_date=date(2026, 3 + min(month_offset, 9), 1),
                amount=amount,
            )
        )
        remaining -= amount

    return [
        SyntheticAltHolding(
            holding_id=f"{household_id}-pe-1",
            household_id=household_id,
            entity_id=entity_id,
            name="Synthetic PE Fund I",
            asset_type="private_equity",
            committed_capital=committed,
            called_capital=called,
            unfunded_capital=unfunded,
            current_nav=called,
            last_mark_date=_BASE_DATE,
            scheduled_calls=calls,
        )
    ]


def _sleeve_only_lots(
    household_id: str,
    account_id: str,
    weights: dict[AssetClass, Decimal],
    nav: Decimal,
) -> list[SyntheticLot]:
    """Rung 3 — one representative lot per sleeve (no concentration split)."""
    lots: list[SyntheticLot] = []
    specs = [
        (AssetClass.EQUITY, "VTI", Decimal("220"), Decimal("200")),
        (AssetClass.FIXED_INCOME, "BND", Decimal("75"), Decimal("72")),
        (AssetClass.CASH, "CASH", Decimal("1"), Decimal("1")),
        (AssetClass.COMMODITIES, "DBC", Decimal("25"), Decimal("24")),
    ]
    for asset_class, ticker, price, basis in specs:
        sleeve_nav = nav * weights.get(asset_class, Decimal("0"))
        if sleeve_nav <= 0:
            continue
        lots.append(
            SyntheticLot(
                lot_id=f"{household_id}-{ticker.lower()}-0",
                account_id=account_id,
                ticker=ticker,
                asset_class=asset_class.value,
                quantity=sleeve_nav / price,
                cost_basis_per_share=basis,
                market_price=price,
                acquisition_date=_BASE_DATE,
            )
        )
    return lots


def emit_hnw_fixture(
    *,
    cohort_id: str,
    seed: int,
    rung: int,
    household_id: str | None = None,
    nav_usd: Decimal = _DEFAULT_NAV,
) -> HouseholdFixture:
    """Emit Shape B household fixture at rung 3 (sleeve lots) or 4 (concentration + calls)."""
    if rung not in (3, 4):
        raise ValueError("emit_hnw_fixture supports rung 3 or 4 only")

    hh_id = household_id or f"synthetic-{cohort_id}-s{seed}"
    weights = sample_sleeve_weights(cohort_id, seed)
    accounts = _build_accounts(hh_id, cohort_id)
    taxable = accounts[0].account_id
    entity_id = accounts[-1].account_id

    if rung == 3:
        lots = _sleeve_only_lots(hh_id, taxable, weights, nav_usd)
        alts = _build_alts(hh_id, entity_id, weights, nav_usd, seed)
    else:
        lots = _split_public_lots(
            household_id=hh_id,
            account_id=taxable,
            weights=weights,
            nav=nav_usd,
            seed=seed,
            cohort_id=cohort_id,
        )
        alts = _build_alts(hh_id, entity_id, weights, nav_usd, seed)

    lot_nav = sum(
        (lot.quantity * lot.market_price for lot in lots), Decimal("0")
    )
    alt_nav = sum((alt.current_nav for alt in alts), Decimal("0"))
    total_nav: Decimal = lot_nav + alt_nav

    stage_hashes = [
        _stage_hash("cohort", cohort_id),
        _stage_hash("weights", str(sorted(weights.items()))),
        _stage_hash("lots", str(len(lots))),
        _stage_hash("alts", str(len(alts))),
    ]
    provenance = ProvenanceManifest(
        generator_version=GENERATOR_VERSION,
        seed=seed,
        cohort_id=cohort_id,
        axiom_set_hash=AXIOM_SET_HASH,
        rung=rung,
        tension_tags=tension_tags_for(cohort_id),
        stage_hashes=stage_hashes,
    )
    fixture = HouseholdFixture(
        household_id=hh_id,
        provenance=provenance,
        accounts=accounts,
        lots=lots,
        alternative_holdings=alts,
        total_nav_usd=total_nav,
    )
    shape_a = project_to_asset_portfolio(fixture)
    return fixture.model_copy(update={"asset_portfolio": shape_a})
