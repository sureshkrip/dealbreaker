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
            "title": {"type": "selector", "value": "#productTitle, #title"},
            "price": {
                "type": "selector",
                "value": (
                    ".apexPriceToPay .a-offscreen, "
                    "#corePriceDisplay_desktop_feature_div .a-offscreen, "
                    ".a-price .a-offscreen, #priceblock_ourprice, #priceblock_dealprice"
                ),
            },
            "image": {"type": "selector", "value": "#landingImage|src, #imgBlkFront|src"},
        },
    },
    {
        "name": "eBay",
        "slug": "ebay",
        "initials": "EB",
        "domains": ["ebay.com", "ebay.com.au", "ebay.co.uk"],
        "scrape_strategy": {
            "title": {"type": "selector", "value": "h1.x-item-title__mainTitle"},
            "price": {"type": "selector", "value": ".x-price-primary span.ux-textspans"},
        },
    },
    {
        "name": "Best Buy",
        "slug": "bestbuy",
        "initials": "BB",
        "domains": ["bestbuy.com"],
        "scrape_strategy": {
            "title": {"type": "selector", "value": ".sku-title h1, h1"},
            "price": {
                "type": "selector",
                "value": (
                    ".priceView-hero-price span[aria-hidden='true'], "
                    "[data-testid='customer-price'] span"
                ),
            },
        },
    },
    {
        "name": "Walmart",
        "slug": "walmart",
        "initials": "WM",
        "domains": ["walmart.com"],
        "scrape_strategy": {
            "title": {"type": "selector", "value": "h1#main-title, h1[itemprop='name']"},
            "price": {
                "type": "selector",
                "value": "[itemprop='price'], span[data-automation-id='product-price']",
            },
        },
    },
    {
        "name": "Target",
        "slug": "target",
        "initials": "TG",
        "domains": ["target.com"],
        "scrape_strategy": {
            "title": {"type": "selector", "value": "h1[data-test='product-title'], h1"},
            "price": {"type": "selector", "value": "[data-test='product-price']"},
        },
    },
    {
        "name": "Newegg",
        "slug": "newegg",
        "initials": "NE",
        "domains": ["newegg.com"],
        "scrape_strategy": {
            "title": {"type": "selector", "value": "h1.product-title"},
            "price": {"type": "selector", "value": ".price-current"},
        },
    },
    {
        "name": "B&H Photo",
        "slug": "bhphoto",
        "initials": "BH",
        "domains": ["bhphotovideo.com"],
        "scrape_strategy": {
            "title": {"type": "selector", "value": "h1[data-selenium='productTitle']"},
            "price": {"type": "selector", "value": "[data-selenium='pricingPrice']"},
        },
    },
]


def fallback_title_from_url(url: str) -> str | None:
    """Derive a human-readable product title from a URL slug when scraping is blocked."""
    parsed = urlparse(url)
    parts = [p for p in (parsed.path or "").split("/") if p]
    # Filter out generic segments like 'dp', 'gp', 'product', 'p', 'ip', pure IDs/numbers
    candidates: list[str] = []
    skip_words = {"dp", "gp", "product", "products", "item", "items", "p", "ip", "site", "d"}
    for part in parts:
        clean = re.sub(r"\.(html?|php|aspx?)$", "", part, flags=re.IGNORECASE)
        if clean.lower() in skip_words:
            continue
        # Skip pure ASINs or numeric IDs like B09XS7JWHH or 12345678
        if re.fullmatch(r"[A-Z0-9]{8,14}", clean) or re.fullmatch(r"\d+", clean):
            continue
        if "-" in clean or "_" in clean or len(clean) >= 6:
            candidates.append(clean)
    if not candidates:
        return None
    best = max(candidates, key=len)
    words = re.sub(r"[-_+]+", " ", best).strip()
    return words.title() if len(words) >= 3 else None


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


def resolve_store_by_name(session: Session, store_name: str) -> Store:
    """Return the Store matching a retailer name (e.g. 'Amazon'), creating one if needed."""
    clean_name = (store_name or "Deal").strip()
    slug = slugify(clean_name)
    for store in session.exec(select(Store)).all():
        if store.slug == slug or store.name.lower() == clean_name.lower():
            return store

    initials = "".join(w[0] for w in clean_name.split()[:2]).upper() or "DL"
    store = Store(
        name=clean_name,
        slug=slug,
        initials=initials,
        domains=[],
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
