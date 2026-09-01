"""Pydantic request/response models for the API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .models import StockStatus


class ProductCreate(BaseModel):
    url: str
    notify_price: float | None = None
    notify_percent: float | None = None


class ProductUpdate(BaseModel):
    title: str | None = None
    favourite: bool | None = None
    notify_price: float | None = None
    notify_percent: float | None = None


class UrlAdd(BaseModel):
    url: str


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
    last_scraped_at: datetime | None


class ProductOut(BaseModel):
    id: int
    title: str
    image: str | None
    favourite: bool
    notify_price: float | None
    notify_percent: float | None
    best_price: float | None
    urls: list[UrlOut]


class ProductListItem(BaseModel):
    id: int
    title: str
    image: str | None
    favourite: bool
    best_price: float | None
    store_count: int
