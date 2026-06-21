from datetime import datetime, timedelta

from bson import ObjectId

from app.crud.admin import list_cms_pages
from app.crud import dashboard as dashboard_crud
from app.dependencies_admin import admin_capabilities, is_superadmin


def can_access(admin, permission: str) -> bool:
    return is_superadmin(admin) or permission in (admin.permissions or [])


async def orders_stats(db):
    total_orders = await dashboard_crud.count_orders(db)
    active_orders = await dashboard_crud.count_orders(db, {"status": {"$ne": "cancelled"}})
    since = datetime.utcnow() - timedelta(days=30)
    month_orders = await dashboard_crud.count_orders(db, {"created_at": {"$gte": since}})
    revenue = await dashboard_crud.summarize_order_revenue(db, {"status": {"$ne": "cancelled"}})
    return {
        "total_orders": total_orders,
        "active_orders": active_orders,
        "month_orders": month_orders,
        "revenue": round(float(revenue.get("total", 0) or 0), 2),
        "average_order": round(float(revenue.get("average", 0) or 0), 2),
    }


async def revenue_for_period(db, start: datetime) -> dict:
    row = await dashboard_crud.summarize_revenue_for_period(db, start)
    return {
        "revenue": round(float(row.get("revenue", 0) or 0), 2),
        "orders": int(row.get("orders", 0) or 0),
        "average_order": round(float(row.get("average_order", 0) or 0), 2),
    }


async def top_products(db, limit: int = 5) -> list[dict]:
    rows = await dashboard_crud.aggregate_top_product_sales(db, limit)

    product_ids = []
    for row in rows:
        try:
            product_ids.append(ObjectId(row["_id"]))
        except Exception:
            pass
    products = await dashboard_crud.list_product_names_by_ids(db, product_ids)
    product_map = {str(product["_id"]): product for product in products}

    return [
        {
            "product_id": row["_id"],
            "product_name": (
                product_map.get(row["_id"], {}).get("full_name")
                or product_map.get(row["_id"], {}).get("name")
                or row["_id"]
            ),
            "qty": int(row.get("qty", 0) or 0),
            "revenue": round(float(row.get("revenue", 0) or 0), 2),
        }
        for row in rows
    ]


async def low_stock(db, threshold: int = 5, limit: int = 10) -> dict:
    items = await dashboard_crud.list_low_stock_items(db, threshold, limit)
    total = await dashboard_crud.count_low_stock_items(db, threshold)
    return {
        "threshold": threshold,
        "total": total,
        "items": [
            {
                "product_id": str(item["_id"]),
                "product_name": item.get("full_name") or item.get("name"),
                "color": item.get("color"),
                "size": item.get("size"),
                "stock": int(item.get("stock", 0) or 0),
            }
            for item in items
        ],
    }


async def executive_summary(db) -> dict:
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    week_start = now - timedelta(days=7)
    month_start = datetime(now.year, now.month, 1)
    active_customers = await dashboard_crud.distinct_order_user_ids(
        db,
        {
            "created_at": {"$gte": now - timedelta(days=30)},
            "user_id": {"$ne": None},
            "status": {"$ne": "cancelled"},
        },
    )
    return {
        "revenue": {
            "today": await revenue_for_period(db, today_start),
            "last_7_days": await revenue_for_period(db, week_start),
            "month": await revenue_for_period(db, month_start),
        },
        "orders_to_process": await dashboard_crud.count_orders(db, {"status": {"$in": ["pending", "confirmed"]}}),
        "pending_reviews": await dashboard_crud.count_collection(db, "reviews", {"status": "pending"}),
        "pending_comments": await dashboard_crud.count_collection(db, "vlog_comments", {"status": "pending"}),
        "active_customers_30d": len(active_customers),
        "low_stock": await low_stock(db),
        "top_products": await top_products(db),
    }


async def build_dashboard_summary(db, current_admin) -> dict:
    permissions = current_admin.permissions or []
    capabilities = await admin_capabilities(current_admin)
    response = {
        "is_superadmin": is_superadmin(current_admin),
        "permissions": permissions,
        "available_permissions": await list_cms_pages(),
        "capabilities": capabilities,
        "sections": capabilities,
        "metrics": {},
    }

    if can_access(current_admin, "orders") or can_access(current_admin, "products") or can_access(current_admin, "engagement"):
        response["executive"] = await executive_summary(db)

    if can_access(current_admin, "products"):
        response["metrics"]["products"] = {
            "total_products": await dashboard_crud.count_collection(db, "products"),
            "in_stock_products": await dashboard_crud.count_collection(db, "products", {"in_stock": True}),
        }

    if can_access(current_admin, "orders"):
        response["metrics"]["orders"] = await orders_stats(db)

    if can_access(current_admin, "users"):
        response["metrics"]["users"] = {
            "total_users": await dashboard_crud.count_collection(db, "users"),
            "active_users": await dashboard_crud.count_collection(db, "users", {"is_active": True}),
        }

    if can_access(current_admin, "packs"):
        response["metrics"]["packs"] = {
            "total_packs": await dashboard_crud.count_collection(db, "packs"),
            "active_packs": await dashboard_crud.count_collection(db, "packs", {"status": "active"}),
        }

    if can_access(current_admin, "promocodes"):
        response["metrics"]["promocodes"] = {
            "total_promocodes": await dashboard_crud.count_collection(db, "promocodes"),
            "active_promocodes": await dashboard_crud.count_collection(db, "promocodes", {"is_active": True}),
        }

    if can_access(current_admin, "categories"):
        response["metrics"]["categories"] = {
            "total_categories": await dashboard_crud.count_collection(db, "categories"),
        }

    if can_access(current_admin, "shipping"):
        response["metrics"]["shipping"] = {
            "total_shipping_rates": await dashboard_crud.count_collection(db, "shipping_rates"),
            "active_shipping_rates": await dashboard_crud.count_collection(db, "shipping_rates", {"is_active": True}),
        }

    if can_access(current_admin, "loyalty"):
        response["metrics"]["loyalty"] = {
            "transactions": await dashboard_crud.count_collection(db, "loyalty_transactions"),
            "users_with_points": await dashboard_crud.count_collection(db, "users", {"loyalty_points_balance": {"$gt": 0}}),
        }

    if can_access(current_admin, "vlog"):
        response["metrics"]["vlog"] = {
            "chapters": await dashboard_crud.count_collection(db, "vlog_chapters"),
            "episodes": await dashboard_crud.count_collection(db, "vlog_episodes"),
        }

    if can_access(current_admin, "header_video"):
        response["metrics"]["header_video"] = {
            "configured": await dashboard_crud.count_collection(db, "cms_settings", {"_id": "store_header_video"}) > 0,
        }

    if can_access(current_admin, "engagement"):
        response["metrics"]["engagement"] = {
            "product_reviews": await dashboard_crud.count_collection(db, "reviews", {"status": {"$ne": "hidden"}}),
            "vlog_comments": await dashboard_crud.count_collection(db, "vlog_comments", {"status": "visible"}),
        }

    if can_access(current_admin, "admins"):
        response["metrics"]["admins"] = {
            "total_admins": await dashboard_crud.count_collection(db, "admins"),
            "active_admins": await dashboard_crud.count_collection(db, "admins", {"is_active": True}),
        }

    return response
