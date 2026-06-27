"""Position → IPS sleeve rollup for drift and optimizer."""

from __future__ import annotations

from warehouse.data.ledger.views import LotPositionView
from warehouse.decision.ips.sleeves import (
    IpsSleeve,
    rollup_security_to_ips_sleeve,
)


def ips_sleeve_for_position(pos: LotPositionView) -> IpsSleeve:
    return rollup_security_to_ips_sleeve(
        pos.security_asset_class,
        ticker=pos.ticker,
        wash_sale_substitute_group=pos.wash_sale_substitute_group,
    )
