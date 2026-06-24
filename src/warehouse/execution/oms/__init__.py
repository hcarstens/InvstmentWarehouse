"""OMS / trade staging — deferred until reconciliation and security master v0 are trustworthy."""

from enum import StrEnum

from pydantic import BaseModel


class OrderStatus(StrEnum):
    STAGED = "staged"
    SUBMITTED = "submitted"
    FILLED = "filled"
    CANCELLED = "cancelled"


class StagedOrder(BaseModel):
    order_id: str
    approval_request_id: str
    status: OrderStatus = OrderStatus.STAGED
