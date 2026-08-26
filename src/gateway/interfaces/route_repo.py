"""Route repository interface."""
from __future__ import annotations

from typing import Protocol

from gateway.routes.models import Route


class RouteRepository(Protocol):
    """Persistent storage for route configuration."""

    async def list(self) -> list[Route]:
        """Return all stored routes."""

    async def get(self, route_id: str) -> Route | None:
        """Return a route by id, or None if it does not exist."""

    async def add(self, route: Route) -> None:
        """Insert a new route.

        Raises:
            ValueError: If a route with the same id already exists.
        """

    async def update(self, route_id: str, route: Route) -> None:
        """Overwrite an existing route.

        Raises:
            KeyError: If the route does not exist.
        """

    async def delete(self, route_id: str) -> None:
        """Remove a route by id (no-op if missing)."""

    async def reload(self) -> list[Route]:
        """Refresh from the underlying source and return all routes."""