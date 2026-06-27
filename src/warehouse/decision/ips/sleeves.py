"""IPS sleeve taxonomy — six-sleeve rollup aligned with risk ``AssetClass``.

Security master uses finer types (e.g. ``ETF``); IPS and drift monitoring roll up
to these sleeves for policy targets.
"""

from __future__ import annotations

from enum import StrEnum

from warehouse.data.security_master import AssetClass as SecurityAssetClass


class IpsSleeve(StrEnum):
    """Strategic allocation sleeves for IPS min/max/target weights."""

    EQUITY = "equity"
    FIXED_INCOME = "fixed_income"
    COMMODITIES = "commodities"
    FX = "fx"
    ALTERNATIVES = "alternatives"
    CASH = "cash"


_LEGACY_SLEEVE_ALIASES: dict[str, IpsSleeve] = {
    "etf": IpsSleeve.EQUITY,
}


def parse_ips_sleeve(value: str) -> IpsSleeve:
    """Load sleeve from persisted JSON; map legacy demo values."""
    if value in _LEGACY_SLEEVE_ALIASES:
        return _LEGACY_SLEEVE_ALIASES[value]
    return IpsSleeve(value)


def rollup_security_to_ips_sleeve(
    asset_class: SecurityAssetClass,
    *,
    ticker: str | None = None,
    wash_sale_substitute_group: str | None = None,
) -> IpsSleeve:
    """Map security-master class to IPS sleeve for drift and optimizer."""
    if asset_class == SecurityAssetClass.EQUITY:
        return IpsSleeve.EQUITY
    if asset_class == SecurityAssetClass.FIXED_INCOME:
        return IpsSleeve.FIXED_INCOME
    if asset_class == SecurityAssetClass.CASH:
        return IpsSleeve.CASH
    if asset_class == SecurityAssetClass.ALTERNATIVE:
        return IpsSleeve.ALTERNATIVES
    if asset_class == SecurityAssetClass.ETF:
        if ticker == "BND":
            return IpsSleeve.FIXED_INCOME
        if wash_sale_substitute_group and "bond" in wash_sale_substitute_group:
            return IpsSleeve.FIXED_INCOME
        return IpsSleeve.EQUITY
    raise ValueError(
        f"unsupported security asset class for IPS rollup: {asset_class}"
    )
