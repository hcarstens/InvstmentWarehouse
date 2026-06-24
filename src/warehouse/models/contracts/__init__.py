"""Versioned contracts — IPS, mandates, fee schedules, alt subscription docs."""

from pydantic import BaseModel


class Contract(BaseModel):
    contract_id: str
    contract_type: str  # ips | mandate | fee_schedule | alt_subscription
    household_id: str
    version: int
    effective_date: str
    document_uri: str | None = None
