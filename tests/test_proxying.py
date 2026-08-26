"""Proxy path rewrite and body forwarding tests."""
from __future__ import annotations

import pytest
import respx
from httpx import Response


@pytest.mark.asyncio
async def test_strip_prefix_and_query_forwarded(client, admin_headers) -> None:
    c, _ = client
    route = {
        "id": "e",
        "path": "/echo/*",
        "methods": ["GET"],
        "target": "http://backend.test",
        "strip_prefix": "/echo",
        "middlewares": [],
        "middleware_config": {},
    }
    await c.post("/admin/routes", json=route, headers=admin_headers)

    with respx.mock(assert_all_called=True) as mock:
        route_mock = mock.get("http://backend.test/users/1").mock(
            return_value=Response(200, json={"ok": True})
        )
        r = await c.get("/echo/users/1?flag=1")
        assert r.status_code == 200
        assert r.json() == {"ok": True}
        assert route_mock.calls.last.request.url.query == b"flag=1"


@pytest.mark.asyncio
async def test_post_body_forwarded(client, admin_headers) -> None:
    c, _ = client
    route = {
        "id": "e",
        "path": "/echo/*",
        "methods": ["POST"],
        "target": "http://backend.test",
        "strip_prefix": "/echo",
        "middlewares": [],
        "middleware_config": {},
    }
    await c.post("/admin/routes", json=route, headers=admin_headers)

    with respx.mock() as mock:
        m = mock.post("http://backend.test/thing").mock(
            return_value=Response(201, json={"created": True})
        )
        r = await c.post("/echo/thing", json={"a": 1})
        assert r.status_code == 201
        assert b'"a"' in m.calls.last.request.content