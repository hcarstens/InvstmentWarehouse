"""Post-trade reconciliation — custodian vs ledger breaks → exception queue."""

from pydantic import BaseModel


class ReconciliationBreak(BaseModel):
    break_id: str
    account_id: str
    description: str
    resolved: bool = False
