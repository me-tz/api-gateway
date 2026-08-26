"""Error handling when the upstream backend is unreachable."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_unreachable_backend_returns_502_or_504(client, admin_headers) -> None:
    c, _ = client
    route = {
        "id": "d",
        "path": "/d/*",
        "methods": ["GET"],
        "target": "http://127.0.0.1:1",
        "middlewares": [],
        "middleware_config": {},
    }
    await c.post("/admin/routes", json=route, headers=admin_headers)
    r = await c.get("/d/x")
    assert r.status_code in (502, 504)
    body = r.json()
    assert "error" in body
    text = r.text.lower()
    assert "traceback" not in text
    assert "127.0.0.1" not in text