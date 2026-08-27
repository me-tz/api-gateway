"""Prometheus metric definitions."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

REQUESTS_TOTAL = Counter(
    "gateway_requests_total",
    "Total requests processed by the gateway",
    ["route", "method", "status"],
)

REQUEST_DURATION = Histogram(
    "gateway_request_duration_seconds",
    "End-to-end request duration",
    ["route", "method"],
)

IN_FLIGHT = Gauge(
    "gateway_requests_in_flight",
    "Requests currently being processed",
    ["route"],
)

RATE_LIMIT_HITS = Counter(
    "gateway_rate_limit_hits_total",
    "Requests denied by rate limit",
    ["route"],
)

AUTH_FAILURES = Counter(
    "gateway_auth_failures_total",
    "Authentication or authorization failures",
    ["reason"],
)

BACKEND_ERRORS = Counter(
    "gateway_backend_errors_total",
    "Upstream errors observed by the proxy",
    ["route", "kind"],
)
