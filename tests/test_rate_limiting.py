"""Rate-limit middleware tests."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_rate_limit_denies_after_capacity(client, admin_headers) -> None:
    c, _ = client
    route = {
        "id": "rl",
        "path": "/rl/*",
        "methods": ["GET"],
        "target": "http://localhost:9999",
        "middlewares": ["rate_limit"],
        "middleware_config": {
            "rate_limit": {"capacity": 2, "refill_per_second": 0.001}
        },
    }
    await c.post("/admin/routes", json=route, headers=admin_headers)

    # First two allowed (upstream will 502 but rate-limit did allow).
    r1 = await c.get("/rl/a")
    r2 = await c.get("/rl/a")
    r3 = await c.get("/rl/a")

    assert r1.status_code in (502, 504)
    assert r2.status_code in (502, 504)
    assert r3.status_code == 429
    assert r3.headers["X-RateLimit-Limit"] == "2"
    assert "Retry-After" in r3.headers
    assert "X-RateLimit-Remaining" in r3.headers
    assert "X-RateLimit-Reset" in r3.headers


@pytest.mark.asyncio
async def test_rate_limit_headers_on_allowed(client, admin_headers) -> None:
    c, _ = client
    route = {
        "id": "rl2",
        "path": "/rl2/*",
        "methods": ["GET"],
        "target": "http://localhost:9999",
        "middlewares": ["rate_limit"],
        "middleware_config": {
            "rate_limit": {"capacity": 100, "refill_per_second": 10.0}
        },
    }
    await c.post("/admin/routes", json=route, headers=admin_headers)
    r = await c.get("/rl2/a")
    assert "X-RateLimit-Limit" in r.headers
    assert r.headers["X-RateLimit-Limit"] == "100"