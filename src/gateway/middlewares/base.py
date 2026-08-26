"""Middleware base classes, registry, and validation helpers.

To add a custom middleware:
    1. Create a class implementing ``GatewayMiddleware``.
    2. Call ``register_middleware(name, factory)`` at import time.
    3. Reference the name in a route's ``middlewares`` list in routes.yaml.

The ``__init__.py`` of this package auto-imports every module in the folder,
so a new middleware file is picked up at startup without editing main.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from starlette.requests import Request
from starlette.responses import Response

from gateway.routes.models import Route


@dataclass
class MiddlewareContext:
    """Mutable context passed through the middleware chain.

    Attributes:
        request: The Starlette request being processed.
        route: The matched route.
        path: The path to send upstream (after rewrite).
        injected_headers: Headers the proxy will add to the upstream request.
        response_headers: Headers to append to the client response.
        user_sub: Authenticated user subject (set by the auth stage).
        extras: Free-form dict for middleware-to-middleware data passing.
    """

    request: Request
    route: Route
    path: str
    injected_headers: dict[str, str] = field(default_factory=dict)
    response_headers: dict[str, str] = field(default_factory=dict)
    user_sub: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class MiddlewareResult:
    """Outcome of a middleware step.

    Attributes:
        short_circuit: If set, the chain terminates and this response is
            returned to the client immediately.
    """

    short_circuit: Response | None = None


class GatewayMiddleware(Protocol):
    """Contract every custom middleware must satisfy."""

    name: str

    async def process(self, ctx: MiddlewareContext) -> MiddlewareResult:
        """Process the context and optionally short-circuit."""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, Callable[[dict[str, Any]], GatewayMiddleware]] = {}


def register_middleware(
    name: str, factory: Callable[[dict[str, Any]], GatewayMiddleware]
) -> None:
    """Register a middleware factory under a name usable in routes.yaml."""
    _REGISTRY[name] = factory


def build_chain(route: Route) -> list[GatewayMiddleware]:
    """Instantiate the custom-middleware chain for a route.

    Only names present in the registry are materialized. Unknown names are
    silently skipped here (the validator surfaces them at startup/reload).
    """
    chain: list[GatewayMiddleware] = []
    cfg_dump = route.middleware_config.model_dump(exclude_none=True)
    for name in route.middlewares:
        if name in _REGISTRY:
            chain.append(_REGISTRY[name](cfg_dump.get(name, {})))
    return chain


async def run_chain(
    chain: list[GatewayMiddleware], ctx: MiddlewareContext
) -> Response | None:
    """Run middlewares sequentially, honoring short-circuit results."""
    for mw in chain:
        result = await mw.process(ctx)
        if result.short_circuit is not None:
            return result.short_circuit
    return None


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

#: Names valid in a route's ``middlewares:`` list because they toggle
#: built-in stages. Not part of the custom-middleware registry.
OPT_IN_BUILTINS: set[str] = {"auth", "rate_limit"}

#: Names of built-in stages that always run at fixed positions and must not
#: appear in a route's ``middlewares:`` list.
RESERVED_BUILTINS: set[str] = {
    "request_id",
    "metrics_start",
    "metrics_end",
    "request_transform",
    "response_transform",
    "proxy",
}


def known_middleware_names() -> set[str]:
    """Return every name currently valid in a route's middlewares: list."""
    return set(_REGISTRY.keys()) | OPT_IN_BUILTINS