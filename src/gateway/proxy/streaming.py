"""Streaming proxy handler using Starlette primitives and httpx.stream."""
from __future__ import annotations

import httpx
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

CLIENT_FORBIDDEN = {
    "x-user-id",
    "x-user-scopes",
    "x-user-email",
    "x-gateway-identity",
    "x-gateway-signature",
    "x-gateway-timestamp",
}

HOP_BY_HOP: set[str] = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}


def filter_headers(headers: dict[str, str]) -> dict[str, str]:
    """Strip hop-by-hop and client-forbidden headers."""
    return {
        k: v
        for k, v in headers.items()
        if k.lower() not in HOP_BY_HOP and k.lower() not in CLIENT_FORBIDDEN
    }


async def proxy_request(
    client: httpx.AsyncClient,
    request: Request,
    target_url: str,
    rewritten_path: str,
    injected_headers: dict[str, str] | None = None,
) -> Response:
    """Forward a request to an upstream backend and stream the response back.

    Args:
        client: Shared httpx client.
        request: Incoming Starlette request.
        target_url: Backend base URL (no trailing slash).
        rewritten_path: Path (with leading slash) to send upstream.
        injected_headers: Additional headers to include (e.g. X-User-Id).

    Returns:
        A StreamingResponse mirroring the upstream, or an error Response
        (502 / 504) with a redacted JSON body on failure.
    """
    url = f"{target_url}{rewritten_path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    headers = filter_headers(dict(request.headers))
    if injected_headers:
        headers.update(injected_headers)

    client_host = request.client.host if request.client else "unknown"
    prior_xff = headers.get("x-forwarded-for")
    headers["x-forwarded-for"] = f"{prior_xff}, {client_host}" if prior_xff else client_host
    headers["x-real-ip"] = client_host
    headers["x-forwarded-proto"] = request.url.scheme

    body = await request.body()

    try:
        req = client.build_request(
            method=request.method, url=url, headers=headers, content=body
        )
        upstream = await client.send(req, stream=True)
    except httpx.TimeoutException:
        return Response(
            content='{"error":"gateway timeout"}',
            status_code=504,
            media_type="application/json",
        )
    except httpx.ConnectError:
        return Response(
            content='{"error":"bad gateway"}',
            status_code=502,
            media_type="application/json",
        )
    except httpx.HTTPError:
        return Response(
            content='{"error":"upstream error"}',
            status_code=502,
            media_type="application/json",
        )

    async def body_iter() -> "AsyncIterator[bytes]":  # noqa: F821
        """Stream upstream body chunks to the client."""
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()

    resp_headers = filter_headers(dict(upstream.headers))
    return StreamingResponse(
        body_iter(),
        status_code=upstream.status_code,
        headers=resp_headers,
        media_type=upstream.headers.get("content-type"),
    )