"""Store endpoints — list and edit scrape strategies."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..auth import require_token
from ..db import get_session
from ..models import StockStatus, Store
from ..schemas import StoreOut, StoreTestRequest, StoreUpdate, UrlPreviewOut
from ..scraper import scrape

router = APIRouter(prefix="/api/stores", tags=["stores"], dependencies=[Depends(require_token)])


@router.get("", response_model=list[StoreOut])
def list_stores(session: Session = Depends(get_session)) -> list[Store]:
    return session.exec(select(Store).order_by(Store.name)).all()


@router.get("/{store_id}", response_model=StoreOut)
def get_store(store_id: int, session: Session = Depends(get_session)) -> Store:
    store = session.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@router.patch("/{store_id}", response_model=StoreOut)
def update_store(
    store_id: int, body: StoreUpdate, session: Session = Depends(get_session)
) -> Store:
    store = session.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    for field_name, value in body.model_dump(exclude_unset=True).items():
        setattr(store, field_name, value)
    session.add(store)
    session.commit()
    session.refresh(store)
    return store


@router.post("/{store_id}/test", response_model=UrlPreviewOut)
async def test_store_strategy(
    store_id: int, body: StoreTestRequest, session: Session = Depends(get_session)
) -> UrlPreviewOut:
    """Test a store's scrape strategy against a sample URL without saving."""
    store = session.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    strategy = (
        body.scrape_strategy if body.scrape_strategy is not None else (store.scrape_strategy or {})
    )
    try:
        result = await scrape(body.url.strip(), strategy)
        return UrlPreviewOut(
            url=body.url.strip(),
            title=result.title,
            price=result.price,
            image=result.image,
            availability=result.availability,
            store_name=store.name,
            error=None if result.price is not None else "No price matched with this strategy.",
        )
    except Exception as exc:
        return UrlPreviewOut(
            url=body.url.strip(),
            title=None,
            price=None,
            image=None,
            availability=StockStatus.unknown,
            store_name=store.name,
            error=f"Scrape failed: {exc}",
        )
