from enum import Enum


class OrderStatus(str, Enum):
    RECEIVED = "received"
    VALIDATED = "validated"
    SOURCED = "sourced"
    ORDERED_FROM_SUPPLIER = "ordered_from_supplier"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    EXCEPTION = "exception"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class InvalidTransition(ValueError):
    """Raised when an order status transition is not allowed."""


ALLOWED_TRANSITIONS = {
    OrderStatus.RECEIVED: {
        OrderStatus.VALIDATED,
        OrderStatus.EXCEPTION,
        OrderStatus.CANCELLED,
    },
    OrderStatus.VALIDATED: {
        OrderStatus.SOURCED,
        OrderStatus.EXCEPTION,
        OrderStatus.CANCELLED,
    },
    OrderStatus.SOURCED: {
        OrderStatus.ORDERED_FROM_SUPPLIER,
        OrderStatus.EXCEPTION,
        OrderStatus.CANCELLED,
    },
    OrderStatus.ORDERED_FROM_SUPPLIER: {
        OrderStatus.SHIPPED,
        OrderStatus.EXCEPTION,
        OrderStatus.CANCELLED,
    },
    OrderStatus.SHIPPED: {OrderStatus.DELIVERED, OrderStatus.EXCEPTION},
    OrderStatus.DELIVERED: {OrderStatus.REFUNDED},
    OrderStatus.EXCEPTION: {
        OrderStatus.VALIDATED,
        OrderStatus.SOURCED,
        OrderStatus.CANCELLED,
    },
    OrderStatus.CANCELLED: {OrderStatus.REFUNDED},
    OrderStatus.REFUNDED: set(),
}


def transition(current, target):
    try:
        current_status = OrderStatus(current)
        target_status = OrderStatus(target)
    except (TypeError, ValueError) as error:
        raise InvalidTransition(f"Invalid order status: {error}") from error

    if target_status not in ALLOWED_TRANSITIONS[current_status]:
        raise InvalidTransition(
            f"Cannot transition from {current_status.value} to {target_status.value}"
        )
    return target_status