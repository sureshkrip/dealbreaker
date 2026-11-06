"""Scraping engine — a Python port of PriceBuddy's ScrapeUrl/StrategyExtractor.

Given page HTML and a store's scrape strategy, extract title / price / image /
availability. Each field's strategy is a ``{"type": ..., "value": ...}`` pair:

    - ``selector``  CSS selector. ``a|href`` extracts the href attribute; the value may
                    be prefixed with ``!`` to take the element's raw HTML (rarely needed).
    - ``regex``     A regular expression; the first capture group (or whole match) is used.
    - ``json``      A dot-path into embedded JSON-LD (schema.org) blocks, e.g. ``offers.price``.
    - ``schema.org``/``meta``  Resolve from JSON-LD / OpenGraph / meta tags (the default fallback).

When a field has no strategy (or it yields nothing) we fall back to schema.org + OG.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser

from .config import settings
from .models import StockStatus

# Map schema.org availability URLs / tokens to our StockStatus.
_AVAILABILITY_MAP: dict[str, StockStatus] = {
    "instock": StockStatus.in_stock,
    "in_stock": StockStatus.in_stock,
    "onlineonly": StockStatus.in_stock,
    "limitedavailability": StockStatus.in_stock,
    "preorder": StockStatus.pre_order,
    "presale": StockStatus.pre_order,
    "backorder": StockStatus.back_order,
    "specialorder": StockStatus.special_order,
    "outofstock": StockStatus.out_of_stock,
    "soldout": StockStatus.out_of_stock,
    "discontinued": StockStatus.discontinued,
}

_TITLE_SEPARATORS = ["|", " - ", " – ", " — ", " :: ", ": "]


@dataclass
class ScrapeResult:
    title: str | None = None
    price: float | None = None
    image: str | None = None
    availability: StockStatus = StockStatus.unknown
    raw: dict[str, Any] = field(default_factory=dict)


def parse_price(value: Any) -> float | None:
    """Turn a messy price string like ``"$1,299.00"`` or ``"1.299,00 €"`` into a float."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    # Keep digits and separators only.
    text = re.sub(r"[^0-9.,]", "", text)
    if not text:
        return None
    if "," in text and "." in text:
        # The rightmost separator is the decimal point.
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        # Ambiguous: "1,299" (thousands) vs "12,99" (decimal). Two trailing digits => decimal.
        text = text.replace(",", ".") if re.search(r",\d{2}$", text) else text.replace(",", "")
    try:
        return round(float(text), 2)
    except ValueError:
        return None


def clean_title(value: str | None) -> str | None:
    if not value:
        return None
    title = re.sub(r"\s+", " ", value).strip()
    # Strip a trailing store/site name after the last separator, e.g. "Widget | Amazon".
    for sep in _TITLE_SEPARATORS:
        if sep in title:
            head = title.rsplit(sep, 1)[0].strip()
            if len(head) >= 8:  # don't strip so much we lose the product name
                title = head
                break
    return title[:1024] or None


def map_availability(value: Any) -> StockStatus:
    if not value:
        return StockStatus.unknown
    token = re.sub(r"[^a-z]", "", str(value).lower())
    # schema.org URLs end in e.g. ".../InStock"; token becomes "httpsschemaorginstock".
    for key, status in _AVAILABILITY_MAP.items():
        if token.endswith(key):
            return status
    return StockStatus.unknown


# --------------------------------------------------------------------------- #
# JSON-LD / meta extraction (the fallback, and the source for schema.org/json)
# --------------------------------------------------------------------------- #

def _iter_jsonld(tree: HTMLParser):
    for node in tree.css('script[type="application/ld+json"]'):
        text = node.text(strip=True)
        if not text:
            continue
        try:
            data = json.loads(text)
        except (ValueError, TypeError):
            continue
        yield from _flatten_jsonld(data)


def _flatten_jsonld(data: Any):
    if isinstance(data, list):
        for item in data:
            yield from _flatten_jsonld(item)
    elif isinstance(data, dict):
        yield data
        for key in ("@graph", "mainEntity", "itemListElement"):
            if key in data:
                yield from _flatten_jsonld(data[key])


def _first_product_node(tree: HTMLParser) -> dict | None:
    for node in _iter_jsonld(tree):
        node_type = node.get("@type", "")
        types = node_type if isinstance(node_type, list) else [node_type]
        if any(str(t).lower() == "product" for t in types) or "offers" in node:
            return node
    return None


def _offer_of(node: dict) -> dict:
    offers = node.get("offers")
    if isinstance(offers, list) and offers:
        for item in offers:
            if isinstance(item, dict) and (
                item.get("price") or item.get("lowPrice") or item.get("priceSpecification")
            ):
                return item
        offers = offers[0]
    return offers if isinstance(offers, dict) else {}


def _extract_offer_price(offer: dict) -> float | None:
    raw = offer.get("price") or offer.get("lowPrice") or offer.get("highPrice")
    if raw is not None:
        parsed = parse_price(raw)
        if parsed is not None:
            return parsed
    spec = offer.get("priceSpecification")
    if isinstance(spec, list) and spec:
        spec = spec[0]
    if isinstance(spec, dict):
        return parse_price(spec.get("price") or spec.get("minPrice"))
    return None


def _dig(node: dict, path: str) -> Any:
    """Follow a dot-path like ``offers.price`` into nested dict/list JSON."""
    cur: Any = node
    for part in path.split("."):
        if isinstance(cur, list):
            cur = cur[0] if cur else None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _meta(tree: HTMLParser, *names: str) -> str | None:
    for name in names:
        node = tree.css_first(f'meta[property="{name}"]') or tree.css_first(
            f'meta[name="{name}"]'
        )
        if node:
            content = node.attributes.get("content")
            if content:
                return content.strip()
    return None


def schema_org_fallback(tree: HTMLParser) -> ScrapeResult:
    result = ScrapeResult()
    node = _first_product_node(tree)
    if node:
        offer = _offer_of(node)
        result.title = clean_title(node.get("name"))
        result.price = _extract_offer_price(offer)
        img = node.get("image")
        if isinstance(img, list):
            img = img[0] if img else None
        if isinstance(img, dict):
            img = img.get("url") or img.get("contentUrl")
        result.image = img
        result.availability = map_availability(offer.get("availability"))

    # OpenGraph / meta / microdata fallback for anything still missing.
    if not result.title:
        result.title = (
            clean_title(_meta(tree, "og:title", "twitter:title"))
            or clean_title(
                _apply_selector(
                    tree,
                    "h1#productTitle, h1[itemprop='name'], h1.product-title, h1",
                )
            )
            or clean_title(tree.css_first("title").text() if tree.css_first("title") else None)
        )
    if result.price is None:
        result.price = parse_price(
            _meta(
                tree,
                "og:price:amount",
                "product:price:amount",
                "price",
                "twitter:data1",
            )
        )
    if result.price is None:
        # Microdata & common retail price selectors
        micro_price = _apply_selector(
            tree,
            (
                "[itemprop='price']|content, [itemprop='price'], [data-price]|data-price, "
                ".a-price .a-offscreen, .product-price, .sale-price, .current-price, .price"
            ),
        )
        result.price = parse_price(micro_price)
    if not result.image:
        result.image = _meta(tree, "og:image", "twitter:image") or _apply_selector(
            tree,
            (
                "#landingImage|src, [itemprop='image']|src, "
                "[itemprop='image']|content, img#main-image|src"
            ),
        )
    if result.availability == StockStatus.unknown:
        avail_sel = "[itemprop='availability']|href, [itemprop='availability']|content"
        result.availability = map_availability(
            _meta(tree, "og:availability", "product:availability")
            or _apply_selector(tree, avail_sel)
        )
    return result


# --------------------------------------------------------------------------- #
# Per-field strategy application
# --------------------------------------------------------------------------- #

def _apply_single_selector(tree: HTMLParser, value: str) -> str | None:
    raw_html = value.startswith("!")
    selector = value[1:] if raw_html else value
    attr = None
    if "|" in selector:
        selector, attr = selector.rsplit("|", 1)
        selector, attr = selector.strip(), attr.strip()
    try:
        node = tree.css_first(selector.strip())
    except Exception:
        return None
    if not node:
        return None
    if attr:
        return (node.attributes.get(attr) or "").strip() or None
    if raw_html:
        return node.html
    return node.text(strip=True) or None


def _apply_selector(tree: HTMLParser, value: str) -> str | None:
    """Apply a CSS selector (or comma-separated list of fallback selectors)."""
    for candidate in value.split(","):
        cand = candidate.strip()
        if not cand:
            continue
        out = _apply_single_selector(tree, cand)
        if out:
            return out
    return None


def _apply_regex(html: str, value: str) -> str | None:
    # PriceBuddy wraps user patterns in delimiters (~...~, #...#); strip a leading/trailing one.
    pattern = value
    if len(pattern) >= 2 and pattern[0] == pattern[-1] and pattern[0] in "~#/!@":
        pattern = pattern[1:-1]
    try:
        m = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
    except re.error:
        return None
    if not m:
        return None
    return (m.group(1) if m.groups() else m.group(0)).strip() or None


def _apply_field(field_name: str, strat: dict, tree: HTMLParser, html: str) -> Any:
    stype = (strat or {}).get("type")
    value = (strat or {}).get("value")
    if not stype or value in (None, ""):
        return None
    if stype == "selector":
        return _apply_selector(tree, value)
    if stype == "regex":
        return _apply_regex(html, value)
    if stype == "json":
        node = _first_product_node(tree)
        return _dig(node, value) if node else None
    if stype in ("schema.org", "schema", "meta"):
        fb = schema_org_fallback(tree)
        return getattr(fb, field_name, None)
    return None


def extract(html: str, strategy: dict | None = None) -> ScrapeResult:
    """Extract fields from HTML using ``strategy``, falling back to schema.org/OG."""
    tree = HTMLParser(html)
    fallback = schema_org_fallback(tree)
    result = ScrapeResult(
        title=fallback.title,
        price=fallback.price,
        image=fallback.image,
        availability=fallback.availability,
    )

    strategy = strategy or {}
    for field_name in ("title", "price", "image", "availability"):
        strat = strategy.get(field_name)
        if not strat:
            continue
        raw = _apply_field(field_name, strat, tree, html)
        if raw in (None, ""):
            continue
        if field_name == "title":
            result.title = clean_title(str(raw)) or result.title
        elif field_name == "price":
            parsed = parse_price(raw)
            if parsed is not None:
                result.price = parsed
        elif field_name == "image":
            result.image = str(raw)
        elif field_name == "availability":
            mapped = map_availability(raw)
            if mapped != StockStatus.unknown:
                result.availability = mapped

    # A store that scrapes fine but is out of stock legitimately has no price.
    if result.availability in (StockStatus.out_of_stock, StockStatus.discontinued):
        result.price = result.price  # keep last-seen price; caller decides whether to store
    return result


# A full, realistic Chrome header set. Many retailers (e.g. Akamai-protected sites like
# Brooks/Salesforce Commerce Cloud) return 403 to clients that send only a User-Agent;
# sending the complete set a real browser sends gets past header-based bot detection.
def _browser_headers() -> dict[str, str]:
    return {
        "User-Agent": settings.user_agent,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    }


async def fetch_html(url: str) -> str:
    async with httpx.AsyncClient(
        timeout=settings.request_timeout_seconds,
        follow_redirects=True,
        headers=_browser_headers(),
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text


async def scrape(url: str, strategy: dict | None = None) -> ScrapeResult:
    html = await fetch_html(url)
    result = extract(html, strategy)
    if result.image and not result.image.startswith(("http://", "https://", "data:")):
        result.image = urljoin(url, result.image)
    return result
