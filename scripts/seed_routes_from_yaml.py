"""Seed the configured RouteRepository from a YAML file.

Purpose:
    When migrating route storage from YAML to Redis or Postgres, the
    new backend starts empty. This script reads a YAML file and inserts
    each route through the RouteRepository interface, so validation and
    normalization match the Admin API path exactly.

Usage:
    poetry run python -m scripts.seed_routes_from_yaml routes.yaml
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import yaml

from gateway.config.factories import build_route_repository
from gateway.routes.models import Route


async def _main(path: Path) -> None:
    """Load routes from ``path`` and insert (or update) them."""
    data = yaml.safe_load(path.read_text()) or {}
    routes = [Route(**r) for r in data.get("routes", [])]
    repo = build_route_repository()
    for r in routes:
        try:
            await repo.add(r)
            print(f"added {r.id}")
        except ValueError:
            await repo.update(r.id, r)
            print(f"updated {r.id}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m scripts.seed_routes_from_yaml <path>")
        sys.exit(1)
    asyncio.run(_main(Path(sys.argv[1])))