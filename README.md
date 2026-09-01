# Dealbreaker

A self-hosted price tracker — a Python/FastAPI + React port of
[PriceBuddy](https://github.com/jez500/pricebuddy). Paste a product URL, Dealbreaker
scrapes the title/price/image/availability, keeps price history, re-checks on a
schedule, compares listings across stores, and notifies you (via ntfy) when a target
price or percentage drop is hit.

## Stack

- **Backend** (`backend/`): FastAPI, SQLModel, httpx + selectolax scraping, APScheduler.
- **Frontend** (`frontend/`): React + Vite + TypeScript, Recharts price history.
- **Deploy**: Docker Compose (Postgres + backend + nginx-served frontend), designed for
  [Coolify](https://coolify.io).

## Architecture

A **Product** has many **Urls** (one per store listing). Each scrape appends a **Price**
row to a Url → price history. A **Store** owns the scrape strategy for its domain(s):
per-field `{type, value}` extractors (`selector` / `regex` / `json` / `schema.org`),
with a schema.org + OpenGraph fallback so common stores work with no configuration.

## Run locally

```bash
# Backend only (SQLite, auto-created)
cd backend
uv sync
ADMIN_TOKEN=devtoken uv run dealbreaker seed
ADMIN_TOKEN=devtoken uv run dealbreaker serve      # http://localhost:8000

# Frontend (proxies /api → :8000)
cd ../frontend
npm install
npm run dev                                         # http://localhost:5173

# Or the whole stack with Docker:
ADMIN_TOKEN=devtoken docker compose up --build      # http://localhost:8090
```

Sign in with the `ADMIN_TOKEN` value.

## Configuration (env)

| Variable                  | Default                     | Purpose                                  |
| ------------------------- | --------------------------- | ---------------------------------------- |
| `DATABASE_URL`            | `sqlite:///./dealbreaker.db`| Postgres URL in production               |
| `ADMIN_TOKEN`             | `change-me`                 | Bearer token for the single-user auth    |
| `SCRAPE_INTERVAL_MINUTES` | `180`                       | How often the scheduler re-scrapes URLs  |
| `NTFY_URL`                | *(empty)*                   | ntfy topic URL for target notifications  |
| `CORS_ORIGINS`            | `*`                         | Allowed CORS origins                     |

## Deploy on Coolify

1. Connect this repo in Coolify → **Docker Compose** build pack.
2. Set env: `ADMIN_TOKEN`, `POSTGRES_PASSWORD`, `NTFY_URL`.
3. Assign the domain to the **frontend** service (port 80); Traefik issues TLS.
4. Deploy. The backend seeds default stores on start.

## Tests

```bash
cd backend && uv run pytest
```

## Scope

MVP of the core loop. Deferred from PriceBuddy: browser extension, SearXNG search,
AI-assisted extraction/self-healing, multi-user/tags, unit-price factors, richer
insights, and the full notification-channel matrix.

Ported from PriceBuddy (GPL-3.0 with a non-commercial clause); this is for personal,
self-hosted use.
