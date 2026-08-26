"""Startup and reload validation for per-route middleware lists.

Emits WARN-level logs for:
    - Unknown names (probable typos).
    - Reserved built-in names that must not appear in the list.
    - Ordering that suggests a misunderstanding of the pipeline
      (e.g. a custom middleware or rate_limit appearing before auth).

Behavior is controlled by ``GATEWAY_STRICT_VALIDATION``:
    - False (default): warnings only. Misconfigured routes still start.
    - True: warnings are still emitted; every issue is aggregated into a
      ``MiddlewareValidationError`` and raised. Startup aborts.

The reload path in ``RouteRegistry`` catches this error and downgrades it
to a warning so a bad admin update cannot tear down a running gateway.
"""
from __future__ import annotations

import structlog

from gateway.config.settings import settings
from gateway.middlewares.base import (
    OPT_IN_BUILTINS,
    RESERVED_BUILTINS,
    known_middleware_names,
)
from gateway.routes.models import Route

log = structlog.get_logger()


class MiddlewareValidationError(Exception):
    """Raised in strict mode when route middleware lists contain issues."""

    def __init__(self, issues: list[str]) -> None:
        """Store the aggregated issue messages and build a readable error."""
        self.issues = issues
        super().__init__(
            f"{len(issues)} middleware validation issue(s) found:\n  - "
            + "\n  - ".join(issues)
        )


def validate_routes(routes: list[Route]) -> None:
    """Run middleware-list validations across every route.

    Args:
        routes: Snapshot of routes to validate.

    Raises:
        MiddlewareValidationError: If ``GATEWAY_STRICT_VALIDATION`` is True
            and at least one issue was found.
    """
    known = known_middleware_names()
    issues: list[str] = []
    for route in routes:
        issues.extend(_validate_names(route, known))
        issues.extend(_validate_ordering(route, known))

    if issues and settings.strict_validation:
        raise MiddlewareValidationError(issues)


def _validate_names(route: Route, known: set[str]) -> list[str]:
    """Warn about reserved and unknown names in a route's middleware list."""
    issues: list[str] = []
    for name in route.middlewares:
        if name in RESERVED_BUILTINS:
            msg = (
                f"route {route.id!r}: {name!r} is a built-in stage and always "
                f"runs at a fixed position; remove it from the middlewares list."
            )
            log.warning(
                "middleware.reserved_name_in_list",
                route_id=route.id,
                name=name,
                message=msg,
            )
            issues.append(msg)
        elif name not in known:
            msg = (
                f"route {route.id!r}: {name!r} is not a registered custom "
                f"middleware and is not one of {sorted(OPT_IN_BUILTINS)}; "
                f"it will be ignored."
            )
            log.warning(
                "middleware.unknown_name",
                route_id=route.id,
                name=name,
                message=msg,
            )
            issues.append(msg)
    return issues


def _validate_ordering(route: Route, known: set[str]) -> list[str]:
    """Warn when list order suggests a misunderstanding of the pipeline."""
    issues: list[str] = []
    names = route.middlewares
    if "auth" not in names:
        return issues
    auth_index = names.index("auth")
    for name in names[:auth_index]:
        if name == "rate_limit":
            msg = (
                f"route {route.id!r}: rate_limit appears before auth in the "
                f"middlewares list. This list does not reorder built-in "
                f"stages; auth still runs before rate_limit."
            )
            log.warning(
                "middleware.suspicious_order",
                route_id=route.id,
                message=msg,
            )
            issues.append(msg)
        elif name in known and name not in OPT_IN_BUILTINS:
            msg = (
                f"route {route.id!r}: custom middleware {name!r} appears "
                f"before auth in the list, but custom middlewares always run "
                f"after auth."
            )
            log.warning(
                "middleware.suspicious_order",
                route_id=route.id,
                name=name,
                message=msg,
            )
            issues.append(msg)
    return issues