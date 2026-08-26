"""Slow backend: sleeps for a configurable duration."""
from __future__ import annotations

import asyncio

from fastapi import FastAPI

app = FastAPI(title="slow-service")


@app.get("/{path:path}")
async def slow(path: str, delay: float = 1.0) -> dict[str, object]:
    """Sleep for ``delay`` seconds then respond."""
    await asyncio.sleep(delay)
    return {"path": "/" + path, "delayed_seconds": delay}


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness endpoint."""
    return {"status": "ok"}