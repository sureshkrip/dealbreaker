"""Live Deals API — Slickdeals Frontpage, Popular, and Keyword Search."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..auth import require_token
from ..deals import fetch_slickdeals
from ..schemas import DealOut

router = APIRouter(
    prefix="/api/deals", tags=["deals"], dependencies=[Depends(require_token)]
)


@router.get("", response_model=list[DealOut])
async def list_live_deals(
    q: str | None = Query(default=None, description="Keyword or product name to search"),
    mode: str = Query(default="frontpage", description="frontpage or popular"),
    limit: int = Query(default=24, ge=1, le=50),
) -> list[DealOut]:
    """Fetch live deals from Slickdeals (Frontpage, Popular, or Keyword search)."""
    items = await fetch_slickdeals(query=q, mode=mode, limit=limit)
    return [DealOut(**d.__dict__) for d in items]
