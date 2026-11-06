"""Background scheduler: periodically re-scrape every tracked URL."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlmodel import Session, select

from .config import settings
from .db import engine
from .models import Product, Url
from .services import refresh_url, sync_product_deals

log = logging.getLogger("dealbreaker.scheduler")
_scheduler: AsyncIOScheduler | None = None


async def refresh_all() -> int:
    """Re-scrape all direct URLs and scan all stores for every tracked product."""
    stored = 0
    with Session(engine) as session:
        products = session.exec(select(Product)).all()
        for product in products:
            stored += await sync_product_deals(session, product)

        urls = session.exec(select(Url)).all()
        for url in urls:
            if "slickdeals.net" in (url.url or ""):
                continue
            price = await refresh_url(session, url)
            if price is not None:
                stored += 1
    log.info(
        "scheduled refresh complete: %d new prices across %d products / %d urls",
        stored,
        len(products),
        len(urls),
    )
    return stored


def start() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        refresh_all,
        "interval",
        minutes=settings.scrape_interval_minutes,
        id="refresh_all",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    log.info("scheduler started (every %d min)", settings.scrape_interval_minutes)


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
