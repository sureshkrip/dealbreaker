"""API integration tests using an in-memory SQLite DB and a mocked scraper."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine
from sqlmodel.pool import StaticPool

from dealbreaker import db as db_module
from dealbreaker import scraper as scraper_module
from dealbreaker import services as services_module
from dealbreaker.config import settings
from dealbreaker.models import StockStatus
from dealbreaker.scraper import ScrapeResult

TOKEN = "test-token"


@pytest.fixture
def client(monkeypatch):
    settings.admin_token = TOKEN
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db_module, "engine", engine)

    # Fake scraper: return a fixed result so tests don't hit the network.
    price_box = {"price": 100.0}

    async def fake_scrape(url, strategy=None):
        return ScrapeResult(
            title="Test Product",
            price=price_box["price"],
            image="https://img.example/p.jpg",
            availability=StockStatus.in_stock,
        )

    # Patch scrape everywhere it's imported.
    monkeypatch.setattr(scraper_module, "scrape", fake_scrape)
    monkeypatch.setattr(services_module, "scrape", fake_scrape)
    import dealbreaker.api.products as products_api

    monkeypatch.setattr(products_api, "scrape", fake_scrape)

    async def fake_fetch_slickdeals(query=None, mode="frontpage", limit=20):
        return []

    monkeypatch.setattr(services_module, "fetch_slickdeals", fake_fetch_slickdeals)

    # Build an app that uses our test engine session.
    from fastapi import FastAPI
    from sqlmodel import Session

    from dealbreaker.api import api_router
    from dealbreaker.db import get_session

    app = FastAPI()
    app.include_router(api_router)

    def get_test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session

    c = TestClient(app)
    c.headers.update({"Authorization": f"Bearer {TOKEN}"})
    c.price_box = price_box  # expose so tests can change the scraped price
    return c


def test_auth_required(client):
    r = client.get("/api/products", headers={"Authorization": ""})
    assert r.status_code == 401


def test_create_product_scrapes_and_stores_price(client):
    r = client.post("/api/products", json={"url": "https://shop.example/item"})
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["title"] == "Test Product"
    assert data["best_price"] == 100.0
    assert len(data["urls"]) == 1
    assert data["urls"][0]["latest_price"] == 100.0


def test_price_history_appends_on_refresh(client):
    pid = client.post("/api/products", json={"url": "https://shop.example/item"}).json()["id"]
    url_id = client.get(f"/api/products/{pid}").json()["urls"][0]["id"]

    client.price_box["price"] = 80.0
    client.post(f"/api/products/urls/{url_id}/refresh")

    history = client.get(f"/api/products/{pid}/prices").json()
    points = history[str(url_id)]
    assert [p["price"] for p in points] == [100.0, 80.0]


def test_target_notification_marks_notified(client, monkeypatch):
    sent = []
    monkeypatch.setattr(
        "dealbreaker.services.notify.send",
        lambda title, message, url=None: sent.append((title, message)) or True,
    )
    pid = client.post(
        "/api/products",
        json={"url": "https://shop.example/item", "notify_price": 90.0},
    ).json()["id"]
    url_id = client.get(f"/api/products/{pid}").json()["urls"][0]["id"]

    client.price_box["price"] = 85.0
    client.post(f"/api/products/urls/{url_id}/refresh")

    assert len(sent) == 1
    assert "Test Product" in sent[0][1]


def test_create_product_by_name_and_manual_price(client, monkeypatch):
    from dealbreaker.deals import DealItem

    async def fake_deals(query=None, mode="frontpage", limit=20):
        return [
            DealItem(
                id="sd-1",
                title="Sony WH-1000XM5 Headphones $278 at Amazon",
                url="https://slickdeals.net/f/1-sony-xm5-amazon",
                price=278.0,
                store_name="Amazon",
                image="https://img.example/xm5.jpg",
            ),
            DealItem(
                id="sd-2",
                title="Sony WH-1000XM5 Headphones $299 at Best Buy",
                url="https://slickdeals.net/f/2-sony-xm5-bestbuy",
                price=299.0,
                store_name="Best Buy",
            ),
        ]

    monkeypatch.setattr(services_module, "fetch_slickdeals", fake_deals)

    r = client.post(
        "/api/products",
        json={
            "title": "Sony WH-1000XM5",
            "notify_price": 280.0,
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["title"] == "Sony WH-1000XM5"
    assert data["best_price"] == 278.0
    assert data["target_hit"] is True
    assert set(data["store_names"]) == {"Amazon", "Best Buy"}
    assert len(data["urls"]) == 2


def test_price_stats_and_manual_price_update(client):
    pid = client.post(
        "/api/products",
        json={"url": "https://shop.example/item", "notify_price": 75.0},
    ).json()["id"]
    url_id = client.get(f"/api/products/{pid}").json()["urls"][0]["id"]

    # Record a lower manual price
    r = client.post(f"/api/products/urls/{url_id}/price", json={"price": 70.0})
    assert r.status_code == 200
    assert r.json()["latest_price"] == 70.0

    prod = client.get(f"/api/products/{pid}").json()
    assert prod["best_price"] == 70.0
    assert prod["lowest_price"] == 70.0
    assert prod["highest_price"] == 100.0
    assert prod["price_change"] == -30.0
    assert prod["price_change_percent"] == -30.0
    assert prod["target_hit"] is True
