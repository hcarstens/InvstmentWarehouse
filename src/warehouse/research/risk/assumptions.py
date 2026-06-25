"""Proprietary risk/return priors by asset class — version-pinned for replay."""

from __future__ import annotations

from decimal import Decimal

from warehouse.research.risk.models import AssetClass

# Annualized vol and return priors — tune via risk_model_version, not ad hoc per request.
CLASS_ANNUAL_VOL: dict[AssetClass, Decimal] = {
    AssetClass.EQUITY: Decimal("0.160"),
    AssetClass.FIXED_INCOME: Decimal("0.060"),
    AssetClass.COMMODITIES: Decimal("0.200"),
    AssetClass.FX: Decimal("0.080"),
    AssetClass.ALTERNATIVES: Decimal("0.250"),
    AssetClass.CASH: Decimal("0.010"),
}

CLASS_EXPECTED_RETURN: dict[AssetClass, Decimal] = {
    AssetClass.EQUITY: Decimal("0.070"),
    AssetClass.FIXED_INCOME: Decimal("0.040"),
    AssetClass.COMMODITIES: Decimal("0.050"),
    AssetClass.FX: Decimal("0.020"),
    AssetClass.ALTERNATIVES: Decimal("0.090"),
    AssetClass.CASH: Decimal("0.030"),
}

# Fermi estimates carry wider effective vol for confidence bands.
FERMI_VOL_MULTIPLIER = Decimal("1.35")
