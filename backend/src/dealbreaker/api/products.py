"""Product & URL endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..auth import require_token
from ..db import get_session
from ..deals import fetch_slickdeals
from ..models import Price, Product, StockStatus, Url, utcnow
from ..schemas import (
    DealOut,
    ManualPriceAdd,
    PricePoint,
    ProductCreate,
    ProductListItem,
    ProductOut,
    ProductUpdate,
    UrlAdd,
    UrlOut,
    UrlPreviewOut,
    UrlPreviewRequest,
)
from ..scraper import ScrapeResult, scrape
from ..services import _evaluate_targets, compute_product_stats, refresh_url
from ..stores import fallback_title_from_url, resolve_store

router = APIRouter(
    prefix="/api/products", tags=["products"], dependencies=[Depends(require_token)]
)


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
        last_error=url.last_error,
        last_scraped_at=url.last_scraped_at,
    )


def _product_out(session: Session, product: Product) -> ProductOut:
    stats = compute_product_stats(session, product)
    return ProductOut(
        id=product.id,
        title=product.title,
        image=product.image,
        favourite=product.favourite,
        search_query=product.search_query,
        category=product.category,
        notify_price=product.notify_price,
        notify_percent=product.notify_percent,
        best_price=stats["best_price"],
        lowest_price=stats["lowest_price"],
        highest_price=stats["highest_price"],
        price_change=stats["price_change"],
        price_change_percent=stats["price_change_percent"],
        target_hit=stats["target_hit"],
        store_names=stats["store_names"],
        last_scraped_at=stats["last_scraped_at"],
        urls=[_url_out(session, u) for u in product.urls],
    )


@router.get("", response_model=list[ProductListItem])
def list_products(session: Session = Depends(get_session)) -> list[ProductListItem]:
    products = session.exec(select(Product).order_by(Product.created_at.desc())).all()
    items: list[ProductListItem] = []
    for p in products:
        stats = compute_product_stats(session, p)
        items.append(
            ProductListItem(
                id=p.id,
                title=p.title,
                image=p.image,
                favourite=p.favourite,
                search_query=p.search_query,
                category=p.category,
                notify_price=p.notify_price,
                notify_percent=p.notify_percent,
                best_price=stats["best_price"],
                lowest_price=stats["lowest_price"],
                highest_price=stats["highest_price"],
                price_change=stats["price_change"],
                price_change_percent=stats["price_change_percent"],
                target_hit=stats["target_hit"],
                store_count=len(p.urls),
                store_names=stats["store_names"],
                last_scraped_at=stats["last_scraped_at"],
            )
        )
    return items


@router.post("/preview", response_model=UrlPreviewOut)
async def preview_product_url(
    body: UrlPreviewRequest, session: Session = Depends(get_session)
) -> UrlPreviewOut:
    """Test-scrape a product URL and return extracted fields without saving yet."""
    clean_url = body.url.strip()
    store = resolve_store(session, clean_url)
    fallback_title = fallback_title_from_url(clean_url)
    try:
        result = await scrape(clean_url, store.scrape_strategy or {})
    except Exception as exc:
        return UrlPreviewOut(
            url=clean_url,
            title=fallback_title,
            price=None,
            image=None,
            availability=StockStatus.unknown,
            store_name=store.name,
            error=(
                f"Store blocked automatic scrape ({exc}). "
                "You can still track it by confirming the title and price below."
            ),
        )

    title = result.title or fallback_title
    warn: str | None = None
    if result.price is None:
        warn = (
            "Could not detect price automatically on this page. "
            "You can enter the current price below or customize the Store Strategy."
        )
    return UrlPreviewOut(
        url=clean_url,
        title=title,
        price=result.price,
        image=result.image,
        availability=result.availability,
        store_name=store.name,
        error=warn,
    )


@router.post("", response_model=ProductOut, status_code=201)
async def create_product(
    body: ProductCreate, session: Session = Depends(get_session)
) -> ProductOut:
    clean_url = (body.url or "").strip() or None
    user_title = (body.title or "").strip() or None
    search_query = (body.search_query or "").strip() or None

    if not clean_url and not user_title and not search_query:
        raise HTTPException(
            status_code=422,
            detail="Provide either a product URL or a product name to track.",
        )

    result = ScrapeResult()
    scrape_error: str | None = None
    store = None

    if clean_url:
        store = resolve_store(session, clean_url)
        try:
            result = await scrape(clean_url, store.scrape_strategy or {})
        except Exception as exc:
            scrape_error = f"Scrape failed: {exc}"[:500]
            if not user_title and not fallback_title_from_url(clean_url):
                raise HTTPException(
                    status_code=422, detail=f"Could not scrape URL: {exc}"
                ) from exc

    final_title = (
        user_title
        or result.title
        or search_query
        or (fallback_title_from_url(clean_url) if clean_url else None)
    )
    if not final_title:
        raise HTTPException(status_code=422, detail="Could not extract a product title")

    final_image = (body.image or "").strip() or result.image
    if body.initial_price is not None and result.price is None:
        result.price = body.initial_price
        if result.availability == StockStatus.unknown:
            result.availability = StockStatus.in_stock

    product = Product(
        title=final_title,
        image=final_image,
        search_query=search_query or final_title,
        category=(body.category or "").strip() or None,
        notify_price=body.notify_price,
        notify_percent=body.notify_percent,
    )
    session.add(product)
    session.commit()
    session.refresh(product)

    if clean_url and store:
        url = Url(
            url=clean_url,
            product_id=product.id,
            store_id=store.id,
            last_error=scrape_error,
            last_scraped_at=utcnow(),
        )
        session.add(url)
        session.commit()
        session.refresh(url)

        if scrape_error is None or result.price is not None:
            await refresh_url(session, url, pre_scraped=result)

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
    product.updated_at = utcnow()
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


@router.get("/{product_id}/deals", response_model=list[DealOut])
async def product_live_deals(
    product_id: int, session: Session = Depends(get_session)
) -> list[DealOut]:
    """Find live Slickdeals community/staff deals matching this product."""
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    query = (product.search_query or product.title or "").strip()
    # Keep first 5 meaningful words if the title is very long
    words = [w for w in query.split() if len(w) > 1]
    short_query = " ".join(words[:5]) if len(words) > 5 else query
    items = await fetch_slickdeals(query=short_query, limit=12)
    return [DealOut(**d.__dict__) for d in items]


@router.post("/{product_id}/urls", response_model=ProductOut, status_code=201)
async def add_url(
    product_id: int, body: UrlAdd, session: Session = Depends(get_session)
) -> ProductOut:
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    clean_url = body.url.strip()
    store = resolve_store(session, clean_url)
    url = Url(url=clean_url, product_id=product.id, store_id=store.id)
    session.add(url)
    session.commit()
    session.refresh(url)

    await refresh_url(session, url)
    # If manual price was supplied and scrape didn't find a price, record the manual price
    if body.price is not None and _latest_price(session, url.id) is None:
        manual_price = Price(price=body.price, url_id=url.id, store_id=store.id)
        url.last_error = None
        url.availability = StockStatus.in_stock
        session.add(manual_price)
        session.add(url)
        session.commit()

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


@router.post("/urls/{url_id}/price", response_model=UrlOut)
def record_manual_price(
    url_id: int, body: ManualPriceAdd, session: Session = Depends(get_session)
) -> UrlOut:
    """Manually record a price point for a URL (useful when a store blocks bots or has a coupon)."""
    url = session.get(Url, url_id)
    if not url:
        raise HTTPException(status_code=404, detail="URL not found")
    new_price = Price(price=body.price, url_id=url.id, store_id=url.store_id)
    url.availability = StockStatus.in_stock
    url.last_error = None
    url.last_scraped_at = utcnow()
    session.add(new_price)
    session.add(url)
    session.commit()
    _evaluate_targets(session, url.product_id)
    session.refresh(url)
    return _url_out(session, url)


@router.delete("/urls/{url_id}", status_code=204)
def delete_url(url_id: int, session: Session = Depends(get_session)) -> None:
    url = session.get(Url, url_id)
    if not url:
        raise HTTPException(status_code=404, detail="URL not found")
    session.delete(url)
    session.commit()
