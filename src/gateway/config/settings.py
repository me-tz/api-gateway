"""Runtime settings loaded from environment variables and .env files."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration object.

    Attributes:
        store_backend: Rate-limit store implementation.
        auth_backend: Authentication provider implementation.
        route_repo_backend: Route repository implementation.
        redis_url: Redis connection URL.
        postgres_dsn: Postgres DSN for the postgres route repo.
        routes_file_path: Path to the YAML routes file (file backend).
        jwt_secret: Symmetric secret for HS256 mock JWTs.
        jwt_algorithm: JWT signing algorithm.
        jwt_issuer: Expected ``iss`` claim.
        jwt_audience: Expected ``aud`` claim.
        rate_limit_fail_mode: Behavior when the rate-limit store is unreachable.
        backend_timeout_seconds: Upstream read/write timeout.
        backend_connect_timeout_seconds: Upstream TCP connect timeout.
        log_level: Log-level name (DEBUG/INFO/WARNING/ERROR).
        log_format: ``json`` for production, ``pretty`` for local dev.
        admin_token: Static token required for Admin API endpoints.
        strict_validation: If True, middleware-list validation errors abort
            startup instead of just logging warnings. Reload-time issues are
            always downgraded to warnings so a bad admin update cannot kill
            a running gateway.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="GATEWAY_", extra="ignore"
    )

    store_backend: Literal["memory", "redis"] = "memory"
    auth_backend: Literal["mock", "oidc"] = "mock"
    route_repo_backend: Literal["file", "redis", "postgres"] = "file"

    redis_url: str = "redis://localhost:6379/0"
    postgres_dsn: str = "postgresql://gateway:gateway@localhost:5432/gateway"
    routes_file_path: Path = Path("./routes.yaml")

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "mock-auth"
    jwt_audience: str = "api-gateway"

    rate_limit_fail_mode: Literal["open", "closed"] = "open"
    backend_timeout_seconds: float = 30.0
    backend_connect_timeout_seconds: float = 5.0

    log_level: str = "INFO"
    log_format: Literal["json", "pretty"] = "pretty"

    admin_token: str = "admin-dev-token"

    strict_validation: bool = False


settings = Settings()