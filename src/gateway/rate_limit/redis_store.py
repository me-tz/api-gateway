"""Redis-backed token-bucket store using an atomic Lua script."""
from __future__ import annotations

import time

import redis.asyncio as redis

from gateway.interfaces.rate_limit import RateLimitResult

_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill = tonumber(ARGV[2])
local cost = tonumber(ARGV[3])
local now = tonumber(ARGV[4])

local data = redis.call('HMGET', key, 'tokens', 'last')
local tokens = tonumber(data[1])
local last = tonumber(data[2])
if tokens == nil then tokens = capacity end
if last == nil then last = now end

local elapsed = math.max(0, (now - last) / 1000.0)
tokens = math.min(capacity, tokens + elapsed * refill)

local allowed = 0
local retry_after = 0
if tokens >= cost then
  tokens = tokens - cost
  allowed = 1
else
  retry_after = (cost - tokens) / refill
end

redis.call('HMSET', key, 'tokens', tokens, 'last', now)
redis.call('EXPIRE', key, math.ceil(capacity / refill) + 10)

return {allowed, tokens, retry_after}
"""


class RedisRateLimitStore:
    """Distributed token bucket, safe under concurrent access.

    Uses a Lua script executed with ``EVAL`` so the read-modify-write
    happens atomically on the Redis server (one round-trip, no race).
    """

    def __init__(self, url: str) -> None:
        """Initialize with a Redis URL."""
        self._redis = redis.from_url(url, decode_responses=True)
        self._script = self._redis.register_script(_LUA)

    async def consume(
        self, key: str, capacity: int, refill_per_second: float, cost: int = 1
    ) -> RateLimitResult:
        """Attempt to consume ``cost`` tokens atomically."""
        now_ms = int(time.time() * 1000)
        result = await self._script(
            keys=[f"rl:{key}"],
            args=[capacity, refill_per_second, cost, now_ms],
        )
        allowed = int(result[0]) == 1
        tokens = float(result[1])
        retry_after = float(result[2])
        reset = (capacity - tokens) / refill_per_second if refill_per_second else 0.0
        return RateLimitResult(
            allowed=allowed,
            remaining=int(tokens),
            limit=capacity,
            reset_seconds=retry_after if not allowed else reset,
            retry_after=retry_after if not allowed else None,
        )

    async def close(self) -> None:
        """Close the Redis connection pool."""
        await self._redis.aclose()