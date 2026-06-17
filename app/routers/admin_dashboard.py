from datetime import datetime, timedelta

from fastapi import APIRouter, Depends

from app.db import get_db
from app.dependencies_admin import ALL_ADMIN_PERMISSIONS, admin_capabilities, get_current_admin, is_superadmin

router = APIRouter(prefix="/admin/dashboard", tags=["admin-dashboard"])


def _can(admin, permission: str) -> bool:
    return is_superadmin(admin) or permission in (admin.permissions or [])


async def _orders_stats(db):
    total_orders = await db["orders"].count_documents({})
    active_orders = await db["orders"].count_documents({"status": {"$ne": "cancelled"}})
    since = datetime.utcnow() - timedelta(days=30)
    month_orders = await db["orders"].count_documents({"created_at": {"$gte": since}})
    revenue_pipeline = [
        {"$match": {"status": {"$ne": "cancelled"}}},
        {"$group": {"_id": None, "total": {"$sum": "$total_amount"}, "average": {"$avg": "$total_amount"}}},
    ]
    revenue_rows = await db["orders"].aggregate(revenue_pipeline).to_list(length=1)
    revenue = revenue_rows[0] if revenue_rows else {}
    return {
        "total_orders": total_orders,
        "active_orders": active_orders,
        "month_orders": month_orders,
        "revenue": round(float(revenue.get("total", 0) or 0), 2),
        "average_order": round(float(revenue.get("average", 0) or 0), 2),
    }


@router.get("")
async def admin_dashboard_summary(
    db=Depends(get_db),
    current_admin=Depends(get_current_admin),
):
    permissions = current_admin.permissions or []
    capabilities = admin_capabilities(current_admin)
    response = {
        "is_superadmin": is_superadmin(current_admin),
        "permissions": permissions,
        "available_permissions": ALL_ADMIN_PERMISSIONS,
        "capabilities": capabilities,
        "sections": capabilities,
        "metrics": {},
    }

    if _can(current_admin, "products"):
        response["metrics"]["products"] = {
            "total_products": await db["products"].count_documents({}),
            "in_stock_products": await db["products"].count_documents({"in_stock": True}),
        }

    if _can(current_admin, "orders"):
        response["metrics"]["orders"] = await _orders_stats(db)

    if _can(current_admin, "users"):
        response["metrics"]["users"] = {
            "total_users": await db["users"].count_documents({}),
            "active_users": await db["users"].count_documents({"is_active": True}),
        }

    if _can(current_admin, "packs"):
        response["metrics"]["packs"] = {
            "total_packs": await db["packs"].count_documents({}),
            "active_packs": await db["packs"].count_documents({"status": "active"}),
        }

    if _can(current_admin, "promocodes"):
        response["metrics"]["promocodes"] = {
            "total_promocodes": await db["promocodes"].count_documents({}),
            "active_promocodes": await db["promocodes"].count_documents({"is_active": True}),
        }

    if _can(current_admin, "categories"):
        response["metrics"]["categories"] = {
            "total_categories": await db["categories"].count_documents({}),
        }

    if _can(current_admin, "shipping"):
        response["metrics"]["shipping"] = {
            "total_shipping_rates": await db["shipping_rates"].count_documents({}),
            "active_shipping_rates": await db["shipping_rates"].count_documents({"is_active": True}),
        }

    if _can(current_admin, "loyalty"):
        response["metrics"]["loyalty"] = {
            "transactions": await db["loyalty_transactions"].count_documents({}),
            "users_with_points": await db["users"].count_documents({"loyalty_points_balance": {"$gt": 0}}),
        }

    if _can(current_admin, "vlog"):
        response["metrics"]["vlog"] = {
            "chapters": await db["vlog_chapters"].count_documents({}),
            "episodes": await db["vlog_episodes"].count_documents({}),
        }

    if _can(current_admin, "header_video"):
        response["metrics"]["header_video"] = {
            "configured": await db["cms_settings"].count_documents({"_id": "store_header_video"}) > 0,
        }

    if _can(current_admin, "engagement"):
        response["metrics"]["engagement"] = {
            "product_reviews": await db["reviews"].count_documents({"status": {"$ne": "hidden"}}),
            "vlog_comments": await db["vlog_comments"].count_documents({"status": "visible"}),
        }

    if _can(current_admin, "admins"):
        response["metrics"]["admins"] = {
            "total_admins": await db["admins"].count_documents({}),
            "active_admins": await db["admins"].count_documents({"is_active": True}),
        }

    return response
