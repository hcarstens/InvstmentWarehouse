"""Simulation job records — snapshot, config hash, projected tax ledger."""

from pydantic import BaseModel


class SimulationJob(BaseModel):
    job_id: str
    household_id: str
    input_snapshot_id: str
    config_hash: str
    status: str = "pending"
    output_trades_uri: str | None = None
