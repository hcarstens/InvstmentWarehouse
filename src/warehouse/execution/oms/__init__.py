"""OMS / trade staging — approval → staged orders → execution routing."""

from enum import StrEnum

from pydantic import BaseModel


class OrderStatus(StrEnum):
    STAGED = "staged"
    SUBMITTED = "submitted"
    FILLED = "filled"
    CANCELLED = "cancelled"


class OrderTransitionError(ValueError):
    """Raised when an order status change violates the allowed-edge map."""

    def __init__(
        self,
        order_id: str,
        from_status: OrderStatus,
        to_status: OrderStatus,
        *,
        operation: str | None = None,
    ) -> None:
        self.order_id = order_id
        self.from_status = from_status
        self.to_status = to_status
        self.operation = operation
        if operation is not None:
            detail = (
                f"Cannot {operation} order {order_id} "
                f"in status '{from_status.value}'"
            )
        else:
            detail = (
                f"Illegal order status transition for {order_id}: "
                f"{from_status.value} → {to_status.value}"
            )
        super().__init__(detail)


class StagedOrder(BaseModel):
    order_id: str
    approval_request_id: str
    status: OrderStatus = OrderStatus.STAGED


__all__ = [
    "OrderStatus",
    "OrderTransitionError",
    "StagedOrder",
]
