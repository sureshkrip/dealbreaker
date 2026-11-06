"""Pydantic request/response models for the API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .models import StockStatus


class ProductCreate(BaseModel):
    url: str | None = None
    title: str | None = None
    image: str | None = None
    initial_price: float | None = None
    search_query: str | None = None
    category: str | None = None
    notify_price: float | None = None
    notify_percent: float | None = None


class ProductUpdate(BaseModel):
    title: str | None = None
    image: str | None = None
    favourite: bool | None = None
    search_query: str | None = None
    category: str | None = None
    notify_price: float | None = None
    notify_percent: float | None = None


class UrlPreviewRequest(BaseModel):
    url: str


class UrlPreviewOut(BaseModel):
    url: str
    title: str | None = None
    price: float | None = None
    image: str | None = None
    availability: StockStatus = StockStatus.unknown
    store_name: str
    error: str | None = None


class StoreTestRequest(BaseModel):
    url: str
    scrape_strategy: dict | None = None


class UrlAdd(BaseModel):
    url: str
    price: float | None = None


class ManualPriceAdd(BaseModel):
    price: float


class StoreOut(BaseModel):
    id: int
    name: str
    slug: str
    domains: list[str]
    scrape_strategy: dict

    model_config = ConfigDict(from_attributes=True)


class StoreUpdate(BaseModel):
    name: str | None = None
    domains: list[str] | None = None
    scrape_strategy: dict | None = None


class PricePoint(BaseModel):
    price: float
    created_at: datetime


class UrlOut(BaseModel):
    id: int
    url: str
    store_id: int
    store_name: str
    availability: StockStatus
    latest_price: float | None
    last_error: str | None = None
    last_scraped_at: datetime | None


class ProductOut(BaseModel):
    id: int
    title: str
    image: str | None
    favourite: bool
    search_query: str | None = None
    category: str | None = None
    notify_price: float | None
    notify_percent: float | None
    best_price: float | None
    lowest_price: float | None = None
    highest_price: float | None = None
    price_change: float | None = None
    price_change_percent: float | None = None
    target_hit: bool = False
    store_names: list[str] = []
    last_scraped_at: datetime | None = None
    urls: list[UrlOut]


class ProductListItem(BaseModel):
    id: int
    title: str
    image: str | None
    favourite: bool
    search_query: str | None = None
    category: str | None = None
    notify_price: float | None = None
    notify_percent: float | None = None
    best_price: float | None
    lowest_price: float | None = None
    highest_price: float | None = None
    price_change: float | None = None
    price_change_percent: float | None = None
    target_hit: bool = False
    store_count: int
    store_names: list[str] = []
    last_scraped_at: datetime | None = None


class DealOut(BaseModel):
    id: str
    title: str
    url: str
    price: float | None = None
    original_price: float | None = None
    discount_percent: int | None = None
    store_name: str
    image: str | None = None
    published_at: str | None = None
    coupon_code: str | None = None
    summary: str | None = None
    is_frontpage: bool = False
    source: str = "Slickdeals"
