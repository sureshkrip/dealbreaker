"""Database models, mirroring PriceBuddy's core schema.

A Product has many Urls (one per store listing). Each scrape appends a Price row to
a Url, giving the price history. A Store owns the scrape strategy for its domain(s).
"""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class StockStatus(StrEnum):
    in_stock = "in_stock"
    pre_order = "pre_order"
    back_order = "back_order"
    special_order = "special_order"
    out_of_stock = "out_of_stock"
    discontinued = "discontinued"
    unknown = "unknown"


class Store(SQLModel, table=True):
    __tablename__ = "stores"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    slug: str = Field(index=True)
    initials: str | None = None
    # List of bare domains this store matches, e.g. ["amazon.com", "amazon.com.au"].
    domains: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    # Per-field extractors: {"title": {"type": "selector", "value": "h1"}, "price": {...}}
    scrape_strategy: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    urls: list["Url"] = Relationship(back_populates="store")


class Product(SQLModel, table=True):
    __tablename__ = "products"

    id: int | None = Field(default=None, primary_key=True)
    title: str
    image: str | None = None
    favourite: bool = True
    # Optional keyword query to monitor deal feeds (e.g. Slickdeals) for this product.
    search_query: str | None = None
    category: str | None = None
    # Notify when any listing drops to/below this absolute price.
    notify_price: float | None = None
    # Notify on a percentage drop from the highest recorded price.
    notify_percent: float | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    urls: list["Url"] = Relationship(
        back_populates="product",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Url(SQLModel, table=True):
    __tablename__ = "urls"

    id: int | None = Field(default=None, primary_key=True)
    url: str
    product_id: int = Field(foreign_key="products.id", index=True)
    store_id: int = Field(foreign_key="stores.id", index=True)
    availability: StockStatus = Field(default=StockStatus.unknown)
    last_error: str | None = None
    last_scraped_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)

    product: "Product" = Relationship(back_populates="urls")
    store: "Store" = Relationship(back_populates="urls")
    prices: list["Price"] = Relationship(
        back_populates="url",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Price(SQLModel, table=True):
    __tablename__ = "prices"

    id: int | None = Field(default=None, primary_key=True)
    price: float
    url_id: int = Field(foreign_key="urls.id", index=True)
    store_id: int = Field(foreign_key="stores.id", index=True)
    notified: bool = False
    created_at: datetime = Field(default_factory=utcnow, index=True)

    url: "Url" = Relationship(back_populates="prices")
