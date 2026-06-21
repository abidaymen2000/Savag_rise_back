import asyncio
from typing import Literal
from fastapi import FastAPI
from pydantic import BaseModel

from app.config import settings
from app.routers.routers_cms import admin_cms_pages, admin_comments, admin_vlog, drop_countdown, header_video
from app.routers.routers_erp import (
    admin_admins,
    admin_auth,
    admin_categories,
    admin_dashboard,
    admin_audit,
    admin_exports,
    admin_inventory,
    admin_loyalty,
    admin_notifications,
    admin_order_actions,
    admin_orders,
    admin_packs,
    admin_products,
    admin_promocodes,
    admin_shipping_rates,
    admin_users,
    admin_variants,
    analytics as analytics_routes,
    upload,
)
from app.routers.routers_store import (
    analytics as store_analytics,
    auth,
    categories,
    contact,
    drop_countdown as store_drop_countdown,
    header_video as store_header_video,
    loyalty,
    meta_catalog,
    orders,
    packs,
    products,
    profile,
    promocodes,
    reviews,
    shipping_rates,
    storefront_vlog,
    variants,
    wishlist,
)
from app.startup import init_mongo
from app.services.services_cms.drop_countdown_notifier import drop_countdown_monitor_loop

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Savage Rise E‑commerce API",  servers = [
    {"url": "http://localhost:8000"},
    {"url": str(settings.BACKEND_URL).rstrip("/")},
])

app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

# Health-check model
class HealthStatus(BaseModel):
    status: Literal["online", "offline"]

#  ←– Ajoute ce endpoint
@app.get(
    "/health",
    response_model=HealthStatus,
    summary="Vérifie la santé de l'API",
    operation_id="checkHealth"
)
async def check_health():
    return {"status": "online"}

@app.on_event("startup")
async def on_startup():
    # Crée collections et index avant que l'app n'accepte des requêtes
    await init_mongo()
    app.state.drop_countdown_task = asyncio.create_task(drop_countdown_monitor_loop())


@app.on_event("shutdown")
async def on_shutdown():
    task = getattr(app.state, "drop_countdown_task", None)
    if task:
        task.cancel()

# enregistrement des routes
app.include_router(upload.router)
app.include_router(profile.router)
app.include_router(products.router)
app.include_router(variants.router)
app.include_router(orders.router)
app.include_router(auth.router)
app.include_router(reviews.router)
app.include_router(wishlist.router)
app.include_router(categories.router)
app.include_router(contact.router)
app.include_router(shipping_rates.router)
app.include_router(promocodes.router)
app.include_router(store_header_video.router)
app.include_router(storefront_vlog.router)
app.include_router(loyalty.router)
app.include_router(packs.router)
app.include_router(meta_catalog.router)
app.include_router(store_drop_countdown.router)
app.include_router(store_analytics.router)
app.include_router(analytics_routes.router)
app.include_router(admin_auth.router)
app.include_router(admin_admins.router)
app.include_router(admin_categories.router)
app.include_router(admin_cms_pages.router)
app.include_router(header_video.router)
app.include_router(admin_dashboard.router)
app.include_router(admin_audit.router)
app.include_router(admin_comments.router)
app.include_router(admin_exports.router)
app.include_router(admin_inventory.router)
app.include_router(admin_loyalty.router)
app.include_router(admin_notifications.router)
app.include_router(admin_order_actions.router)
app.include_router(admin_orders.router)
app.include_router(admin_packs.router)
app.include_router(admin_products.router)
app.include_router(admin_promocodes.router)
app.include_router(admin_shipping_rates.router)
app.include_router(admin_users.router)
app.include_router(admin_variants.router)
app.include_router(admin_vlog.router)
app.include_router(drop_countdown.router)
