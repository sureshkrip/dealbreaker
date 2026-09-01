# Backend image: FastAPI served by uvicorn.
FROM python:3.13-slim

# uv for fast, reproducible installs.
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (better layer caching).
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

# Seed default stores (idempotent), then start the API.
CMD ["sh", "-c", "dealbreaker seed && uvicorn dealbreaker.main:app --host 0.0.0.0 --port 8000"]
