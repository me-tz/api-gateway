"""In-memory hot cache of routes with atomic reload."""
from __future__ import annotations

import asyncio
from typing import Any

import structlog

from gateway.interfaces.route_repo import RouteRepository
from gateway.routes.matcher import find_route
from gateway.routes.models import Route

log = structlog.get_logger()


class RouteRegistry:
    """Read-mostly in-memory snapshot of routes.

    Populated at startup via :meth:`load`. Refreshed via :meth:`reload`.
    On reload the snapshot is replaced under a lock in a single assignment,
    so in-flight requests continue to see a consistent view.
    """

    def __init__(self, repo: RouteRepository) -> None:
        """Initialize the registry backed by a repository."""
        self._repo = repo
        self._routes: list[Route] = []
        self._lock = asyncio.Lock()

    async def load(self) -> None:
        """Load routes from the repository (called once at startup)."""
        async with self._lock:
            self._routes = await self._repo.list()

    async def reload(self) -> dict[str, Any]:
        """Re-fetch routes, atomically swap the snapshot, and validate.

        Validation is best-effort at reload: strict-mode failures are
        downgraded to WARN so a bad admin update does not kill a running
        gateway. Startup uses the same validator but propagates strict
        failures — see :mod:`gateway.middlewares.validator`.

        Returns:
            Diff summary with the new total count and the added/removed ids.
        """
        # Local imports keep top-level imports light and avoid any accidental
        # circular imports as the codebase grows.
        from gateway.middlewares.validator import (
            MiddlewareValidationError,
            validate_routes,
        )

        async with self._lock:
            new_routes = await self._repo.reload()
            old_ids = {r.id for r in self._routes}
            new_ids = {r.id for r in new_routes}
            self._routes = new_routes

            try:
                validate_routes(self._routes)
            except MiddlewareValidationError as e:
                log.warning(
                    "gateway.reload_validation_failed", issues=e.issues
                )

            return {
                "total": len(new_routes),
                "added": sorted(new_ids - old_ids),
                "removed": sorted(old_ids - new_ids),
            }

    def snapshot(self) -> list[Route]:
        """Return the current route list (a shallow copy)."""
        return list(self._routes)

    def match(self, path: str, method: str) -> Route | None:
        """Find a route matching the given path and method."""
        return find_route(self._routes, path, method)