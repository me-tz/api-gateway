"""YAML-file backed RouteRepository."""
from __future__ import annotations

import asyncio
from pathlib import Path

import yaml

from gateway.routes.models import Route


class YamlFileRouteRepository:
    """Reads and writes routes from a YAML file on disk.

    Suitable for local dev and single-instance deployments. Not
    recommended for multi-instance topologies (no shared writes).
    """

    def __init__(self, path: Path) -> None:
        """Initialize the repository.

        Args:
            path: Path to the YAML file (created lazily if missing).
        """
        self._path = path
        self._lock = asyncio.Lock()
        self._cache: list[Route] = []

    async def _read(self) -> list[Route]:
        """Read and parse the file, returning validated routes."""
        if not self._path.exists():
            return []
        data = yaml.safe_load(self._path.read_text()) or {}
        return [Route(**r) for r in data.get("routes", [])]

    async def _write(self) -> None:
        """Persist the current cache back to disk."""
        data = {"routes": [r.model_dump(mode="json", exclude_none=True) for r in self._cache]}
        self._path.write_text(yaml.safe_dump(data, sort_keys=False))

    async def list(self) -> list[Route]:
        """Return all routes, loading from disk on first call."""
        if not self._cache:
            self._cache = await self._read()
        return list(self._cache)

    async def get(self, route_id: str) -> Route | None:
        """Return a route by id or None."""
        for r in await self.list():
            if r.id == route_id:
                return r
        return None

    async def add(self, route: Route) -> None:
        """Insert a new route.

        Raises:
            ValueError: If the route id already exists.
        """
        async with self._lock:
            self._cache = await self._read()
            if any(r.id == route.id for r in self._cache):
                raise ValueError(f"Route {route.id} already exists")
            self._cache.append(route)
            await self._write()

    async def update(self, route_id: str, route: Route) -> None:
        """Overwrite an existing route.

        Raises:
            KeyError: If the route does not exist.
        """
        async with self._lock:
            self._cache = await self._read()
            for i, r in enumerate(self._cache):
                if r.id == route_id:
                    self._cache[i] = route
                    await self._write()
                    return
            raise KeyError(route_id)

    async def delete(self, route_id: str) -> None:
        """Delete a route (no-op if missing)."""
        async with self._lock:
            self._cache = await self._read()
            self._cache = [r for r in self._cache if r.id != route_id]
            await self._write()

    async def reload(self) -> list[Route]:
        """Force re-read from disk."""
        async with self._lock:
            self._cache = await self._read()
            return list(self._cache)