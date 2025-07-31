from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.startup import init_mongo

from .routers import profile, products, upload, variants, orders, auth, reviews, wishlist
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Savage Rise E‑commerce API", servers=[{"url": "http://localhost:8000"}])

app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    # Crée collections et index avant que l'app n'accepte des requêtes
    await init_mongo()

# Sert tout ce qui est dans ./static via /static
app.mount("/static", StaticFiles(directory="static"), name="static")

# enregistrement des routes
app.include_router(upload.router)
app.include_router(profile.router)
app.include_router(products.router)
app.include_router(variants.router)
app.include_router(orders.router)
app.include_router(auth.router)
app.include_router(reviews.router)
app.include_router(wishlist.router)