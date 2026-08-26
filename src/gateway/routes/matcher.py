"""Route matching and path rewriting."""
from __future__ import annotations

from gateway.routes.models import Route


def _match_pattern(pattern: str, path: str) -> bool:
    """Match ``path`` against a route pattern.

    Args:
        pattern: Route pattern, e.g. ``/api/users/*`` or ``/health``.
        path: Incoming request path.

    Returns:
        True if the path matches.
    """
    if pattern.endswith("/*"):
        prefix = pattern[:-2]
        return path == prefix or path.startswith(prefix + "/")
    return path == pattern


def find_route(routes: list[Route], path: str, method: str) -> Route | None:
    """Find the best route for a request.

    Selection order:
        1. Higher ``priority`` wins.
        2. Longer pattern wins.
        3. Exact match beats wildcard.

    Args:
        routes: All known routes.
        path: Incoming request path.
        method: HTTP method (case-insensitive).

    Returns:
        The best matching enabled route, or None.
    """
    candidates: list[Route] = []
    for r in routes:
        if not r.enabled:
            continue
        if method.upper() not in [m.upper() for m in r.methods]:
            continue
        if _match_pattern(r.path, path):
            candidates.append(r)
    if not candidates:
        return None

    def sort_key(r: Route) -> tuple[int, int, int]:
        is_exact = not r.path.endswith("/*")
        return (-r.priority, -len(r.path), 0 if is_exact else 1)

    candidates.sort(key=sort_key)
    return candidates[0]


def rewrite_path(route: Route, incoming_path: str) -> str:
    """Apply ``strip_prefix`` and ``add_prefix`` transforms.

    Args:
        route: Matched route with rewrite configuration.
        incoming_path: Original request path.

    Returns:
        The path to send upstream (always starts with ``/``).
    """
    path = incoming_path
    if route.strip_prefix and path.startswith(route.strip_prefix):
        path = path[len(route.strip_prefix):] or "/"
    if route.add_prefix:
        path = route.add_prefix.rstrip("/") + path
    if not path.startswith("/"):
        path = "/" + path
    return path