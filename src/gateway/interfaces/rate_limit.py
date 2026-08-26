"""Rate-limit store interface."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class RateLimitResult:
    """Outcome of a rate-limit check.

    Attributes:
        allowed: Whether the request may proceed.
        remaining: Approximate tokens left in the bucket.
        limit: Bucket capacity.
        reset_seconds: Seconds until the bucket is fully refilled.
        retry_after: Seconds the client should wait before retrying (only on deny).
    """

    allowed: bool
    remaining: int
    limit: int
    reset_seconds: float
    retry_after: float | None = None


class RateLimitStore(Protocol):
    """Token-bucket rate-limit store."""

    async def consume(
        self, key: str, capacity: int, refill_per_second: float, cost: int = 1
    ) -> RateLimitResult:
        """Attempt to consume tokens for a bucket.

        Args:
            key: Bucket identifier (route + client).
            capacity: Maximum tokens the bucket holds.
            refill_per_second: Continuous refill rate.
            cost: Tokens to consume for this request.

        Returns:
            The check result with allow/deny and metadata.
        """

    async def close(self) -> None:
        """Release any underlying resources."""