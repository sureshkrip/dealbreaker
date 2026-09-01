"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import scheduler
from .api import api_router
from .auth import require_token
from .config import settings
from .db import init_db
from .scheduler import refresh_all

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="Dealbreaker", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/refresh", dependencies=[Depends(require_token)], tags=["admin"])
async def refresh_now() -> dict[str, int]:
    """Trigger an immediate re-scrape of all tracked URLs."""
    stored = await refresh_all()
    return {"new_prices": stored}
