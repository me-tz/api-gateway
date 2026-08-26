"""Redis-backed RouteRepository."""
from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis

from gateway.routes.models import Route

_KEY_PREFIX = "gw:route:"
_INDEX_KEY = "gw:routes:index"
_CHANNEL = "gw:routes:changed"


class RedisRouteRepository:
    """Multi-instance friendly route store using Redis.

    Key layout:
        gw: Namespacing. If someone else uses the same Redis DB
        ``gw:route:<id>`` — JSON blob of the route. Fetch a single route by id
        ``gw:routes:index`` — SET of all route ids. Enumerate all routes without SCAN
        ``gw:routes:changed`` — pub/sub channel for reload notifications. Notify other instances to reload
    """

    def __init__(self, redis_url: str) -> None:
        """Initialize with a Redis connection URL.
        
            Args:
                redis_url: Redis connection URL (e.g., ``redis://redis:6379/0``).
        """
        self._redis: redis.Redis = redis.from_url(redis_url, decode_responses=True)

    @staticmethod
    def _key(route_id: str) -> str:
        """Return the Redis key for a route id."""
        return f"{_KEY_PREFIX}{route_id}"

    @staticmethod
    def _dump(route: Route) -> str:
        """Serialize a route to JSON."""
        return json.dumps(route.model_dump(mode="json", exclude_none=True))

    @staticmethod
    def _load(data: str) -> Route:
        """Deserialize a route from JSON."""
        return Route(**json.loads(data))

    async def _notify(self, action: str, route_id: str) -> None:
        """Publish a mutation event to the pub/sub channel."""
        payload: dict[str, Any] = {"action": action, "id": route_id}
        await self._redis.publish(_CHANNEL, json.dumps(payload))

    async def list(self) -> list[Route]:
        """Return every route currently stored."""
        ids: set[str] = await self._redis.smembers(_INDEX_KEY)
        if not ids:
            return []
        keys = [self._key(rid) for rid in ids]
        blobs: list[str | None] = await self._redis.mget(keys)
        return [self._load(b) for b in blobs if b]

    async def get(self, route_id: str) -> Route | None:
        """Return a single route by id."""
        blob = await self._redis.get(self._key(route_id))
        return self._load(blob) if blob else None

    async def add(self, route: Route) -> None:
        """Insert a new route.

        Raises:
            ValueError: If the id already exists.
        """
        exists = await self._redis.sismember(_INDEX_KEY, route.id)
        if exists:
            raise ValueError(f"Route {route.id} already exists")
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.set(self._key(route.id), self._dump(route))
            pipe.sadd(_INDEX_KEY, route.id)
            await pipe.execute()
        await self._notify("add", route.id)

    async def update(self, route_id: str, route: Route) -> None:
        """Overwrite an existing route.

        Raises:
            KeyError: If the route does not exist.
        """
        exists = await self._redis.sismember(_INDEX_KEY, route_id)
        if not exists:
            raise KeyError(route_id)
        if route.id != route_id:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.delete(self._key(route_id))
                pipe.srem(_INDEX_KEY, route_id)
                pipe.set(self._key(route.id), self._dump(route))
                pipe.sadd(_INDEX_KEY, route.id)
                await pipe.execute()
        else:
            await self._redis.set(self._key(route_id), self._dump(route))
        await self._notify("update", route.id)

    async def delete(self, route_id: str) -> None:
        """Delete a route (no-op if missing)."""
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.delete(self._key(route_id))
            pipe.srem(_INDEX_KEY, route_id)
            await pipe.execute()
        await self._notify("delete", route_id)

    async def reload(self) -> list[Route]:
        """Return the latest state (no local cache)."""
        return await self.list()

    async def close(self) -> None:
        """Close the Redis connection pool."""
        await self._redis.aclose()