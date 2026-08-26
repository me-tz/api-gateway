"""Simple in-house circuit breaker."""
from __future__ import annotations

import time
from enum import Enum

from gateway.routes.models import CircuitBreakerConfig


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Per-backend circuit breaker.

    States:
        CLOSED: normal, failures counted.
        OPEN: fail fast for ``cooldown_seconds`` after ``failure_threshold``.
        HALF_OPEN: allow up to ``half_open_max_calls`` probes; success closes,
            any failure re-opens.
    """

    def __init__(self, config: CircuitBreakerConfig) -> None:
        """Initialize with breaker configuration."""
        self._config = config
        self._states: dict[str, CircuitState] = {}
        self._failures: dict[str, int] = {}
        self._opened_at: dict[str, float] = {}
        self._half_open_calls: dict[str, int] = {}

    def state(self, key: str) -> CircuitState:
        """Return the current state for ``key`` (transitioning if cooldown elapsed)."""
        st = self._states.get(key, CircuitState.CLOSED)
        if st == CircuitState.OPEN:
            elapsed = time.monotonic() - self._opened_at.get(key, 0)
            if elapsed >= self._config.cooldown_seconds:
                self._states[key] = CircuitState.HALF_OPEN
                self._half_open_calls[key] = 0
                return CircuitState.HALF_OPEN
        return st

    def allow(self, key: str) -> bool:
        """Whether a request should be allowed through the breaker."""
        st = self.state(key)
        if st == CircuitState.CLOSED:
            return True
        if st == CircuitState.HALF_OPEN:
            calls = self._half_open_calls.get(key, 0)
            if calls < self._config.half_open_max_calls:
                self._half_open_calls[key] = calls + 1
                return True
            return False
        return False

    def record_success(self, key: str) -> None:
        """Record a successful call, closing the circuit."""
        self._states[key] = CircuitState.CLOSED
        self._failures[key] = 0
        self._half_open_calls[key] = 0

    def record_failure(self, key: str) -> None:
        """Record a failed call, opening the circuit at threshold."""
        self._failures[key] = self._failures.get(key, 0) + 1
        if self._failures[key] >= self._config.failure_threshold:
            self._states[key] = CircuitState.OPEN
            self._opened_at[key] = time.monotonic()