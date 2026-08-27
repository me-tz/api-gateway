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
os.environ["GATEWAY_STRICT_VALIDATION"] = "false"

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from gateway.auth.mock_provider import MockAuthProvider


@pytest.fixture
async def client(tmp_path, monkeypatch):
    """Yield an httpx AsyncClient bound to a fresh gateway app.

    Patches the settings object directly so the temp routes file is used
    regardless of when Settings() was instantiated.

    Args:
        tmp_path: Pytest-provided temp directory.
        monkeypatch: Pytest monkeypatch fixture.

    Yields:
        A tuple of (AsyncClient, FastAPI app).
    """
    routes_file = tmp_path / "routes.yaml"
    routes_file.write_text("routes: []")

    # Path the settings singleton directly.
    from gateway.config.settings import settings
    monkeypatch.setattr(settings, "routes_file_path", routes_file)

    import importlib
    import gateway.main as main_mode
    importlib.reload(main_mode)

    # Run the lifespan so app.state is populated before any test runs.
    async with LifespanManager(main_mode.app):
        async with AsyncClient(
                transport=ASGITransport(app=main_mode.app),
                base_url="http://test"
        ) as c:
            yield c, main_mode.app


@pytest.fixture
def jwt_token() -> str:
    """Return a signed JWT with the default test scope."""
    provider = MockAuthProvider("test-secret", "HS256", "mock-auth", "api-gateway")
    return provider.issue("user-1", ["users:read"])


@pytest.fixture
def admin_headers() -> dict[str, str]:
    """Headers required for the Admin API."""
    return {"x-admin-token": "admin-dev-token"}
