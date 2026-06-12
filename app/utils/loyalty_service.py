from datetime import datetime
from typing import Optional

from bson import ObjectId
from fastapi import HTTPException, status

from app.schemas.loyalty import LoyaltySettingsOut, LoyaltyTransactionOut


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
    doc = await db[SETTINGS_COLLECTION].find_one({"_id": LOYALTY_SETTINGS_KEY})
    if not doc:
        return LoyaltySettingsOut()
    return LoyaltySettingsOut(**doc["value"], updated_at=doc.get("updated_at"))


async def get_points_balance(db, user_id: str) -> int:
    user = await db["users"].find_one({"_id": validate_object_id(user_id, "Utilisateur ID")}, {"loyalty_points_balance": 1})
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Utilisateur introuvable")
    return int(user.get("loyalty_points_balance", 0) or 0)


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
    res = await db[TRANSACTIONS_COLLECTION].insert_one(data)
    data["id"] = str(res.inserted_id)
    return LoyaltyTransactionOut(**data)


async def redeem_points_for_order(db, user_id: str, order_id: str, points: int, discount_value: float) -> int:
    if points <= 0:
        return await get_points_balance(db, user_id)
    user_oid = validate_object_id(user_id, "Utilisateur ID")
    res = await db["users"].find_one_and_update(
        {"_id": user_oid, "loyalty_points_balance": {"$gte": points}},
        {"$inc": {"loyalty_points_balance": -points}},
        return_document=True,
    )
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
    res = await db["users"].find_one_and_update(
        {"_id": validate_object_id(user_id, "Utilisateur ID")},
        {"$inc": {"loyalty_points_balance": points}},
        return_document=True,
    )
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
        await db["orders"].update_one({"_id": order_doc["_id"]}, {"$set": {"loyalty_points_refunded": True}})


async def award_points_for_paid_order(db, order_id: ObjectId) -> int:
    order = await db["orders"].find_one({"_id": order_id})
    if not order or not order.get("user_id") or order.get("loyalty_points_awarded"):
        return 0

    settings = await loyalty_settings_out(db)
    eligible_amount = float(order.get("loyalty_eligible_amount", order.get("subtotal", 0)) or 0)
    points = calculate_earn_points(eligible_amount, settings)
    if points <= 0:
        await db["orders"].update_one({"_id": order_id}, {"$set": {"loyalty_points_awarded": True, "loyalty_points_earned": 0}})
        return 0

    res = await db["users"].find_one_and_update(
        {"_id": validate_object_id(order["user_id"], "Utilisateur ID")},
        {"$inc": {"loyalty_points_balance": points}},
        return_document=True,
    )
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
    await db["orders"].update_one(
        {"_id": order_id},
        {"$set": {"loyalty_points_awarded": True, "loyalty_points_earned": points}},
    )
    return points
