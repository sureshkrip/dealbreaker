# Dealbreaker — backend

FastAPI backend for Dealbreaker, a self-hosted price tracker (a Python/FastAPI port of
[PriceBuddy](https://github.com/jez500/pricebuddy)).

## Dev

```bash
uv sync
uv run dealbreaker serve        # starts uvicorn on :8000
uv run dealbreaker seed         # seed admin token + starter stores
uv run pytest
```

Config via env (see `src/dealbreaker/config.py`): `DATABASE_URL`, `ADMIN_TOKEN`,
`SCRAPE_INTERVAL_MINUTES`, `NTFY_URL`, `CORS_ORIGINS`. Defaults to SQLite at
`./dealbreaker.db` when `DATABASE_URL` is unset.
