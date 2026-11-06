"""Live Deal Discovery Engine — Multi-Store & Slickdeals Scanner.

Allows Dealbreaker to monitor a product across all stores by product name alone
(no store or URL required):
1. Searches Slickdeals title-matched deals across Amazon, Best Buy, Walmart, Costco, etc.
2. Filters out cheap accessory false-positives (cases, covers, cables, straps) unless requested.
3. Automatically syncs store listings and price history for every tracked product.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.parse import quote_plus

import httpx
from selectolax.parser import HTMLParser

from .config import settings
from .scraper import _browser_headers, parse_price

log = logging.getLogger("dealbreaker.deals")

# Pure retailers (checked first so "Apple AirPods at Best Buy" resolves to "Best Buy", not "Apple").
RETAIL_STORES: list[tuple[str, str]] = [
    ("Amazon", "Amazon"),
    ("Best Buy", "Best Buy"),
    ("BestBuy", "Best Buy"),
    ("Walmart", "Walmart"),
    ("Target", "Target"),
    ("Costco", "Costco"),
    ("Sam's Club", "Sam's Club"),
    ("Sams Club", "Sam's Club"),
    ("eBay", "eBay"),
    ("B&H Photo", "B&H Photo"),
    ("B&H", "B&H Photo"),
    ("Newegg", "Newegg"),
    ("Home Depot", "Home Depot"),
    ("Lowe's", "Lowe's"),
    ("Lowes", "Lowe's"),
    ("Woot", "Woot"),
    ("Adorama", "Adorama"),
    ("Micro Center", "Micro Center"),
    ("Macy's", "Macy's"),
    ("Kohl's", "Kohl's"),
    ("REI", "REI"),
    ("GameStop", "GameStop"),
    ("Wayfair", "Wayfair"),
    ("Staples", "Staples"),
    ("Office Depot", "Office Depot"),
    ("Monoprice", "Monoprice"),
    ("Verizon", "Verizon"),
    ("T-Mobile", "T-Mobile"),
    ("AT&T", "AT&T"),
]

# Brand direct stores (matched when "at/via/from <Brand>" or if no retail store matched).
BRAND_STORES = [
    "Samsung",
    "Dell",
    "Lenovo",
    "HP",
    "Apple",
    "Sony",
    "LG",
    "Anker",
    "Nike",
    "Adidas",
    "Garmin",
    "Dyson",
    "Bose",
    "Sonos",
    "Nintendo",
    "PlayStation",
    "Microsoft",
]

ACCESSORY_KEYWORDS = {
    "case",
    "cover",
    "protector",
    "skin",
    "strap",
    "band",
    "cable",
    "cord",
    "adapter",
    "mount",
    "holder",
    "stand",
    "sleeve",
    "pouch",
    "keychain",
    "earpads",
    "tips",
}

_ACCESSORY_PHRASE_RE = re.compile(
    r"\b(?:case|cover|screen\s+protector|protector|skin|strap|band|mount|holder|sleeve|pouch|ear\s*tips|replacement)\s+(?:for|compatible\s+with|fits)\b",
    re.IGNORECASE,
)

_PRICE_RE = re.compile(
    r"\$\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)"
)
_ORIG_PRICE_RE = re.compile(
    r"(?:reg\.?|regular|was|list(?:\s+price)?|msrp|orig\.?|normally)\s*:?\s*\$\s*([0-9,]+(?:\.[0-9]{1,2})?)",
    re.IGNORECASE,
)
_COUPON_RE = re.compile(
    r"(?:code|coupon|promo(?:\s+code)?)\s*[:\"']?\s*([A-Z0-9_-]{4,20})",
    re.IGNORECASE,
)


@dataclass
class DealItem:
    id: str
    title: str
    url: str
    price: float | None = None
    original_price: float | None = None
    discount_percent: int | None = None
    store_name: str = "Deal"
    image: str | None = None
    published_at: str | None = None
    coupon_code: str | None = None
    summary: str | None = None
    is_frontpage: bool = False
    source: str = "Slickdeals"


def is_accessory_mismatch(query: str, deal_title: str) -> bool:
    """Return True if deal_title is an accessory ('Case for X') when query didn't ask for one."""
    q_words = set(re.findall(r"[a-z0-9]+", query.lower()))
    if q_words & ACCESSORY_KEYWORDS:
        return False
    return bool(_ACCESSORY_PHRASE_RE.search(deal_title))


def extract_deal_price(title: str, description_text: str = "") -> float | None:
    """Extract the primary deal price from a deal title or description."""
    cleaned_title = re.sub(
        r"\$\s*[0-9,]+(?:\.[0-9]{1,2})?\s*(?:off|rebate|gift\s*card|gc|savings)",
        "",
        title,
        flags=re.IGNORECASE,
    )
    matches = _PRICE_RE.findall(cleaned_title)
    if matches:
        return parse_price(matches[0])
    desc_matches = _PRICE_RE.findall(description_text)
    if desc_matches:
        return parse_price(desc_matches[0])
    return None


def extract_original_price(
    title: str, description_text: str, deal_price: float | None
) -> float | None:
    """Extract the list/compare price if mentioned."""
    combined = f"{title} {description_text}"
    m = _ORIG_PRICE_RE.search(combined)
    if m:
        orig = parse_price(m.group(1))
        if orig and (deal_price is None or orig > deal_price):
            return orig
    return None


def detect_store(title: str, description_text: str = "") -> str:
    """Detect the merchant/store name from a deal headline or body."""
    # 1. Explicit "at <Store>" / "via <Store>" / "from <Store>" / "[<Store>]" in title
    m_explicit = re.search(
        r"(?:\b(?:at|via|from)\s+|\[)([A-Z][A-Za-z0-9&'.\s]{1,18}?)(?:\]|\s*[-–|:(]|\s+for\s+\$|$)",
        title,
    )
    if m_explicit:
        cand = m_explicit.group(1).strip()
        for token, canonical in RETAIL_STORES:
            if token.lower() in cand.lower():
                return canonical
        for brand in BRAND_STORES:
            if brand.lower() == cand.lower():
                return f"{brand} Store"

    # 2. Check pure retail stores anywhere in the title
    for token, canonical in RETAIL_STORES:
        pattern = r"\b" + re.escape(token) + r"\b"
        if re.search(pattern, title, re.IGNORECASE):
            return canonical

    # 3. Check pure retail stores in the description text
    for token, canonical in RETAIL_STORES:
        pattern = r"\b" + re.escape(token) + r"\b"
        if re.search(pattern, description_text, re.IGNORECASE):
            return canonical

    # 4. Fallback to brand store if mentioned in title
    for brand in BRAND_STORES:
        pattern = r"\b" + re.escape(brand) + r"\b"
        if re.search(pattern, title, re.IGNORECASE):
            return f"{brand} Direct"

    return "Multi-Store"


def parse_slickdeals_rss(
    xml_text: str, is_frontpage: bool = False, query: str | None = None
) -> list[DealItem]:
    """Parse Slickdeals RSS XML into structured DealItem objects."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        log.warning("Failed to parse Slickdeals RSS XML: %s", exc)
        return []

    ns = {"content": "http://purl.org/rss/1.0/modules/content/"}
    deals: list[DealItem] = []

    for idx, item in enumerate(root.findall(".//item")):
        raw_title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip() or None
        guid = (item.findtext("guid") or link or f"sd-{idx}").strip()

        if not raw_title or not link:
            continue

        if query and is_accessory_mismatch(query, raw_title):
            continue

        content_html = (
            item.findtext("content:encoded", default="", namespaces=ns)
            or item.findtext("description")
            or ""
        )
        tree = HTMLParser(content_html)
        desc_text = tree.text(separator=" ", strip=True) if tree.body else ""

        image: str | None = None
        for img_node in tree.css("img"):
            src = img_node.attributes.get("src") or img_node.attributes.get("data-src")
            skip_tokens = ("pixel", "spacer", "1x1", "avatar")
            if src and not any(skip in src.lower() for skip in skip_tokens):
                if src.startswith("//"):
                    src = "https:" + src
                image = src
                break

        price = extract_deal_price(raw_title, desc_text)
        orig_price = extract_original_price(raw_title, desc_text, price)
        discount_pct: int | None = None
        if price is not None and orig_price is not None and orig_price > price:
            discount_pct = round((orig_price - price) / orig_price * 100)

        store_name = detect_store(raw_title, desc_text)

        coupon_match = _COUPON_RE.search(f"{raw_title} {desc_text}")
        coupon_code = coupon_match.group(1) if coupon_match else None
        if coupon_code and coupon_code.lower() in {
            "with",
            "from",
            "free",
            "deal",
            "sale",
            "code",
        }:
            coupon_code = None

        summary = desc_text[:200].strip()
        if len(desc_text) > 200:
            summary += "…"

        deals.append(
            DealItem(
                id=guid,
                title=raw_title,
                url=link,
                price=price,
                original_price=orig_price,
                discount_percent=discount_pct,
                store_name=store_name,
                image=image,
                published_at=pub_date,
                coupon_code=coupon_code,
                summary=summary or None,
                is_frontpage=is_frontpage,
                source="Slickdeals Frontpage" if is_frontpage else "Slickdeals",
            )
        )

    return deals


async def fetch_slickdeals(
    query: str | None = None, mode: str = "frontpage", limit: int = 24
) -> list[DealItem]:
    """Fetch live deals from Slickdeals RSS feed (frontpage, popular, or title search)."""
    clean_q = (query or "").strip()
    if clean_q:
        q = quote_plus(clean_q)
        # titleonly=1 ensures we only get deals whose product title matches the query
        rss_url = (
            f"https://slickdeals.net/newsearch.php?q={q}"
            "&searcharea=deals&searchin=first&titleonly=1&rss=1"
        )
        is_fp = False
    else:
        feed_mode = "popdeals" if mode == "popular" else "frontpage"
        rss_url = (
            f"https://slickdeals.net/newsearch.php?mode={feed_mode}"
            "&searcharea=deals&searchin=first&rss=1"
        )
        is_fp = feed_mode == "frontpage"

    try:
        async with httpx.AsyncClient(
            timeout=settings.request_timeout_seconds,
            follow_redirects=True,
            headers=_browser_headers(),
        ) as client:
            resp = await client.get(rss_url)
            resp.raise_for_status()
            items = parse_slickdeals_rss(resp.text, is_frontpage=is_fp, query=clean_q or None)
            return items[:limit]
    except Exception as exc:
        log.warning("Could not fetch Slickdeals feed (%s): %s", rss_url, exc)
        return []
