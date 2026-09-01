"""Store resolution: match a URL's domain to a Store, auto-creating one if needed."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from sqlmodel import Session, select

from .models import Store

# A few starter stores with sensible default strategies. Most real stores work off the
# schema.org / OpenGraph fallback, so the strategy can be empty ({}) to mean "use fallback".
DEFAULT_STORES: list[dict] = [
    {
        "name": "Amazon",
        "slug": "amazon",
        "initials": "AZ",
        "domains": ["amazon.com", "amazon.com.au", "amazon.co.uk", "amazon.de", "amazon.ca"],
        "scrape_strategy": {
            "title": {"type": "selector", "value": "#productTitle"},
            "price": {"type": "selector", "value": ".a-price .a-offscreen"},
            "image": {"type": "selector", "value": "#landingImage|src"},
        },
    },
    {
        "name": "eBay",
        "slug": "ebay",
        "initials": "EB",
        "domains": ["ebay.com", "ebay.com.au", "ebay.co.uk"],
        "scrape_strategy": {},  # schema.org fallback handles eBay well
    },
    {
        "name": "Best Buy",
        "slug": "bestbuy",
        "initials": "BB",
        "domains": ["bestbuy.com"],
        "scrape_strategy": {},
    },
]


def bare_domain(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return re.sub(r"^www\.", "", host)


def store_name_from_domain(domain: str) -> str:
    core = domain.split(".")[0] if domain else "store"
    return core.replace("-", " ").title() or "Store"


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "store"


def resolve_store(session: Session, url: str) -> Store:
    """Return the Store matching ``url``'s domain, creating a bare one if none exists."""
    domain = bare_domain(url)
    for store in session.exec(select(Store)).all():
        for d in store.domains or []:
            if domain == d or domain.endswith("." + d):
                return store

    name = store_name_from_domain(domain)
    store = Store(
        name=name,
        slug=slugify(name),
        initials="".join(w[0] for w in name.split()[:2]).upper() or None,
        domains=[domain] if domain else [],
        scrape_strategy={},
    )
    session.add(store)
    session.commit()
    session.refresh(store)
    return store


def seed_default_stores(session: Session) -> int:
    created = 0
    existing_slugs = {s.slug for s in session.exec(select(Store)).all()}
    for spec in DEFAULT_STORES:
        if spec["slug"] in existing_slugs:
            continue
        session.add(Store(**spec))
        created += 1
    if created:
        session.commit()
    return created
