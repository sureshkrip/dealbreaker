"""Tests for the scraping strategy engine and price/title helpers."""

from dealbreaker.deals import parse_slickdeals_rss
from dealbreaker.models import StockStatus
from dealbreaker.scraper import (
    clean_title,
    extract,
    map_availability,
    parse_price,
)
from dealbreaker.stores import fallback_title_from_url

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


def test_comma_separated_fallback_selectors():
    strategy = {
        "title": {"type": "selector", "value": "#missingTitle, #productTitle"},
        "price": {"type": "selector", "value": ".missing-price, .a-price .a-offscreen"},
        "image": {"type": "selector", "value": "#missingImg|src, #landingImage|src"},
    }
    result = extract(SELECTOR_HTML, strategy)
    assert result.title == "Super Widget 3000"
    assert result.price == 1299.00
    assert result.image == "https://img.example/widget.jpg"


def test_fallback_title_from_url():
    url = "https://www.amazon.com/Sony-WH-1000XM5-Canceling-Headphones/dp/B09XS7JWHH"
    assert fallback_title_from_url(url) == "Sony Wh 1000Xm5 Canceling Headphones"


def test_parse_slickdeals_rss():
    sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
      <channel>
        <item>
          <title><![CDATA[Sony WH-1000XM5 Wireless Headphones $278 (Reg. $399) at Amazon]]></title>
          <link>https://slickdeals.net/f/12345-sony-wh-1000xm5</link>
          <guid>sd-12345</guid>
          <pubDate>Fri, 06 Nov 2026 12:00:00 GMT</pubDate>
          <description><![CDATA[
            <img src="https://img.example/xm5.jpg" /> Great deal with code AUDIO20
          ]]></description>
        </item>
      </channel>
    </rss>
    """
    deals = parse_slickdeals_rss(sample_xml, is_frontpage=True)
    assert len(deals) == 1
    d = deals[0]
    assert d.price == 278.0
    assert d.original_price == 399.0
    assert d.discount_percent == 30
    assert d.store_name == "Amazon"
    assert d.image == "https://img.example/xm5.jpg"
    assert d.coupon_code == "AUDIO20"
    assert d.is_frontpage is True
