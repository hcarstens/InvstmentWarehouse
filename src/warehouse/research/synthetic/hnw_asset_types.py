"""HNW leaf asset taxonomy (A–O) — maps to risk ``AssetClass`` sleeves.

See ``docs/research/hnw_asset_types.md``. Risk API consumes Shape A
(6 sleeves); this catalog drives combinatorial stress via distinct
``AllocationSlot`` metadata per leaf type (``label`` = leaf id).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from warehouse.research.risk.models import AssetClass, MeasurementMode


class HnwAssetType(StrEnum):
    """Fifteen HNW asset categories — stable ids for harness cards."""

    OPERATING_BUSINESS = "operating_business"  # A
    PUBLIC_EQUITY = "public_equity"  # B
    REAL_ESTATE = "real_estate"  # C
    PE_VC = "pe_vc"  # D
    FIXED_INCOME_CASH = "fixed_income_cash"  # E
    RETIREMENT_TAX_ADV = "retirement_tax_adv"  # F
    CONCENTRATED_EMPLOYER = "concentrated_employer"  # G
    PRIVATE_CREDIT = "private_credit"  # H
    HEDGE_FUNDS = "hedge_funds"  # I
    REAL_ASSETS_COMMODITIES = "real_assets_commodities"  # J
    ART_COLLECTIBLES = "art_collectibles"  # K
    CRYPTOCURRENCY = "cryptocurrency"  # L
    INSURANCE_ANNUITIES = "insurance_annuities"  # M
    PHILANTHROPIC = "philanthropic"  # N — outside IPS investable numerator
    PERSONAL_USE = "personal_use"  # O — balance sheet only


# Stable iteration order (A → O).
HNW_ASSET_TYPES: tuple[HnwAssetType, ...] = tuple(HnwAssetType)


@dataclass(frozen=True)
class HnwAssetSpec:
    """Per-leaf defaults when projected into a risk manifest."""

    asset_type: HnwAssetType
    risk_class: AssetClass
    ips_investable: bool
    liquidity_tier: int
    measurement: MeasurementMode
    duration_years: Decimal | None = None
    beta: Decimal | None = None
    category_letter: str = ""


class IpsExcludedError(ValueError):
    """Leaf type(s) are outside the IPS investable numerator."""


_HNW_SPECS: dict[HnwAssetType, HnwAssetSpec] = {
    HnwAssetType.OPERATING_BUSINESS: HnwAssetSpec(
        HnwAssetType.OPERATING_BUSINESS,
        AssetClass.ALTERNATIVES,
        True,
        3,
        MeasurementMode.FERMI,
        duration_years=Decimal("10"),
        category_letter="A",
    ),
    HnwAssetType.PUBLIC_EQUITY: HnwAssetSpec(
        HnwAssetType.PUBLIC_EQUITY,
        AssetClass.EQUITY,
        True,
        1,
        MeasurementMode.MEASURABLE,
        beta=Decimal("1.0"),
        category_letter="B",
    ),
    HnwAssetType.REAL_ESTATE: HnwAssetSpec(
        HnwAssetType.REAL_ESTATE,
        AssetClass.ALTERNATIVES,
        True,
        3,
        MeasurementMode.FERMI,
        duration_years=Decimal("12"),
        category_letter="C",
    ),
    HnwAssetType.PE_VC: HnwAssetSpec(
        HnwAssetType.PE_VC,
        AssetClass.ALTERNATIVES,
        True,
        3,
        MeasurementMode.FERMI,
        duration_years=Decimal("7"),
        category_letter="D",
    ),
    HnwAssetType.FIXED_INCOME_CASH: HnwAssetSpec(
        HnwAssetType.FIXED_INCOME_CASH,
        AssetClass.FIXED_INCOME,
        True,
        1,
        MeasurementMode.MEASURABLE,
        duration_years=Decimal("5.5"),
        category_letter="E",
    ),
    HnwAssetType.RETIREMENT_TAX_ADV: HnwAssetSpec(
        HnwAssetType.RETIREMENT_TAX_ADV,
        AssetClass.EQUITY,
        True,
        2,
        MeasurementMode.MEASURABLE,
        beta=Decimal("0.95"),
        category_letter="F",
    ),
    HnwAssetType.CONCENTRATED_EMPLOYER: HnwAssetSpec(
        HnwAssetType.CONCENTRATED_EMPLOYER,
        AssetClass.EQUITY,
        True,
        1,
        MeasurementMode.MEASURABLE,
        beta=Decimal("1.5"),
        category_letter="G",
    ),
    HnwAssetType.PRIVATE_CREDIT: HnwAssetSpec(
        HnwAssetType.PRIVATE_CREDIT,
        AssetClass.ALTERNATIVES,
        True,
        2,
        MeasurementMode.FERMI,
        duration_years=Decimal("5"),
        category_letter="H",
    ),
    HnwAssetType.HEDGE_FUNDS: HnwAssetSpec(
        HnwAssetType.HEDGE_FUNDS,
        AssetClass.ALTERNATIVES,
        True,
        2,
        MeasurementMode.FERMI,
        duration_years=Decimal("3"),
        category_letter="I",
    ),
    HnwAssetType.REAL_ASSETS_COMMODITIES: HnwAssetSpec(
        HnwAssetType.REAL_ASSETS_COMMODITIES,
        AssetClass.COMMODITIES,
        True,
        2,
        MeasurementMode.FERMI,
        beta=Decimal("0.5"),
        category_letter="J",
    ),
    HnwAssetType.ART_COLLECTIBLES: HnwAssetSpec(
        HnwAssetType.ART_COLLECTIBLES,
        AssetClass.ALTERNATIVES,
        True,
        3,
        MeasurementMode.FERMI,
        duration_years=Decimal("15"),
        category_letter="K",
    ),
    HnwAssetType.CRYPTOCURRENCY: HnwAssetSpec(
        HnwAssetType.CRYPTOCURRENCY,
        AssetClass.ALTERNATIVES,
        True,
        1,
        MeasurementMode.FERMI,
        beta=Decimal("1.2"),
        category_letter="L",
    ),
    HnwAssetType.INSURANCE_ANNUITIES: HnwAssetSpec(
        HnwAssetType.INSURANCE_ANNUITIES,
        AssetClass.FIXED_INCOME,
        True,
        3,
        MeasurementMode.FERMI,
        duration_years=Decimal("15"),
        category_letter="M",
    ),
    HnwAssetType.PHILANTHROPIC: HnwAssetSpec(
        HnwAssetType.PHILANTHROPIC,
        AssetClass.CASH,
        False,
        3,
        MeasurementMode.FERMI,
        category_letter="N",
    ),
    HnwAssetType.PERSONAL_USE: HnwAssetSpec(
        HnwAssetType.PERSONAL_USE,
        AssetClass.COMMODITIES,
        False,
        3,
        MeasurementMode.FERMI,
        category_letter="O",
    ),
}


def hnw_asset_spec(asset_type: HnwAssetType) -> HnwAssetSpec:
    return _HNW_SPECS[asset_type]


def ips_excluded_types(
    types: tuple[HnwAssetType, ...],
) -> tuple[HnwAssetType, ...]:
    return tuple(t for t in types if not hnw_asset_spec(t).ips_investable)
