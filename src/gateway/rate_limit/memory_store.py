"""In-memory token-bucket store for local dev and tests."""
from __future__ import annotations

import asyncio
import time

from gateway.interfaces.rate_limit import RateLimitResult


class InMemoryRateLimitStore:
    """Token bucket implemented with a per-key asyncio.Lock.

    Not shared across processes; fine for single-worker local dev.
    """

    def __init__(self) -> None:
        """Create empty bucket storage."""
        self._buckets: dict[str, tuple[float, float]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def _get_lock(self, key: str) -> asyncio.Lock:
        """Return the per-key lock, creating it on first use."""
        async with self._global_lock:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            return self._locks[key]

    async def consume(
        self, key: str, capacity: int, refill_per_second: float, cost: int = 1
    ) -> RateLimitResult:
        """Attempt to consume ``cost`` tokens from bucket ``key``."""
        lock = await self._get_lock(key)
        async with lock:
            now = time.monotonic()
            tokens, last = self._buckets.get(key, (float(capacity), now))
            elapsed = now - last
            tokens = min(capacity, tokens + elapsed * refill_per_second)

            if tokens >= cost:
                tokens -= cost
                self._buckets[key] = (tokens, now)
                reset = (capacity - tokens) / refill_per_second if refill_per_second else 0
                return RateLimitResult(
                    allowed=True,
                    remaining=int(tokens),
                    limit=capacity,
                    reset_seconds=reset,
                )
            self._buckets[key] = (tokens, now)
            missing = cost - tokens
            retry_after = missing / refill_per_second if refill_per_second else 60.0
            return RateLimitResult(
                allowed=False,
                remaining=int(tokens),
                limit=capacity,
                reset_seconds=retry_after,
                retry_after=retry_after,
            )

    async def close(self) -> None:
        """No-op for the in-memory store."""