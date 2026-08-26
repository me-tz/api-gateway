"""Route matcher unit tests."""
from __future__ import annotations

from gateway.routes.matcher import find_route, rewrite_path
from gateway.routes.models import Route


def _r(**kw) -> Route:
    """Build a Route with a placeholder target."""
    return Route(target="http://x", **kw)


def test_exact_match_hits_only_exact_path() -> None:
    r = _r(id="a", path="/foo", methods=["GET"])
    assert find_route([r], "/foo", "GET") is r
    assert find_route([r], "/foo/bar", "GET") is None


def test_wildcard_matches_prefix_and_base() -> None:
    r = _r(id="a", path="/api/*", methods=["GET"])
    assert find_route([r], "/api/x", "GET") is r
    assert find_route([r], "/api", "GET") is r
    assert find_route([r], "/other", "GET") is None


def test_method_filter_rejects_wrong_method() -> None:
    r = _r(id="a", path="/foo", methods=["POST"])
    assert find_route([r], "/foo", "GET") is None
    assert find_route([r], "/foo", "POST") is r


def test_more_specific_wildcard_wins() -> None:
    generic = _r(id="g", path="/api/*", methods=["GET"])
    specific = _r(id="s", path="/api/users/*", methods=["GET"])
    assert find_route([generic, specific], "/api/users/1", "GET").id == "s"


def test_priority_overrides_specificity() -> None:
    long = _r(id="long", path="/api/users/*", methods=["GET"], priority=0)
    short = _r(id="short", path="/api/*", methods=["GET"], priority=10)
    assert find_route([long, short], "/api/users/1", "GET").id == "short"


def test_disabled_route_is_ignored() -> None:
    r = _r(id="a", path="/foo", methods=["GET"], enabled=False)
    assert find_route([r], "/foo", "GET") is None


def test_rewrite_strips_prefix() -> None:
    r = _r(id="a", path="/api/*", methods=["GET"], strip_prefix="/api")
    assert rewrite_path(r, "/api/users/1") == "/users/1"
    assert rewrite_path(r, "/api") == "/"


def test_rewrite_adds_prefix() -> None:
    r = _r(id="a", path="/*", methods=["GET"], add_prefix="/v1")
    assert rewrite_path(r, "/things") == "/v1/things"