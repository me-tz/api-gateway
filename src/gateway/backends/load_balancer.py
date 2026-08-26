"""Round-robin load balancer with circuit-breaker awareness."""
from __future__ import annotations

import itertools

from gateway.backends.circuit_breaker import CircuitBreaker
from gateway.routes.models import Route


class RoundRobinLoadBalancer:
    """Selects the next healthy backend for a route in round-robin order."""

    def __init__(self, breaker: CircuitBreaker | None = None) -> None:
        """Initialize with an optional circuit breaker for eligibility checks."""
        self._cycles: dict[str, itertools.cycle[str]] = {}
        self._breaker = breaker

    def pick(self, route: Route) -> str | None:
        """Return an eligible backend URL, or None if all are excluded."""
        targets = route.all_targets
        if not targets:
            return None
        if route.id not in self._cycles:
            self._cycles[route.id] = itertools.cycle(targets)
        for _ in range(len(targets)):
            candidate = next(self._cycles[route.id])
            if self._breaker is None or self._breaker.allow(candidate):
                return candidate
        return None