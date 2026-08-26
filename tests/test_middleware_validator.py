"""Unit tests for validate_routes covering all three warning types.

Covers, per warning type:
    - non-strict mode: logs a warning, does not raise
    - strict mode: raises MiddlewareValidationError

Also covers valid routes producing zero issues, and multi-route aggregation
in strict mode.
"""
from __future__ import annotations

import pytest

from gateway.middlewares.base import register_middleware
from gateway.middlewares.validator import (
    MiddlewareValidationError,
    validate_routes,
)
from gateway.routes.models import Route


def _route(middlewares: list[str], route_id: str = "r1") -> Route:
    """Build a minimal valid Route with a specific middlewares list."""
    return Route(
        id=route_id,
        path="/x/*",
        methods=["GET"],
        target="http://backend.test",
        middlewares=middlewares,
    )


@pytest.fixture(autouse=True)
def _register_a_custom_middleware():
    """Ensure a known custom middleware exists in the registry for tests."""

    class _Dummy:
        name = "custom_a"

        def __init__(self, config: dict) -> None:
            self._config = config

        async def process(self, ctx):  # pragma: no cover - not invoked
            from gateway.middlewares.base import MiddlewareResult
            return MiddlewareResult()

    register_middleware("custom_a", lambda cfg: _Dummy(cfg))


@pytest.fixture
def strict(monkeypatch):
    """Enable strict validation via the settings singleton."""
    from gateway.config import settings as settings_mod
    monkeypatch.setattr(settings_mod.settings, "strict_validation", True)


@pytest.fixture
def lenient(monkeypatch):
    """Force non-strict validation regardless of env."""
    from gateway.config import settings as settings_mod
    monkeypatch.setattr(settings_mod.settings, "strict_validation", False)


# ---------- valid input ----------

def test_valid_route_produces_no_error(lenient):
    validate_routes([_route(["auth", "rate_limit", "custom_a"])])
    # no exception, no assertion needed


def test_valid_route_strict_mode(strict):
    validate_routes([_route(["auth", "rate_limit", "custom_a"])])


# ---------- unknown name ----------

def test_unknown_name_lenient_logs_only(caplog, lenient):
    with caplog.at_level("WARNING"):
        validate_routes([_route(["auth", "typo_here"])])
    assert any("typo_here" in rec.message or "typo_here" in str(rec)
               for rec in caplog.records)


def test_unknown_name_strict_raises(strict):
    with pytest.raises(MiddlewareValidationError) as exc_info:
        validate_routes([_route(["auth", "typo_here"])])
    assert any("typo_here" in issue for issue in exc_info.value.issues)


# ---------- reserved name ----------

def test_reserved_name_lenient_logs_only(caplog, lenient):
    with caplog.at_level("WARNING"):
        validate_routes([_route(["request_id", "auth"])])
    assert any("request_id" in str(rec) for rec in caplog.records)


def test_reserved_name_strict_raises(strict):
    with pytest.raises(MiddlewareValidationError) as exc_info:
        validate_routes([_route(["proxy", "auth"])])
    assert any("proxy" in issue for issue in exc_info.value.issues)


# ---------- suspicious ordering ----------

def test_rate_limit_before_auth_lenient(caplog, lenient):
    with caplog.at_level("WARNING"):
        validate_routes([_route(["rate_limit", "auth"])])
    assert any("rate_limit" in str(rec) and "auth" in str(rec)
               for rec in caplog.records)


def test_rate_limit_before_auth_strict(strict):
    with pytest.raises(MiddlewareValidationError) as exc_info:
        validate_routes([_route(["rate_limit", "auth"])])
    assert any("rate_limit" in issue and "before auth" in issue
               for issue in exc_info.value.issues)


def test_custom_before_auth_lenient(caplog, lenient):
    with caplog.at_level("WARNING"):
        validate_routes([_route(["custom_a", "auth"])])
    assert any("custom_a" in str(rec) for rec in caplog.records)


def test_custom_before_auth_strict(strict):
    with pytest.raises(MiddlewareValidationError) as exc_info:
        validate_routes([_route(["custom_a", "auth"])])
    assert any("custom_a" in issue for issue in exc_info.value.issues)


# ---------- multi-route aggregation ----------

def test_strict_aggregates_issues_from_multiple_routes(strict):
    routes = [
        _route(["typo_a"], route_id="r1"),
        _route(["rate_limit", "auth"], route_id="r2"),
        _route(["proxy"], route_id="r3"),
    ]
    with pytest.raises(MiddlewareValidationError) as exc_info:
        validate_routes(routes)
    joined = " | ".join(exc_info.value.issues)
    assert "r1" in joined
    assert "r2" in joined
    assert "r3" in joined