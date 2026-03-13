from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from app.routers import admin_auth, admin_orders, admin_users, contact
from app.startup import init_mongo
from .routers import (
    profile,
    products,
    upload,
    variants,
    orders,
    auth,
    reviews,
    wishlist,
    categories,
    promocodes,
)

app = FastAPI(
    title="Savage Rise E-commerce API",
    servers=[
        {"url": "http://localhost:8000"},
        {"url": "https://savage-rise-backend-8f0f0a23c13f.herokuapp.com"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://savagerise.com",
        "https://www.savagerise.com",
        "http://localhost:3000",
        "http://localhost:4200",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthStatus(BaseModel):
    status: Literal["online", "offline"]


@app.get(
    "/health",
    response_model=HealthStatus,
    summary="Vérifie la santé de l'API",
    operation_id="checkHealth",
)
async def check_health():
    return {"status": "online"}


@app.on_event("startup")
async def on_startup():
    await init_mongo()


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
app.include_router(promocodes.router)
app.include_router(admin_auth.router)
app.include_router(admin_orders.router)
app.include_router(admin_users.router)