"""Postgres-backed RouteRepository."""
from __future__ import annotations

import json
from typing import Any

import asyncpg

from gateway.routes.models import Route


class PostgresRouteRepository:
    """Persists routes in a Postgres ``routes`` table.

    Provides transactional CRUD and a natural upgrade path to add
    audit history via a companion ``routes_audit`` table.
    """

    def __init__(self, dsn: str) -> None:
        """Initialize with a Postgres DSN."""
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def _get_pool(self) -> asyncpg.Pool:
        """Lazily create the connection pool."""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=10)
        assert self._pool is not None
        return self._pool

    @staticmethod
    def _row_to_route(row: asyncpg.Record) -> Route:
        """Convert a DB row into a Route model."""
        return Route(
            id=row["id"],
            path=row["path"],
            methods=list(row["methods"]),
            targets=json.loads(row["targets"]),
            load_balancer=row["load_balancer"],
            strip_prefix=row["strip_prefix"],
            add_prefix=row["add_prefix"],
            enabled=row["enabled"],
            priority=row["priority"],
            middlewares=json.loads(row["middlewares"]),
            middleware_config=json.loads(row["middleware_config"]),
            health_check=json.loads(row["health_check"]) if row["health_check"] else None,
            circuit_breaker=json.loads(row["circuit_breaker"]) if row["circuit_breaker"] else None,
        )

    @staticmethod
    def _route_to_params(route: Route) -> tuple[Any, ...]:
        """Convert a Route into positional insert/update parameters."""
        d = route.model_dump(mode="json", exclude_none=True)
        return (
            route.id,
            route.path,
            route.methods,
            json.dumps(d.get("targets", [])),
            route.load_balancer,
            route.strip_prefix,
            route.add_prefix,
            route.enabled,
            route.priority,
            json.dumps(route.middlewares),
            json.dumps(d.get("middleware_config", {})),
            json.dumps(d.get("health_check")) if d.get("health_check") else None,
            json.dumps(d.get("circuit_breaker")) if d.get("circuit_breaker") else None,
        )

    async def list(self) -> list[Route]:
        """Return every stored route ordered by priority."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM routes ORDER BY priority DESC, id ASC"
            )
        return [self._row_to_route(r) for r in rows]

    async def get(self, route_id: str) -> Route | None:
        """Return a route by id."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM routes WHERE id = $1", route_id)
        return self._row_to_route(row) if row else None

    async def add(self, route: Route) -> None:
        """Insert a new route.

        Raises:
            ValueError: If the id already exists.
        """
        pool = await self._get_pool()
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO routes (
                        id, path, methods, targets, load_balancer,
                        strip_prefix, add_prefix, enabled, priority,
                        middlewares, middleware_config, health_check, circuit_breaker
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                    """,
                    *self._route_to_params(route),
                )
        except asyncpg.UniqueViolationError as e:
            raise ValueError(f"Route {route.id} already exists") from e

    async def update(self, route_id: str, route: Route) -> None:
        """Overwrite an existing route.

        Raises:
            KeyError: If the route does not exist.
        """
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE routes SET
                    id=$1, path=$2, methods=$3, targets=$4, load_balancer=$5,
                    strip_prefix=$6, add_prefix=$7, enabled=$8, priority=$9,
                    middlewares=$10, middleware_config=$11,
                    health_check=$12, circuit_breaker=$13
                WHERE id=$14
                """,
                *self._route_to_params(route),
                route_id,
            )
        if result.endswith(" 0"):
            raise KeyError(route_id)

    async def delete(self, route_id: str) -> None:
        """Delete a route by id."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM routes WHERE id = $1", route_id)

    async def reload(self) -> list[Route]:
        """Return the latest state."""
        return await self.list()

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None