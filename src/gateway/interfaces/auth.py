"""Authentication provider interface."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class Claims:
    """Verified JWT claims exposed to middlewares.

    Attributes:
        sub: Subject identifier (user id).
        scopes: Granted scopes/permissions.
        email: Optional email claim.
        raw: Full decoded payload for advanced use.
    """

    sub: str
    scopes: list[str] = field(default_factory=list)
    email: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class AuthProvider(Protocol):
    """Verifies bearer tokens and returns their claims."""

    async def verify(self, token: str) -> Claims:
        """Verify a token and return its claims.

        Args:
            token: The raw bearer token string.

        Returns:
            Decoded and validated claims.

        Raises:
            Exception: On invalid signature, expiry, issuer, or audience.
        """