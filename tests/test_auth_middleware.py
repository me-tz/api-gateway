"""Auth middleware behavior tests."""
from __future__ import annotations

import pytest

from gateway.auth.mock_provider import MockAuthProvider


def _auth_route() -> dict:
    return {
        "id": "u",
        "path": "/api/*",
        "methods": ["GET"],
        "target": "http://localhost:9999",
        "middlewares": ["auth"],
        "middleware_config": {"auth": {"required": True, "scopes": ["users:read"]}},
    }


@pytest.mark.asyncio
async def test_missing_token_returns_401(client, admin_headers) -> None:
    c, _ = client
    r = await c.post("/admin/routes", json=_auth_route(), headers=admin_headers)
    assert r.status_code == 200
    r = await c.get("/api/x")
    assert r.status_code == 401
    assert "error" in r.json()


@pytest.mark.asyncio
async def test_invalid_token_returns_401(client, admin_headers) -> None:
    c, _ = client
    await c.post("/admin/routes", json=_auth_route(), headers=admin_headers)
    r = await c.get("/api/x", headers={"authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_missing_scope_returns_403(client, admin_headers) -> None:
    c, _ = client
    await c.post("/admin/routes", json=_auth_route(), headers=admin_headers)
    tok = MockAuthProvider("test-secret", "HS256", "mock-auth", "api-gateway").issue(
        "u", ["other:scope"]
    )
    r = await c.get("/api/x", headers={"authorization": f"Bearer {tok}"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_valid_token_passes_auth(client, admin_headers, jwt_token) -> None:
    c, _ = client
    await c.post("/admin/routes", json=_auth_route(), headers=admin_headers)
    # Backend is unreachable so we get 502, but importantly not 401/403.
    r = await c.get("/api/x", headers={"authorization": f"Bearer {jwt_token}"})
    assert r.status_code in (502, 504)