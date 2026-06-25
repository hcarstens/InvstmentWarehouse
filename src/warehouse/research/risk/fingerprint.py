"""Input fingerprinting — replay metadata without storing proprietary allocations."""

from __future__ import annotations

import hashlib
import json

from warehouse.research.risk.models import AssetPortfolio, RiskHorizon


def portfolio_fingerprint(portfolio: AssetPortfolio, horizon: RiskHorizon) -> str:
    payload = {
        "portfolio_id": portfolio.portfolio_id,
        "horizon_years": str(horizon.years),
        "allocations": [
            {
                "asset_class": s.asset_class.value,
                "weight": str(s.weight),
                "duration_years": str(s.duration_years) if s.duration_years is not None else None,
                "liquidity_tier": s.liquidity_tier,
                "measurement": s.measurement.value,
            }
            for s in sorted(portfolio.allocations, key=lambda x: x.asset_class.value)
        ],
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return digest[:16]
