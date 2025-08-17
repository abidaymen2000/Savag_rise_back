from typing import Literal
from fastapi import FastAPI
from pydantic import BaseModel

from app.routers import admin_auth, admin_orders, contact
from app.startup import init_mongo

from .routers import profile, products, upload, variants, orders, auth, reviews, wishlist, categories, promocodes
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Savage Rise E‑commerce API",  servers = [
    {"url": "http://localhost:8000"},
    {"url": "https://savage-rise-backend-d86a05fb19d4.herokuapp.com"},
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
app.include_router(promocodes.router)
app.include_router(admin_auth.router)
app.include_router(admin_orders.router)