"""Admin API CRUD tests."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_admin_requires_token(client) -> None:
    c, _ = client
    r = await c.get("/admin/routes")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_admin_crud_and_reload(client, admin_headers) -> None:
    c, _ = client

    r = await c.get("/admin/routes", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == []

    route = {
        "id": "x",
        "path": "/x/*",
        "methods": ["GET"],
        "target": "http://localhost:9999",
        "middlewares": [],
        "middleware_config": {},
    }
    assert (await c.post("/admin/routes", json=route, headers=admin_headers)).status_code == 200
    assert len((await c.get("/admin/routes", headers=admin_headers)).json()) == 1

    reload_r = await c.post("/admin/reload", headers=admin_headers)
    assert reload_r.status_code == 200
    assert reload_r.json()["total"] == 1

    assert (await c.delete("/admin/routes/x", headers=admin_headers)).status_code == 200
    assert (await c.get("/admin/routes", headers=admin_headers)).json() == []