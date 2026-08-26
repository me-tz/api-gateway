"""Header handling tests."""
from __future__ import annotations

import pytest
import respx
from httpx import Response


@pytest.mark.asyncio
async def test_hop_by_hop_stripped_and_forwarded_headers_added(
    client, admin_headers
) -> None:
    c, _ = client
    route = {
        "id": "e",
        "path": "/e/*",
        "methods": ["GET"],
        "target": "http://backend.test",
        "strip_prefix": "/e",
        "middlewares": [],
        "middleware_config": {},
    }
    await c.post("/admin/routes", json=route, headers=admin_headers)

    captured: dict = {}

    def _capture(request):
        captured["headers"] = dict(request.headers)
        return Response(200, json={"ok": True})

    with respx.mock() as mock:
        mock.get("http://backend.test/foo").mock(side_effect=_capture)
        r = await c.get(
            "/e/foo",
            headers={"connection": "close", "x-custom": "yes"},
        )
        assert r.status_code == 200
        assert "connection" not in captured["headers"]
        assert captured["headers"].get("x-custom") == "yes"
        assert "x-request-id" in captured["headers"]
        assert "x-forwarded-for" in captured["headers"]
        assert "x-real-ip" in captured["headers"]
        assert r.headers.get("X-Request-ID")
        assert r.headers.get("X-Gateway-Duration-Ms")


@pytest.mark.asyncio
async def test_request_id_propagated_when_supplied(client, admin_headers) -> None:
    c, _ = client
    route = {
        "id": "e",
        "path": "/e/*",
        "methods": ["GET"],
        "target": "http://backend.test",
        "strip_prefix": "/e",
        "middlewares": [],
        "middleware_config": {},
    }
    await c.post("/admin/routes", json=route, headers=admin_headers)

    captured: dict = {}

    def _capture(request):
        captured["headers"] = dict(request.headers)
        return Response(200, json={"ok": True})

    with respx.mock() as mock:
        mock.get("http://backend.test/x").mock(side_effect=_capture)
        r = await c.get("/e/x", headers={"x-request-id": "trace-abc"})
        assert captured["headers"]["x-request-id"] == "trace-abc"
        assert r.headers["X-Request-ID"] == "trace-abc"