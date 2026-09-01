"""Tests for the scraping strategy engine and price/title helpers."""

from dealbreaker.models import StockStatus
from dealbreaker.scraper import (
    clean_title,
    extract,
    map_availability,
    parse_price,
)

SCHEMA_ORG_HTML = """
<html><head>
<title>Wireless Mouse | MegaStore</title>
<meta property="og:image" content="https://img.example/mouse.jpg">
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"Acme Wireless Mouse",
 "image":"https://img.example/acme.jpg",
 "offers":{"@type":"Offer","price":"29.99","priceCurrency":"USD",
 "availability":"https://schema.org/InStock"}}
</script>
</head><body><h1 class="pdp-title">Acme Wireless Mouse</h1>
<span class="price">$29.99</span></body></html>
"""

SELECTOR_HTML = """
<html><head><title>Ignore me</title></head>
<body>
  <h1 id="productTitle">Super Widget 3000</h1>
  <div class="a-price"><span class="a-offscreen">$1,299.00</span></div>
  <img id="landingImage" src="https://img.example/widget.jpg">
</body></html>
"""


def test_parse_price_variants():
    assert parse_price("$1,299.00") == 1299.00
    assert parse_price("1.299,00 €") == 1299.00
    assert parse_price("12,99") == 12.99
    assert parse_price("29.99") == 29.99
    assert parse_price("free") is None
    assert parse_price(49.5) == 49.5


def test_clean_title_strips_store_suffix():
    assert clean_title("Wireless Mouse | MegaStore") == "Wireless Mouse"
    assert clean_title("  Multi   space   name ") == "Multi space name"


def test_map_availability():
    assert map_availability("https://schema.org/InStock") == StockStatus.in_stock
    assert map_availability("https://schema.org/OutOfStock") == StockStatus.out_of_stock
    assert map_availability("PreOrder") == StockStatus.pre_order
    assert map_availability(None) == StockStatus.unknown


def test_extract_schema_org_fallback():
    result = extract(SCHEMA_ORG_HTML)
    assert result.title == "Acme Wireless Mouse"
    assert result.price == 29.99
    assert result.image == "https://img.example/acme.jpg"
    assert result.availability == StockStatus.in_stock


def test_extract_with_selector_strategy():
    strategy = {
        "title": {"type": "selector", "value": "#productTitle"},
        "price": {"type": "selector", "value": ".a-price .a-offscreen"},
        "image": {"type": "selector", "value": "#landingImage|src"},
    }
    result = extract(SELECTOR_HTML, strategy)
    assert result.title == "Super Widget 3000"
    assert result.price == 1299.00
    assert result.image == "https://img.example/widget.jpg"


def test_extract_with_regex_strategy():
    strategy = {"price": {"type": "regex", "value": r"\$([0-9,]+\.[0-9]{2})"}}
    result = extract(SELECTOR_HTML, strategy)
    assert result.price == 1299.00
