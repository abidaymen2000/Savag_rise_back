from fastapi import FastAPI
from .routers import users, products
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Savage Rise E‑commerce API", servers=[{"url": "http://localhost:8000"}])

app.add_middleware(
  CORSMiddleware,
  allow_origins=["http://localhost:3000"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)
app.include_router(users.router)
app.include_router(products.router)


