"""API routers."""

from fastapi import APIRouter

from .products import router as products_router
from .stores import router as stores_router

api_router = APIRouter()
api_router.include_router(products_router)
api_router.include_router(stores_router)

__all__ = ["api_router"]
