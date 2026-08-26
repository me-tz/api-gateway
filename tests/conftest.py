"""Pytest fixtures and environment for the gateway test suite."""
from __future__ import annotations

import os

os.environ["GATEWAY_STORE_BACKEND"] = "memory"
os.environ["GATEWAY_AUTH_BACKEND"] = "mock"
os.environ["GATEWAY_ROUTE_REPO_BACKEND"] = "file"
os.environ["GATEWAY_JWT_SECRET"] = "test-secret"
os.environ["GATEWAY_JWT_ISSUER"] = "mock-auth"
os.environ["GATEWAY_JWT_AUDIENCE"] = "api-gateway"
os.environ["GATEWAY_ADMIN_TOKEN"] = "admin-dev-token"

import pytest
from httpx import ASGITransport, AsyncClient

from gateway.auth.mock_provider import MockAuthProvider


@pytest.fixture
async def client(tmp_path, monkeypatch):
    """Yield an httpx AsyncClient bound to a fresh gateway app.

    Args:
        tmp_path: Pytest-provided temp directory.
        monkeypatch: Pytest monkeypatch fixture.

    Yields:
        A tuple of (AsyncClient, FastAPI app).
    """
    routes = tmp_path / "routes.yaml"
    routes.write_text("routes: []")
    monkeypatch.setenv("GATEWAY_ROUTES_FILE_PATH", str(routes))

    from importlib import reload
    from gateway import main as m
    reload(m)

    async with AsyncClient(
        transport=ASGITransport(app=m.app), base_url="http://test"
    ) as c:
        yield c, m.app


@pytest.fixture
def jwt_token() -> str:
    """Return a signed JWT with the default test scope."""
    provider = MockAuthProvider("test-secret", "HS256", "mock-auth", "api-gateway")
    return provider.issue("user-1", ["users:read"])


@pytest.fixture
def admin_headers() -> dict[str, str]:
    """Headers required for the Admin API."""
    return {"x-admin-token": "admin-dev-token"}