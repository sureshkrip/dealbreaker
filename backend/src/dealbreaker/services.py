"""Core domain operations shared by the API and the scheduler."""

from __future__ import annotations

import logging

from sqlmodel import Session, select

from . import notify
from .deals import fetch_slickdeals
from .models import Price, Product, StockStatus, Url, utcnow
from .scraper import ScrapeResult, scrape
from .stores import resolve_store_by_name

log = logging.getLogger("dealbreaker.services")


async def sync_product_deals(session: Session, product: Product) -> int:
    """Search across all stores/deals for this product by name and record store listings & prices.

    Allows monitoring any product across Amazon, Best Buy, Walmart, Costco, Target, eBay, etc.
    without requiring a manually entered store URL.
    """
    query = (product.search_query or product.title or "").strip()
    if not query:
        return 0
    words = [w for w in query.split() if len(w) > 1]
    short_query = " ".join(words[:5]) if len(words) > 5 else query

    deals = await fetch_slickdeals(query=short_query, limit=20)
    if not deals:
        return 0

    # Pick the lowest-priced active deal per store
    best_by_store: dict[str, object] = {}
    for d in deals:
        if d.price is None or d.price <= 0:
            continue
        existing = best_by_store.get(d.store_name)
        if existing is None or d.price < existing.price:
            best_by_store[d.store_name] = d

    stored_count = 0
    existing_urls = session.exec(select(Url).where(Url.product_id == product.id)).all()

    for store_name, deal in list(best_by_store.items())[:8]:
        store = resolve_store_by_name(session, store_name)
        # Find existing Slickdeals-backed URL for this store on this product, or create one
        target_url = next(
            (
                u
                for u in existing_urls
                if u.store_id == store.id and "slickdeals.net" in (u.url or "")
            ),
            None,
        )
        if target_url is None:
            target_url = Url(
                url=deal.url,
                product_id=product.id,
                store_id=store.id,
                availability=StockStatus.in_stock,
                last_scraped_at=utcnow(),
            )
            session.add(target_url)
            session.commit()
            session.refresh(target_url)
            existing_urls.append(target_url)
        else:
            target_url.url = deal.url
            target_url.availability = StockStatus.in_stock
            target_url.last_error = None
            target_url.last_scraped_at = utcnow()
            session.add(target_url)

        if deal.image and not product.image:
            product.image = deal.image
            session.add(product)

        last_price = _latest_price(session, target_url.id)
        if last_price is None or last_price != deal.price:
            session.add(
                Price(price=deal.price, url_id=target_url.id, store_id=store.id)
            )
            stored_count += 1

    session.commit()
    if stored_count > 0:
        _evaluate_targets(session, product.id)
    return stored_count


async def refresh_url(
    session: Session, url: Url, pre_scraped: ScrapeResult | None = None
) -> Price | None:
    """Re-scrape a single URL, append a Price row if a price was found, and check targets.

    Returns the new Price row, or None if nothing was stored (e.g. out of stock).
    """
    if pre_scraped is None and "slickdeals.net" in (url.url or "") and url.product:
        await sync_product_deals(session, url.product)
        row = session.exec(
            select(Price).where(Price.url_id == url.id).order_by(Price.created_at.desc())
        ).first()
        return row

    store = url.store
    if pre_scraped is not None:
        result = pre_scraped
    else:
        try:
            result = await scrape(url.url, store.scrape_strategy or {})
        except Exception as exc:  # network / parse errors shouldn't kill the batch
            log.warning("scrape failed for url %s: %s", url.id, exc)
            url.last_error = f"Scrape failed: {exc}"[:500]
            url.last_scraped_at = utcnow()
            session.add(url)
            session.commit()
            return None

    url.availability = result.availability
    url.last_scraped_at = utcnow()

    if result.image and url.product and not url.product.image:
        url.product.image = result.image
        session.add(url.product)

    new_price: Price | None = None
    if result.price is not None and result.availability not in (
        StockStatus.out_of_stock,
        StockStatus.discontinued,
    ):
        url.last_error = None
        new_price = Price(price=result.price, url_id=url.id, store_id=url.store_id)
        session.add(new_price)
    elif result.price is None and result.availability not in (
        StockStatus.out_of_stock,
        StockStatus.discontinued,
    ):
        url.last_error = "No price found on page — check store scrape strategy"
    else:
        url.last_error = None

    session.add(url)
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


def compute_product_stats(session: Session, product: Product) -> dict:
    """Compute comprehensive price history metrics for a product."""
    urls = session.exec(select(Url).where(Url.product_id == product.id)).all()
    all_prices: list[Price] = []
    latest_per_url: list[float] = []
    last_scraped: list = []

    for u in urls:
        if u.last_scraped_at:
            last_scraped.append(u.last_scraped_at)
        rows = session.exec(
            select(Price).where(Price.url_id == u.id).order_by(Price.created_at.asc())
        ).all()
        if rows:
            all_prices.extend(rows)
            latest_per_url.append(rows[-1].price)

    best = min(latest_per_url) if latest_per_url else None
    price_vals = [r.price for r in all_prices]
    lowest = min(price_vals) if price_vals else None
    highest = max(price_vals) if price_vals else None

    # Compare current best against highest or previous distinct price to show trend
    price_change: float | None = None
    price_change_percent: float | None = None
    if best is not None and len(all_prices) >= 2:
        sorted_rows = sorted(all_prices, key=lambda r: r.created_at)
        # Find the most recent price that differs from `best`, or fall back to initial price
        baseline = sorted_rows[0].price
        for r in reversed(sorted_rows[:-1]):
            if r.price != best:
                baseline = r.price
                break
        if baseline and baseline > 0:
            price_change = round(best - baseline, 2)
            price_change_percent = round((best - baseline) / baseline * 100, 1)

    target_hit = False
    if best is not None:
        if product.notify_price is not None and best <= product.notify_price:
            target_hit = True
        elif product.notify_percent is not None and highest and highest > 0:
            drop_pct = (highest - best) / highest * 100
            if drop_pct >= product.notify_percent:
                target_hit = True

    return {
        "best_price": best,
        "lowest_price": lowest,
        "highest_price": highest,
        "price_change": price_change,
        "price_change_percent": price_change_percent,
        "target_hit": target_hit,
        "last_scraped_at": max(last_scraped) if last_scraped else None,
        "store_names": list(dict.fromkeys(u.store.name for u in urls if u.store)),
    }


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
