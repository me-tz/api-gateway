"""FastAPI application and top-level request handler."""
from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI, Request
from fastapi.security import HTTPBearer
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from gateway.admin.router import router as admin_router
from gateway.backends.circuit_breaker import CircuitBreaker
from gateway.backends.load_balancer import RoundRobinLoadBalancer
from gateway.config.factories import (
    build_auth_provider,
    build_rate_limit_store,
    build_route_repository,
)
from gateway.config.settings import settings
from gateway.middlewares.validator import (
    MiddlewareValidationError,
    validate_routes,
)
from gateway.observability.logging import configure_logging
from gateway.observability.metrics import (
    AUTH_FAILURES,
    BACKEND_ERRORS,
    IN_FLIGHT,
    RATE_LIMIT_HITS,
    REQUEST_DURATION,
    REQUESTS_TOTAL,
)
from gateway.proxy.client import build_http_client
from gateway.proxy.streaming import proxy_request
from gateway.routes.matcher import rewrite_path
from gateway.routes.models import CircuitBreakerConfig
from gateway.routes.registry import RouteRegistry

configure_logging()
log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize shared resources on startup and clean up on shutdown."""
    app.state.http_client = build_http_client()
    app.state.route_repo = build_route_repository()
    app.state.registry = RouteRegistry(app.state.route_repo)
    await app.state.registry.load()

    # Validate middleware lists immediately after the registry is populated
    # and before the app starts serving traffic. In strict mode this raises
    # and startup aborts, which is the desired safety net.
    try:
        validate_routes(app.state.registry.snapshot())
    except MiddlewareValidationError as e:
        log.error(
            "gateway.startup_aborted",
            reason="middleware_validation",
            issues=e.issues,
        )
        raise

    app.state.rate_limit_store = build_rate_limit_store()
    app.state.auth_provider = build_auth_provider()
    app.state.circuit_breaker = CircuitBreaker(CircuitBreakerConfig())
    app.state.lb = RoundRobinLoadBalancer(app.state.circuit_breaker)
    log.info("gateway.started", routes=len(app.state.registry.snapshot()))
    try:
        yield
    finally:
        await app.state.http_client.aclose()
        await app.state.rate_limit_store.close()


app = FastAPI(title="API Gateway", lifespan=lifespan)
bearer_scheme = HTTPBearer(auto_error=False)

app.include_router(admin_router)

if settings.auth_backend == "mock":
    from gateway.auth.router import router as mock_auth_router
    app.include_router(mock_auth_router)


# ---------------------------------------------------------------------------
# Framework endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health(request: Request) -> dict[str, object]:
    """Return gateway liveness and current route count."""
    return {"status": "ok", "routes": len(request.app.state.registry.snapshot())}


@app.get("/metrics")
async def metrics() -> Response:
    """Expose Prometheus metrics in text exposition format."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _client_key(request: Request, sub: str | None) -> str:
    """Return the rate-limit key for the caller."""
    if sub:
        return f"user:{sub}"
    client_host = request.client.host if request.client else "unknown"
    return f"ip:{client_host}"


# ---------------------------------------------------------------------------
# Catch-all request handler (the gateway pipeline)
# ---------------------------------------------------------------------------

@app.api_route(
    "/{full_path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
    include_in_schema=False,
)
async def gateway_handler(full_path: str, request: Request) -> Response:
    """Match a route, run middlewares, proxy upstream, return the response."""
    start = time.perf_counter()

    # ---- RequestID / Logging entry (built-in, always) ----
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(request_id=request_id)

    path = "/" + full_path if not full_path.startswith("/") else full_path
    route = request.app.state.registry.match(path, request.method)
    route_id = route.id if route else "unmatched"

    # ---- Metrics start (built-in, always) ----
    IN_FLIGHT.labels(route=route_id).inc()

    try:
        if route is None:
            REQUESTS_TOTAL.labels(
                route="unmatched", method=request.method, status=404
            ).inc()
            return Response(
                content='{"error":"route not found"}',
                status_code=404,
                media_type="application/json",
            )

        injected: dict[str, str] = {"x-request-id": request_id}
        sub: str | None = None

        # ---- Auth (built-in, opt-in via middlewares: [auth]) ----
        auth_cfg = route.middleware_config.auth
        if "auth" in route.middlewares and auth_cfg:
            authz = request.headers.get("authorization", "")
            token = (
                authz.removeprefix("Bearer ").strip()
                if authz.lower().startswith("bearer ")
                else ""
            )
            if not token:
                if auth_cfg.required:
                    AUTH_FAILURES.labels(reason="missing_token").inc()
                    REQUESTS_TOTAL.labels(
                        route=route.id, method=request.method, status=401
                    ).inc()
                    return Response(
                        content='{"error":"missing token"}',
                        status_code=401,
                        media_type="application/json",
                    )
            else:
                try:
                    claims = await request.app.state.auth_provider.verify(token)
                except Exception:
                    AUTH_FAILURES.labels(reason="invalid_token").inc()
                    REQUESTS_TOTAL.labels(
                        route=route.id, method=request.method, status=401
                    ).inc()
                    return Response(
                        content='{"error":"invalid token"}',
                        status_code=401,
                        media_type="application/json",
                    )
                if auth_cfg.scopes and not set(auth_cfg.scopes).issubset(
                    set(claims.scopes)
                ):
                    AUTH_FAILURES.labels(reason="missing_scope").inc()
                    REQUESTS_TOTAL.labels(
                        route=route.id, method=request.method, status=403
                    ).inc()
                    return Response(
                        content='{"error":"insufficient scope"}',
                        status_code=403,
                        media_type="application/json",
                    )
                sub = claims.sub
                injected["x-user-id"] = claims.sub
                injected["x-user-scopes"] = ",".join(claims.scopes)
                if claims.email:
                    injected["x-user-email"] = claims.email

        # ---- Rate Limit (built-in, opt-in via middlewares: [rate_limit]) ----
        rl_headers: dict[str, str] = {}
        rl_cfg = route.middleware_config.rate_limit
        if "rate_limit" in route.middlewares and rl_cfg:
            key = f"{route.id}:{_client_key(request, sub)}"
            try:
                result = await request.app.state.rate_limit_store.consume(
                    key, rl_cfg.capacity, rl_cfg.refill_per_second
                )
            except Exception as e:
                # Fail-open by default: log a WARN and let the request through.
                # Fail-closed returns 503. See DECISIONS.md → Fail Open vs Closed.
                log.warning("rate_limit.store_error", error=str(e))
                if settings.rate_limit_fail_mode == "closed":
                    REQUESTS_TOTAL.labels(
                        route=route.id, method=request.method, status=503
                    ).inc()
                    return Response(
                        content='{"error":"rate limiter unavailable"}',
                        status_code=503,
                        media_type="application/json",
                    )
                result = None

            if result is not None:
                if not result.allowed:
                    RATE_LIMIT_HITS.labels(route=route.id).inc()
                    REQUESTS_TOTAL.labels(
                        route=route.id, method=request.method, status=429
                    ).inc()
                    return Response(
                        content='{"error":"rate limit exceeded"}',
                        status_code=429,
                        media_type="application/json",
                        headers={
                            "X-RateLimit-Limit": str(result.limit),
                            "X-RateLimit-Remaining": str(result.remaining),
                            "X-RateLimit-Reset": f"{result.reset_seconds:.2f}",
                            "Retry-After": f"{int(result.retry_after or 1)}",
                        },
                    )
                rl_headers = {
                    "X-RateLimit-Limit": str(result.limit),
                    "X-RateLimit-Remaining": str(result.remaining),
                    "X-RateLimit-Reset": f"{result.reset_seconds:.2f}",
                }

        # ---- Request Transform (built-in, always; happens inside proxy) ----
        # ---- Custom middlewares (registry, in list order) ----
        # Custom middlewares run in the slot between Request Transform and
        # Proxy. The proxy layer applies header stripping and X-Forwarded-*.
        from gateway.middlewares.base import (
            MiddlewareContext,
            build_chain,
            run_chain,
        )

        chain = build_chain(route)
        if chain:
            ctx = MiddlewareContext(
                request=request,
                route=route,
                path=path,
                injected_headers=injected,
                user_sub=sub,
            )
            short = await run_chain(chain, ctx)
            if short is not None:
                REQUESTS_TOTAL.labels(
                    route=route.id,
                    method=request.method,
                    status=short.status_code,
                ).inc()
                return short
            injected = ctx.injected_headers
            rl_headers.update(ctx.response_headers)

        # ---- Load balancer + circuit breaker ----
        target = request.app.state.lb.pick(route)
        if target is None:
            BACKEND_ERRORS.labels(route=route.id, kind="no_backend").inc()
            REQUESTS_TOTAL.labels(
                route=route.id, method=request.method, status=503
            ).inc()
            return Response(
                content='{"error":"no healthy backend"}',
                status_code=503,
                media_type="application/json",
            )

        # ---- Proxy (built-in, always) ----
        rewritten = rewrite_path(route, path)
        response = await proxy_request(
            request.app.state.http_client,
            request,
            target,
            rewritten,
            injected,
        )

        # Feed the circuit breaker with the outcome of this call.
        if response.status_code >= 500:
            request.app.state.circuit_breaker.record_failure(target)
            BACKEND_ERRORS.labels(
                route=route.id, kind=f"http_{response.status_code}"
            ).inc()
        else:
            request.app.state.circuit_breaker.record_success(target)

        # ---- Response Transform (built-in, always) ----
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Gateway-Duration-Ms"] = f"{duration_ms:.2f}"
        response.headers["X-Request-ID"] = request_id
        for k, v in rl_headers.items():
            response.headers[k] = v

        # ---- Metrics end (built-in, always) ----
        REQUESTS_TOTAL.labels(
            route=route.id, method=request.method, status=response.status_code
        ).inc()
        REQUEST_DURATION.labels(
            route=route.id, method=request.method
        ).observe(duration_ms / 1000)
        return response
    finally:
        IN_FLIGHT.labels(route=route_id).dec()
        structlog.contextvars.clear_contextvars()