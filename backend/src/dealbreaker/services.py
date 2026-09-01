"""Core domain operations shared by the API and the scheduler."""

from __future__ import annotations

import logging

from sqlmodel import Session, select

from . import notify
from .models import Price, Product, StockStatus, Url, utcnow
from .scraper import ScrapeResult, scrape

log = logging.getLogger("dealbreaker.services")


async def refresh_url(session: Session, url: Url) -> Price | None:
    """Re-scrape a single URL, append a Price row if a price was found, and check targets.

    Returns the new Price row, or None if nothing was stored (e.g. out of stock).
    """
    store = url.store
    try:
        result: ScrapeResult = await scrape(url.url, store.scrape_strategy or {})
    except Exception as exc:  # network / parse errors shouldn't kill the batch
        log.warning("scrape failed for url %s: %s", url.id, exc)
        return None

    url.availability = result.availability
    url.last_scraped_at = utcnow()
    session.add(url)

    new_price: Price | None = None
    if result.price is not None and result.availability not in (
        StockStatus.out_of_stock,
        StockStatus.discontinued,
    ):
        new_price = Price(price=result.price, url_id=url.id, store_id=url.store_id)
        session.add(new_price)

    session.commit()
    if new_price:
        session.refresh(new_price)
        _evaluate_targets(session, url.product_id)
    return new_price


def _latest_price(session: Session, url_id: int) -> float | None:
    row = session.exec(
        select(Price).where(Price.url_id == url_id).order_by(Price.created_at.desc())
    ).first()
    return row.price if row else None


def current_best(session: Session, product_id: int) -> float | None:
    """Lowest current price across all of a product's URLs."""
    prices = [
        _latest_price(session, u.id)
        for u in session.exec(select(Url).where(Url.product_id == product_id)).all()
    ]
    prices = [p for p in prices if p is not None]
    return min(prices) if prices else None


def _highest_ever(session: Session, product_id: int) -> float | None:
    urls = session.exec(select(Url).where(Url.product_id == product_id)).all()
    highs: list[float] = []
    for u in urls:
        rows = session.exec(select(Price).where(Price.url_id == u.id)).all()
        highs.extend(r.price for r in rows)
    return max(highs) if highs else None


def _evaluate_targets(session: Session, product_id: int) -> None:
    """Fire an ntfy notification if a product hit its absolute or percent-drop target."""
    product = session.get(Product, product_id)
    if not product:
        return
    best = current_best(session, product_id)
    if best is None:
        return

    hit_reason: str | None = None
    if product.notify_price is not None and best <= product.notify_price:
        hit_reason = f"now ${best:.2f} (target ${product.notify_price:.2f})"
    elif product.notify_percent is not None:
        high = _highest_ever(session, product_id)
        if high and high > 0:
            drop = (high - best) / high * 100
            if drop >= product.notify_percent:
                hit_reason = f"down {drop:.0f}% to ${best:.2f} (from ${high:.2f})"

    if not hit_reason:
        return

    # Avoid re-notifying: mark the newest unnotified price rows for this product.
    unnotified = _unnotified_prices(session, product_id)
    if not unnotified:
        return
    notify.send(
        title=f"Price drop: {product.title}",
        message=f"{product.title} is {hit_reason}",
        url=_any_url(session, product_id),
    )
    for row in unnotified:
        row.notified = True
        session.add(row)
    session.commit()


def _unnotified_prices(session: Session, product_id: int) -> list[Price]:
    urls = session.exec(select(Url).where(Url.product_id == product_id)).all()
    out: list[Price] = []
    for u in urls:
        out.extend(
            session.exec(
                select(Price).where(Price.url_id == u.id, Price.notified == False)  # noqa: E712
            ).all()
        )
    return out


def _any_url(session: Session, product_id: int) -> str | None:
    u = session.exec(select(Url).where(Url.product_id == product_id)).first()
    return u.url if u else None
