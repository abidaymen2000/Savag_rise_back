from app.domain.order_constants import (
    FULFILLMENT_STATUS_CANCELLED,
    FULFILLMENT_STATUS_FULFILLED,
    FULFILLMENT_STATUS_PROCESSING,
    FULFILLMENT_STATUS_RESERVED,
    FULFILLMENT_STATUS_RETURNED,
    FULFILLMENT_STATUS_RETURNING,
    ORDER_STATUS_CANCELLED,
    ORDER_STATUS_CONFIRMED,
    ORDER_STATUS_DELIVERED,
    ORDER_STATUS_PENDING,
    ORDER_STATUS_PREPARING,
    ORDER_STATUS_RETURNED,
    ORDER_STATUS_RETURN_IN_TRANSIT,
    ORDER_STATUS_RETURN_RECEIVED,
    ORDER_STATUS_RETURN_REQUESTED,
    ORDER_STATUS_SHIPPED,
    PAYMENT_STATUS_PARTIALLY_REFUNDED,
    PAYMENT_STATUS_REFUNDED,
)
from app.domain.order_errors import InvalidOrderTransitionError


ORDER_TRANSITIONS = {
    ORDER_STATUS_PENDING: {ORDER_STATUS_CONFIRMED, ORDER_STATUS_CANCELLED},
    ORDER_STATUS_CONFIRMED: {ORDER_STATUS_PREPARING, ORDER_STATUS_CANCELLED},
    ORDER_STATUS_PREPARING: {ORDER_STATUS_SHIPPED, ORDER_STATUS_CANCELLED},
    ORDER_STATUS_SHIPPED: {ORDER_STATUS_DELIVERED, ORDER_STATUS_RETURN_REQUESTED},
    ORDER_STATUS_DELIVERED: {ORDER_STATUS_RETURN_REQUESTED},
    ORDER_STATUS_RETURN_REQUESTED: {ORDER_STATUS_RETURN_IN_TRANSIT},
    ORDER_STATUS_RETURN_IN_TRANSIT: {ORDER_STATUS_RETURN_RECEIVED},
    ORDER_STATUS_RETURN_RECEIVED: {ORDER_STATUS_RETURNED},
    ORDER_STATUS_CANCELLED: set(),
    ORDER_STATUS_RETURNED: set(),
}


def ensure_order_transition(current_status: str, next_status: str) -> None:
    if next_status == current_status:
        return
    allowed = ORDER_TRANSITIONS.get(current_status, set())
    if next_status not in allowed:
        raise InvalidOrderTransitionError(f"Transition invalide: {current_status} -> {next_status}")


def fulfillment_status_for_order_status(order_status: str, current_fulfillment_status: str | None) -> str:
    if order_status == ORDER_STATUS_PENDING:
        return current_fulfillment_status or "reserved"
    if order_status == ORDER_STATUS_CONFIRMED:
        return FULFILLMENT_STATUS_RESERVED
    if order_status == ORDER_STATUS_PREPARING:
        return FULFILLMENT_STATUS_PROCESSING
    if order_status in {ORDER_STATUS_SHIPPED, ORDER_STATUS_DELIVERED}:
        return FULFILLMENT_STATUS_FULFILLED
    if order_status == ORDER_STATUS_CANCELLED:
        return FULFILLMENT_STATUS_CANCELLED
    if order_status in {ORDER_STATUS_RETURN_REQUESTED, ORDER_STATUS_RETURN_IN_TRANSIT}:
        return FULFILLMENT_STATUS_RETURNING
    if order_status in {ORDER_STATUS_RETURN_RECEIVED, ORDER_STATUS_RETURNED}:
        return FULFILLMENT_STATUS_RETURNED
    return current_fulfillment_status or "unfulfilled"


def payment_status_after_refund(amount: float, total_amount: float) -> str:
    if amount >= total_amount:
        return PAYMENT_STATUS_REFUNDED
    return PAYMENT_STATUS_PARTIALLY_REFUNDED
