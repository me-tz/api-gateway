"""Mock JWT provider (REMOVABLE).

To remove for production:
    1. Delete this file and ``auth/router.py``.
    2. Remove the conditional include in ``main.py``.
    3. Set ``GATEWAY_AUTH_BACKEND=oidc`` and implement ``OidcAuthProvider``.
"""
from __future__ import annotations

import time

import jwt

from gateway.interfaces.auth import Claims


class MockAuthProvider:
    """Issues and verifies HS256 JWTs signed with a static secret."""

    def __init__(self, secret: str, algorithm: str, issuer: str, audience: str) -> None:
        """Initialize the provider.

        Args:
            secret: HMAC signing secret.
            algorithm: JWT algorithm identifier (typically ``HS256``).
            issuer: Value placed in and validated against the ``iss`` claim.
            audience: Value placed in and validated against the ``aud`` claim.
        """
        self._secret = secret
        self._algorithm = algorithm
        self._issuer = issuer
        self._audience = audience

    def issue(self, sub: str, scopes: list[str], ttl_seconds: int = 3600) -> str:
        """Issue a new signed JWT.

        Args:
            sub: Subject (user id).
            scopes: Scopes to include.
            ttl_seconds: Token lifetime.

        Returns:
            Encoded JWT string.
        """
        now = int(time.time())
        payload = {
            "sub": sub,
            "scopes": scopes,
            "iss": self._issuer,
            "aud": self._audience,
            "iat": now,
            "exp": now + ttl_seconds,
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    async def verify(self, token: str) -> Claims:
        """Verify signature, issuer, audience, and expiry.

        Args:
            token: Bearer token.

        Returns:
            Decoded claims.

        Raises:
            jwt.PyJWTError: On any validation failure.
        """
        payload = jwt.decode(
            token,
            self._secret,
            algorithms=[self._algorithm],
            issuer=self._issuer,
            audience=self._audience,
        )
        return Claims(
            sub=payload["sub"],
            scopes=payload.get("scopes", []),
            email=payload.get("email"),
            raw=payload,
        )