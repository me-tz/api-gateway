"""Echo backend: reflects request metadata as JSON."""
from __future__ import annotations

from fastapi import FastAPI, Request

app = FastAPI(title="echo-service")


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def echo(path: str, request: Request) -> dict[str, object]:
    """Return the request method, path, headers, query, and body."""
    body = await request.body()
    return {
        "method": request.method,
        "path": "/" + path,
        "headers": dict(request.headers),
        "query": dict(request.query_params),
        "body": body.decode("utf-8", errors="replace"),
    }


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness endpoint."""
    return {"status": "ok"}