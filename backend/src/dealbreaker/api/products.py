"""Product & URL endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..auth import require_token
from ..db import get_session
from ..models import Price, Product, Url
from ..schemas import (
    PricePoint,
    ProductCreate,
    ProductListItem,
    ProductOut,
    ProductUpdate,
    UrlAdd,
    UrlOut,
)
from ..scraper import scrape
from ..services import current_best, refresh_url
from ..stores import resolve_store

router = APIRouter(prefix="/api/products", tags=["products"], dependencies=[Depends(require_token)])


def _latest_price(session: Session, url_id: int) -> float | None:
    row = session.exec(
        select(Price).where(Price.url_id == url_id).order_by(Price.created_at.desc())
    ).first()
    return row.price if row else None


def _url_out(session: Session, url: Url) -> UrlOut:
    return UrlOut(
        id=url.id,
        url=url.url,
        store_id=url.store_id,
        store_name=url.store.name,
        availability=url.availability,
        latest_price=_latest_price(session, url.id),
        last_scraped_at=url.last_scraped_at,
    )


def _product_out(session: Session, product: Product) -> ProductOut:
    return ProductOut(
        id=product.id,
        title=product.title,
        image=product.image,
        favourite=product.favourite,
        notify_price=product.notify_price,
        notify_percent=product.notify_percent,
        best_price=current_best(session, product.id),
        urls=[_url_out(session, u) for u in product.urls],
    )


@router.get("", response_model=list[ProductListItem])
def list_products(session: Session = Depends(get_session)) -> list[ProductListItem]:
    products = session.exec(select(Product).order_by(Product.created_at.desc())).all()
    return [
        ProductListItem(
            id=p.id,
            title=p.title,
            image=p.image,
            favourite=p.favourite,
            best_price=current_best(session, p.id),
            store_count=len(p.urls),
        )
        for p in products
    ]


@router.post("", response_model=ProductOut, status_code=201)
async def create_product(
    body: ProductCreate, session: Session = Depends(get_session)
) -> ProductOut:
    store = resolve_store(session, body.url)
    try:
        result = await scrape(body.url, store.scrape_strategy or {})
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not scrape URL: {exc}") from exc
    if not result.title:
        raise HTTPException(status_code=422, detail="Could not extract a product title")

    product = Product(
        title=result.title,
        image=result.image,
        notify_price=body.notify_price,
        notify_percent=body.notify_percent,
    )
    session.add(product)
    session.commit()
    session.refresh(product)

    url = Url(url=body.url, product_id=product.id, store_id=store.id)
    session.add(url)
    session.commit()
    session.refresh(url)

    await refresh_url(session, url)
    session.refresh(product)
    return _product_out(session, product)


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, session: Session = Depends(get_session)) -> ProductOut:
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return _product_out(session, product)


@router.patch("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int, body: ProductUpdate, session: Session = Depends(get_session)
) -> ProductOut:
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for field_name, value in body.model_dump(exclude_unset=True).items():
        setattr(product, field_name, value)
    session.add(product)
    session.commit()
    session.refresh(product)
    return _product_out(session, product)


@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: int, session: Session = Depends(get_session)) -> None:
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    session.delete(product)
    session.commit()


@router.get("/{product_id}/prices", response_model=dict[int, list[PricePoint]])
def product_prices(
    product_id: int, session: Session = Depends(get_session)
) -> dict[int, list[PricePoint]]:
    """Price history grouped by URL id."""
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    history: dict[int, list[PricePoint]] = {}
    for url in product.urls:
        rows = session.exec(
            select(Price).where(Price.url_id == url.id).order_by(Price.created_at)
        ).all()
        history[url.id] = [PricePoint(price=r.price, created_at=r.created_at) for r in rows]
    return history


@router.post("/{product_id}/urls", response_model=ProductOut, status_code=201)
async def add_url(
    product_id: int, body: UrlAdd, session: Session = Depends(get_session)
) -> ProductOut:
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    store = resolve_store(session, body.url)
    url = Url(url=body.url, product_id=product.id, store_id=store.id)
    session.add(url)
    session.commit()
    session.refresh(url)
    await refresh_url(session, url)
    session.refresh(product)
    return _product_out(session, product)


@router.post("/urls/{url_id}/refresh", response_model=UrlOut)
async def refresh_single_url(url_id: int, session: Session = Depends(get_session)) -> UrlOut:
    url = session.get(Url, url_id)
    if not url:
        raise HTTPException(status_code=404, detail="URL not found")
    await refresh_url(session, url)
    session.refresh(url)
    return _url_out(session, url)


@router.delete("/urls/{url_id}", status_code=204)
def delete_url(url_id: int, session: Session = Depends(get_session)) -> None:
    url = session.get(Url, url_id)
    if not url:
        raise HTTPException(status_code=404, detail="URL not found")
    session.delete(url)
    session.commit()
