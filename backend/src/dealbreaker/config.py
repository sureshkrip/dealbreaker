"""Application configuration, loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database. Defaults to a local SQLite file for dev; set to a Postgres URL in prod.
    # Example: postgresql+psycopg://user:pass@host:5432/dealbreaker
    database_url: str = "sqlite:///./dealbreaker.db"

    # Single-user auth token. Clients send it as `Authorization: Bearer <token>`.
    admin_token: str = "change-me"

    # How often the scheduler re-scrapes every tracked URL.
    scrape_interval_minutes: int = 180

    # ntfy topic URL for target-price notifications (e.g. https://ntfy.sh/my-topic).
    ntfy_url: str = ""

    # Comma-separated list of allowed CORS origins for the frontend.
    cors_origins: str = "*"

    # HTTP client settings for scraping.
    request_timeout_seconds: float = 20.0
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
