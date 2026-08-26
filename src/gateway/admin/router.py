"""Admin API endpoints (routes CRUD + reload)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from gateway.config.settings import settings
from gateway.routes.models import Route

router = APIRouter(prefix="/admin", tags=["admin"])


def _check_admin(x_admin_token: str = Header(default="")) -> None:
    """Reject the request if the admin token header is invalid."""
    if x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="invalid admin token")


@router.get("/routes", dependencies=[Depends(_check_admin)])
async def list_routes(request: Request) -> list[dict[str, Any]]:
    """Return the current in-memory route snapshot."""
    return [r.model_dump(mode="json") for r in request.app.state.registry.snapshot()]


@router.post("/routes", dependencies=[Depends(_check_admin)])
async def add_route(request: Request, route: Route) -> dict[str, bool]:
    """Insert a new route and reload the registry."""
    await request.app.state.route_repo.add(route)
    await request.app.state.registry.reload()
    return {"ok": True}


@router.put("/routes/{route_id}", dependencies=[Depends(_check_admin)])
async def update_route(request: Request, route_id: str, route: Route) -> dict[str, bool]:
    """Update an existing route."""
    await request.app.state.route_repo.update(route_id, route)
    await request.app.state.registry.reload()
    return {"ok": True}


@router.delete("/routes/{route_id}", dependencies=[Depends(_check_admin)])
async def delete_route(request: Request, route_id: str) -> dict[str, bool]:
    """Delete a route by id."""
    await request.app.state.route_repo.delete(route_id)
    await request.app.state.registry.reload()
    return {"ok": True}


@router.post("/reload", dependencies=[Depends(_check_admin)])
async def reload_routes(request: Request) -> dict[str, Any]:
    """Force a reload from the configured route repository."""
    return await request.app.state.registry.reload()