"""Shared long-lived HTTP client with tuned pool and timeouts."""
from __future__ import annotations

import httpx

from gateway.config.settings import settings


def build_http_client() -> httpx.AsyncClient:
    """Return a configured async client for upstream calls.

    Returns:
        An ``httpx.AsyncClient`` with connection pooling and timeouts.
    """
    limits = httpx.Limits(
        max_connections=200,
        max_keepalive_connections=100,
        keepalive_expiry=30.0,
    )
    timeout = httpx.Timeout(
        connect=settings.backend_connect_timeout_seconds,
        read=settings.backend_timeout_seconds,
        write=settings.backend_timeout_seconds,
        pool=5.0,
    )
    return httpx.AsyncClient(limits=limits, timeout=timeout, follow_redirects=False)