"""Flaky backend: fails randomly for chaos testing."""
from __future__ import annotations

import random

from fastapi import FastAPI, HTTPException

app = FastAPI(title="flaky-service")


@app.get("/{path:path}")
async def flaky(path: str, failure_rate: float = 0.5) -> dict[str, object]:
    """Return 500 with probability ``failure_rate``, else 200."""
    if random.random() < failure_rate:
        raise HTTPException(status_code=500, detail="random failure")
    return {"path": "/" + path, "ok": True}


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness endpoint."""
    return {"status": "ok"}