from typing import Any


def stock_on_hand_value(size_row: dict[str, Any]) -> int:
    return int(size_row.get("stock_on_hand", 0) or 0)


def stock_reserved_value(size_row: dict[str, Any]) -> int:
    return int(size_row.get("stock_reserved", 0) or 0)


def stock_available_value(size_row: dict[str, Any]) -> int:
    return stock_on_hand_value(size_row) - stock_reserved_value(size_row)


def inventory_projection(size_row: dict[str, Any]) -> dict[str, Any]:
    on_hand = stock_on_hand_value(size_row)
    reserved = stock_reserved_value(size_row)
    available = on_hand - reserved
    return {
        **size_row,
        "stock_on_hand": on_hand,
        "stock_reserved": reserved,
        "stock_available": available,
    }
