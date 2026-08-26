"""Pydantic models describing route configuration."""
from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, Field, HttpUrl, model_validator


class HealthCheckConfig(BaseModel):
    """Health check parameters for a backend.

    Attributes:
        path: Path to probe on the backend.
        interval_seconds: Delay between probes.
        timeout_seconds: Per-probe timeout.
        unhealthy_threshold: Consecutive failures to mark unhealthy.
        healthy_threshold: Consecutive successes to mark healthy.
    """

    path: str = "/health"
    interval_seconds: float = 10.0
    timeout_seconds: float = 2.0
    unhealthy_threshold: int = 3
    healthy_threshold: int = 2


class CircuitBreakerConfig(BaseModel):
    """Circuit breaker parameters for a backend."""

    failure_threshold: int = 5
    cooldown_seconds: float = 30.0
    half_open_max_calls: int = 1


class AuthMiddlewareConfig(BaseModel):
    """Auth middleware per-route configuration."""

    required: bool = True
    scopes: list[str] = Field(default_factory=list)


class RateLimitMiddlewareConfig(BaseModel):
    """Rate-limit middleware per-route configuration."""

    capacity: int = 100
    refill_per_second: float = 1.0


class MiddlewareConfig(BaseModel):
    """Aggregate middleware configuration."""

    auth: AuthMiddlewareConfig | None = None
    rate_limit: RateLimitMiddlewareConfig | None = None


class Route(BaseModel):
    """A single routing rule.

    Supports either a single ``target`` or a ``targets`` list. Internally
    both are normalized into ``targets`` so downstream code is uniform.
    """

    id: str
    path: str
    methods: list[str] = Field(default_factory=lambda: ["GET"])
    target: HttpUrl | None = None
    targets: list[HttpUrl] = Field(default_factory=list)
    load_balancer: Literal["round_robin"] = "round_robin"
    strip_prefix: str | None = None
    add_prefix: str | None = None
    enabled: bool = True
    priority: int = 0
    middlewares: list[str] = Field(default_factory=list)
    middleware_config: MiddlewareConfig = Field(default_factory=MiddlewareConfig)
    health_check: HealthCheckConfig | None = None
    circuit_breaker: CircuitBreakerConfig | None = None

    @model_validator(mode="after")
    def _normalize_targets(self) -> Self:
        """Ensure exactly one form is supplied and normalize to ``targets``."""
        if self.target and self.targets:
            raise ValueError("Use either 'target' or 'targets', not both")
        if not self.target and not self.targets:
            raise ValueError("Must specify 'target' or 'targets'")
        if self.target:
            self.targets = [self.target]
            self.target = None
        return self

    @property
    def all_targets(self) -> list[str]:
        """Return backend URLs as strings without trailing slashes."""
        return [str(t).rstrip("/") for t in self.targets]