from datetime import datetime
from typing import Optional

from bson import ObjectId
from fastapi import HTTPException, status

from app.crud import loyalty as loyalty_crud
from app.schemas.loyalty import (
    LoyaltyBalanceOut,
    LoyaltyQuoteOut,
    LoyaltySettingsOut,
    LoyaltyTransactionOut,
    PaginatedLoyaltyTransactionsOut,
)


SETTINGS_COLLECTION = "cms_settings"
LOYALTY_SETTINGS_KEY = "loyalty_program"
TRANSACTIONS_COLLECTION = "loyalty_transactions"


def now_utc() -> datetime:
    return datetime.utcnow()


def validate_object_id(value: str, label: str = "ID") -> ObjectId:
    try:
        return ObjectId(value)
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{label} invalide")


async def loyalty_settings_out(db) -> LoyaltySettingsOut:
    doc = await loyalty_crud.find_loyalty_settings(db)
    if not doc:
        return LoyaltySettingsOut()
    return LoyaltySettingsOut(**doc["value"], updated_at=doc.get("updated_at"))


async def get_points_balance(db, user_id: str) -> int:
    user = await loyalty_crud.find_user_points_balance(db, validate_object_id(user_id, "Utilisateur ID"))
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Utilisateur introuvable")
    return int(user.get("loyalty_points_balance", 0) or 0)


def transaction_out(doc) -> LoyaltyTransactionOut:
    payload = {k: v for k, v in doc.items() if k != "_id"}
    payload["id"] = str(doc["_id"])
    return LoyaltyTransactionOut(**payload)


def points_value(points: int, settings: LoyaltySettingsOut) -> float:
    return round(max(0, int(points)) * float(settings.point_value), 2)


def calculate_earn_points(eligible_amount: float, settings: LoyaltySettingsOut) -> int:
    if not settings.is_active or eligible_amount <= 0:
        return 0
    value = float(eligible_amount) * (float(settings.earning_percentage) / 100)
    return int(value / float(settings.point_value))


def calculate_redeem(
    requested_points: int,
    balance: int,
    eligible_amount: float,
    settings: LoyaltySettingsOut,
) -> tuple[int, float]:
    if not settings.is_active or requested_points <= 0 or eligible_amount <= 0:
        return 0, 0.0
    if requested_points < settings.min_redeem_points:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Minimum {settings.min_redeem_points} SR pour utiliser les points fidelite",
        )

    max_discount = float(eligible_amount) * (float(settings.max_redeem_percentage) / 100)
    max_points_by_total = int(max_discount / float(settings.point_value))
    usable_points = min(int(requested_points), int(balance), max_points_by_total)
    discount_value = min(points_value(usable_points, settings), round(float(eligible_amount), 2))
    return usable_points, discount_value


async def add_loyalty_transaction(
    db,
    user_id: str,
    tx_type: str,
    points: int,
    value: float,
    balance_after: int,
    order_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> LoyaltyTransactionOut:
    now = now_utc()
    data = {
        "user_id": user_id,
        "type": tx_type,
        "points": int(points),
        "value": float(value),
        "order_id": order_id,
        "reason": reason,
        "balance_after": int(balance_after),
        "created_at": now,
    }
    res = await loyalty_crud.insert_loyalty_transaction(db, data)
    data["id"] = str(res.inserted_id)
    return LoyaltyTransactionOut(**data)


async def update_loyalty_settings(db, payload) -> LoyaltySettingsOut:
    value = payload.model_dump()
    updated_at = now_utc()
    await loyalty_crud.save_loyalty_settings(db, value, updated_at)
    return LoyaltySettingsOut(**value, updated_at=updated_at)


async def get_user_loyalty_balance(db, user_id: str, limit: int) -> LoyaltyBalanceOut:
    validate_object_id(user_id, "Utilisateur ID")
    settings = await loyalty_settings_out(db)
    balance = await get_points_balance(db, user_id)
    docs = await loyalty_crud.list_loyalty_transactions(db, {"user_id": user_id}, limit=limit)
    return LoyaltyBalanceOut(
        user_id=user_id,
        points_balance=balance,
        value_balance=points_value(balance, settings),
        settings=settings,
        recent_transactions=[transaction_out(doc) for doc in docs],
    )


async def quote_loyalty_redemption(db, user_id: str, payload) -> LoyaltyQuoteOut:
    settings = await loyalty_settings_out(db)
    balance = await get_points_balance(db, user_id)
    usable_points, discount_value = calculate_redeem(
        payload.points_to_use,
        balance,
        payload.order_total,
        settings,
    )
    remaining_total = max(0.0, round(float(payload.order_total) - discount_value, 2))
    return LoyaltyQuoteOut(
        points_balance=balance,
        requested_points=payload.points_to_use,
        usable_points=usable_points,
        discount_value=discount_value,
        remaining_total=remaining_total,
        estimated_points_earned=calculate_earn_points(remaining_total, settings),
        settings=settings,
    )


async def adjust_user_loyalty(db, user_id: str, payload) -> LoyaltyBalanceOut:
    user_oid = validate_object_id(user_id, "Utilisateur ID")
    user = await loyalty_crud.find_user_points_balance(db, user_oid)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Utilisateur introuvable")
    before = int(user.get("loyalty_points_balance", 0) or 0)
    balance = max(0, before + payload.points)
    delta = balance - before
    await loyalty_crud.set_user_points_balance(db, user_oid, balance)
    settings = await loyalty_settings_out(db)
    await add_loyalty_transaction(
        db,
        user_id=user_id,
        tx_type="adjust",
        points=delta,
        value=points_value(abs(delta), settings) * (1 if delta >= 0 else -1),
        balance_after=balance,
        reason=payload.reason or "Ajustement admin",
    )
    docs = await loyalty_crud.list_loyalty_transactions(db, {"user_id": user_id}, limit=20)
    return LoyaltyBalanceOut(
        user_id=user_id,
        points_balance=balance,
        value_balance=points_value(balance, settings),
        settings=settings,
        recent_transactions=[transaction_out(doc) for doc in docs],
    )


async def list_loyalty_transactions(db, page: int, page_size: int, user_id: str | None, order_id: str | None):
    filters = {}
    if user_id:
        filters["user_id"] = user_id
    if order_id:
        filters["order_id"] = order_id
    skip = (page - 1) * page_size
    total = await loyalty_crud.count_loyalty_transactions(db, filters)
    docs = await loyalty_crud.list_loyalty_transactions(db, filters, skip=skip, limit=page_size)
    return PaginatedLoyaltyTransactionsOut(
        items=[transaction_out(doc) for doc in docs],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


async def redeem_points_for_order(db, user_id: str, order_id: str, points: int, discount_value: float) -> int:
    if points <= 0:
        return await get_points_balance(db, user_id)
    user_oid = validate_object_id(user_id, "Utilisateur ID")
    res = await loyalty_crud.decrement_user_points_if_available(db, user_oid, points)
    if not res:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Solde SR insuffisant")
    balance_after = int(res.get("loyalty_points_balance", 0) or 0)
    await add_loyalty_transaction(
        db,
        user_id=user_id,
        tx_type="redeem",
        points=-points,
        value=-discount_value,
        balance_after=balance_after,
        order_id=order_id,
        reason="Utilisation SR sur commande",
    )
    return balance_after


async def refund_redeemed_points(db, order_doc: dict, reason: str = "Remboursement SR") -> None:
    points = int(order_doc.get("loyalty_points_used", 0) or 0)
    user_id = order_doc.get("user_id")
    if not user_id or points <= 0 or order_doc.get("loyalty_points_refunded"):
        return
    res = await loyalty_crud.increment_user_points(db, validate_object_id(user_id, "Utilisateur ID"), points)
    balance_after = int((res or {}).get("loyalty_points_balance", 0) or 0)
    order_id = str(order_doc.get("_id") or order_doc.get("id"))
    await add_loyalty_transaction(
        db,
        user_id=user_id,
        tx_type="refund",
        points=points,
        value=float(order_doc.get("loyalty_discount_value", 0) or 0),
        balance_after=balance_after,
        order_id=order_id,
        reason=reason,
    )
    if order_doc.get("_id"):
        await loyalty_crud.mark_order_loyalty_points_refunded(db, order_doc["_id"])


async def award_points_for_paid_order(db, order_id: ObjectId) -> int:
    order = await loyalty_crud.find_order_by_id(db, order_id)
    if not order or not order.get("user_id") or order.get("loyalty_points_awarded"):
        return 0

    settings = await loyalty_settings_out(db)
    eligible_amount = float(order.get("loyalty_eligible_amount", order.get("subtotal", 0)) or 0)
    points = calculate_earn_points(eligible_amount, settings)
    if points <= 0:
        await loyalty_crud.mark_order_loyalty_awarded(db, order_id, 0)
        return 0

    res = await loyalty_crud.increment_user_points(db, validate_object_id(order["user_id"], "Utilisateur ID"), points)
    balance_after = int((res or {}).get("loyalty_points_balance", 0) or 0)
    await add_loyalty_transaction(
        db,
        user_id=order["user_id"],
        tx_type="earn",
        points=points,
        value=points_value(points, settings),
        balance_after=balance_after,
        order_id=str(order_id),
        reason="Gain SR apres paiement",
    )
    await loyalty_crud.mark_order_loyalty_awarded(db, order_id, points)
    return points
