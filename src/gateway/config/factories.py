"""Factories that select interface implementations based on settings."""
from __future__ import annotations

from gateway.config.settings import settings
from gateway.interfaces.auth import AuthProvider
from gateway.interfaces.rate_limit import RateLimitStore
from gateway.interfaces.route_repo import RouteRepository


def build_rate_limit_store() -> RateLimitStore:
    """Return the rate-limit store implementation selected by settings.

    Returns:
        A memory-backed store for local dev, Redis-backed for production.
    """
    if settings.store_backend == "redis":
        from gateway.rate_limit.redis_store import RedisRateLimitStore
        return RedisRateLimitStore(settings.redis_url)
    from gateway.rate_limit.memory_store import InMemoryRateLimitStore
    return InMemoryRateLimitStore()


def build_auth_provider() -> AuthProvider:
    """Return the auth provider selected by settings.

    Raises:
        NotImplementedError: If OIDC is requested (stub only).
    """
    if settings.auth_backend == "oidc":
        raise NotImplementedError("OIDC provider not yet implemented")
    from gateway.auth.mock_provider import MockAuthProvider
    return MockAuthProvider(
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
    )


def build_route_repository() -> RouteRepository:
    """Return the route repository selected by settings."""
    if settings.route_repo_backend == "redis":
        from gateway.repositories.routes.redis_repo import RedisRouteRepository
        return RedisRouteRepository(settings.redis_url)
    if settings.route_repo_backend == "postgres":
        from gateway.repositories.routes.postgres_repo import PostgresRouteRepository
        return PostgresRouteRepository(settings.postgres_dsn)
    from gateway.repositories.routes.yaml_repo import YamlFileRouteRepository
    return YamlFileRouteRepository(settings.routes_file_path)