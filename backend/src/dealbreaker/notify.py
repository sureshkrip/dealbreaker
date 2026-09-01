"""Notifications. MVP supports ntfy (https://ntfy.sh). No-op when NTFY_URL is unset."""

from __future__ import annotations

import logging

import httpx

from .config import settings

log = logging.getLogger("dealbreaker.notify")


def send(title: str, message: str, url: str | None = None) -> bool:
    """Send an ntfy notification. Returns True if delivered, False if skipped/failed."""
    if not settings.ntfy_url:
        log.info("notify skipped (NTFY_URL unset): %s — %s", title, message)
        return False
    headers = {"Title": title}
    if url:
        headers["Click"] = url
    try:
        resp = httpx.post(
            settings.ntfy_url,
            data=message.encode("utf-8"),
            headers=headers,
            timeout=10.0,
        )
        resp.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        log.warning("ntfy notification failed: %s", exc)
        return False
