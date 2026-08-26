"""HTTP endpoints for the mock auth provider (REMOVABLE)."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from gateway.auth.mock_provider import MockAuthProvider
from gateway.config.settings import settings

router = APIRouter(prefix="/mock-auth", tags=["mock-auth"])


class TokenRequest(BaseModel):
    """Request body for issuing a mock JWT."""

    sub: str = "user-1"
    scopes: list[str] = ["users:read"]
    ttl_seconds: int = 3600


class TokenResponse(BaseModel):
    """Response body containing the issued JWT."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


@router.post("/token", response_model=TokenResponse)
async def issue_token(req: TokenRequest) -> TokenResponse:
    """Issue a JWT for development and Swagger testing."""
    provider = MockAuthProvider(
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
    )
    token = provider.issue(req.sub, req.scopes, req.ttl_seconds)
    return TokenResponse(access_token=token, expires_in=req.ttl_seconds)