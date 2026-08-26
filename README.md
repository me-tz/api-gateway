# API Gateway

Lightweight async API Gateway with authentication, dynamic routing, token-bucket rate limiting, request/response transformation, health checks, circuit breaker, and Prometheus metrics.

---

## Table of Contents

- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Setup and Installation](#setup-and-installation)
  - [Prerequisites](#prerequisites)
  - [Install dependencies](#install-dependencies)
  - [Environment files](#environment-files)
  - [Configuring Redis and the Database](#configuring-redis-and-the-database)
  - [Environment samples](#environment-samples)
- [Running the Project](#running-the-project)
  - [Running locally without Docker](#running-locally-without-docker)
  - [Running with Docker Compose](#running-with-docker-compose)
  - [Verify the gateway is up](#verify-the-gateway-is-up)
- [Proxy and Streaming](#proxy-and-streaming)
- [Route Targets](#route-targets)
- [Tests](#tests)
- [Adding a Custom Middleware](#adding-a-custom-middleware)
- [Getting a JWT via Swagger](#getting-a-jwt-via-swagger)
- [Example Requests](#example-requests)
- [Circuit Breaker](#circuit-breaker)
- [Prometheus](#prometheus)
- [Configuration Reference](#configuration-reference)
- [Migration](#migration)

---

## Architecture

[![Architecture Flowchart](assets/architecture-flowchart.png)](assets/architecture-flowchart.png)

---

## Project Structure

| Folder | Purpose |
|---|---|
| `src/gateway/` | The gateway application code. |
| `src/gateway/config/` | Settings loaded from env vars and factories that pick which implementation to use for each interface. |
| `src/gateway/interfaces/` | Protocol definitions — the contracts every implementation must satisfy (auth, rate limit, route repo). |
| `src/gateway/auth/` | Mock JWT provider and its `/mock-auth/token` router. Removable when moving to a real IdP. |
| `src/gateway/rate_limit/` | Token-bucket store implementations (in-memory for dev, Redis for prod). |
| `src/gateway/routes/` | Route domain: Pydantic models, matcher, and the in-memory `RouteRegistry`. |
| `src/gateway/repositories/` | Persistence layer. Currently only `routes/` (YAML, Redis, Postgres). |
| `src/gateway/backends/` | Circuit breaker and load balancer for talking to upstream services. |
| `src/gateway/middlewares/` | Middleware base classes and registry. Drop a new file here and it is auto-loaded. |
| `src/gateway/proxy/` | Shared `httpx.AsyncClient` and the streaming proxy handler. |
| `src/gateway/admin/` | Admin API: routes CRUD and `POST /admin/reload`. |
| `src/gateway/observability/` | Structured logging config and Prometheus metric definitions. |
| `mock_backends/` | Three tiny FastAPI services (echo, slow, flaky) for local testing. |
| `tests/` | Pytest suite. Runs entirely in-process with in-memory fakes. |
| `scripts/` | Operational scripts: DB schema, one-time YAML→DB seeder, test runners. |
| `examples/` | End-to-end curl walkthroughs (Bash and PowerShell). |

---

## Setup and Installation

### Prerequisites

- Python 3.12.10
- [Poetry](https://python-poetry.org/) — `pip install poetry`
- [`just`](https://github.com/casey/just) task runner
  - Windows: `winget install --id Casey.Just --exact`
  - macOS: `brew install just`
  - Linux: `cargo install just` or your package manager
- Docker Desktop (only required if running via Docker Compose)

### Install dependencies

```bash
poetry install
```

### Environment files

There are three env files in the repo, each with a specific purpose:

| File | Committed? | Purpose |
|---|---|---|
| `.env.example` | Yes | Template with safe defaults. Copy to `.env`. |
| `.env` | No (gitignored) | Your local secrets and overrides. |
| `.env.docker` | Yes | Loaded by `docker-compose.yml` for service-to-service networking. |

Create your local file by copying the template:

```bash
cp .env.example .env
```

The defaults in `.env.example` work out of the box for local dev — no Redis, no Postgres, no external services required.

### Configuring Redis and the Database

Two things to understand:

1. **Whether you use Redis or Postgres at all is a choice.** By default the gateway uses no external services: rate-limit counters live in memory, and route definitions live in `routes.yaml`. You only opt in when you need them.

2. **All configuration lives in `.env` (or environment variables).** There is no separate config file for Redis or the DB — every setting is a `GATEWAY_*` variable read by `src/gateway/config/settings.py`.

The three switches that control which backend is used:

| Variable | Values | What it selects |
|---|---|---|
| `GATEWAY_STORE_BACKEND` | `memory` \| `redis` | Where rate-limit counters live |
| `GATEWAY_ROUTE_REPO_BACKEND` | `file` \| `redis` \| `postgres` | Where routes are persisted |
| `GATEWAY_AUTH_BACKEND` | `mock` \| `oidc` | Which auth provider to use |

If any backend is set to `redis` or `postgres`, the gateway reads the connection string from these variables:

| Variable | Example | Used by |
|---|---|---|
| `GATEWAY_REDIS_URL` | `redis://localhost:6379/0` | Redis rate-limit store and/or Redis route repo |
| `GATEWAY_POSTGRES_DSN` | `postgresql://gateway:gateway@localhost:5432/gateway` | Postgres route repo |

Both connection strings live in `.env.example` — they are simply ignored unless one of the backend switches is set to `redis` or `postgres`.

### Environment samples

**Sample 1 — Fully local (no external services)** — recommended for first run:

```env
GATEWAY_STORE_BACKEND=memory
GATEWAY_ROUTE_REPO_BACKEND=file
GATEWAY_AUTH_BACKEND=mock

GATEWAY_ROUTES_FILE_PATH=./routes.yaml
GATEWAY_JWT_SECRET=dev-secret-change-me
GATEWAY_JWT_ISSUER=mock-auth
GATEWAY_JWT_AUDIENCE=api-gateway

GATEWAY_RATE_LIMIT_FAIL_MODE=open
GATEWAY_LOG_LEVEL=INFO
GATEWAY_LOG_FORMAT=pretty
GATEWAY_ADMIN_TOKEN=admin-dev-token
```

**Sample 2 — Local dev with remote Redis and Postgres**:

```env
GATEWAY_STORE_BACKEND=redis
GATEWAY_ROUTE_REPO_BACKEND=postgres
GATEWAY_AUTH_BACKEND=mock

GATEWAY_REDIS_URL=redis://redis.internal.example.com:6379/0
GATEWAY_POSTGRES_DSN=postgresql://gateway:secret@postgres.internal.example.com:5432/gateway

GATEWAY_JWT_SECRET=change-me
GATEWAY_JWT_ISSUER=mock-auth
GATEWAY_JWT_AUDIENCE=api-gateway

GATEWAY_RATE_LIMIT_FAIL_MODE=open
GATEWAY_LOG_LEVEL=INFO
GATEWAY_LOG_FORMAT=json
GATEWAY_ADMIN_TOKEN=rotate-me-in-prod
```

**Sample 3 — Docker Compose (`.env.docker`)** — uses Compose service names:

```env
GATEWAY_STORE_BACKEND=redis
GATEWAY_ROUTE_REPO_BACKEND=file
GATEWAY_AUTH_BACKEND=mock

GATEWAY_REDIS_URL=redis://redis:6379/0
GATEWAY_POSTGRES_DSN=postgresql://gateway:gateway@postgres:5432/gateway
GATEWAY_ROUTES_FILE_PATH=/app/routes.docker.yaml

GATEWAY_JWT_SECRET=change-me-in-real-prod
GATEWAY_JWT_ISSUER=mock-auth
GATEWAY_JWT_AUDIENCE=api-gateway

GATEWAY_RATE_LIMIT_FAIL_MODE=open
GATEWAY_LOG_LEVEL=INFO
GATEWAY_LOG_FORMAT=json
GATEWAY_ADMIN_TOKEN=admin-docker-token
```

**Configuration precedence** (highest wins): real environment variables → `.env` file → defaults in `src/gateway/config/settings.py`. You can override any setting inline for one command:

```bash
GATEWAY_STORE_BACKEND=redis just gateway
```

---

## Running the Project

### Running locally without Docker

Use this for day-to-day development — fast iteration, no container overhead.

```bash
poetry install
cp .env.example .env
```

Open two terminals:

```bash
# Terminal 1 — mock backends on ports 9001, 9002, 9003
just backends
```

```bash
# Terminal 2 — gateway on port 8080
just gateway
```

Gateway available at `http://localhost:8080`. Swagger UI at `http://localhost:8080/docs`.

**With a standalone Redis** (optional):

```bash
docker run -d --name gw-redis -p 6379:6379 redis:7-alpine
GATEWAY_STORE_BACKEND=redis just gateway
```

**With a standalone Postgres for route storage** (optional):

```bash
docker run -d --name gw-postgres -p 5432:5432 \
  -e POSTGRES_USER=gateway -e POSTGRES_PASSWORD=gateway -e POSTGRES_DB=gateway \
  postgres:16-alpine

psql "$GATEWAY_POSTGRES_DSN" -f scripts/schema.sql
just seed-routes routes.yaml
GATEWAY_ROUTE_REPO_BACKEND=postgres just gateway
```

### Running with Docker Compose

Brings up the full stack in one command: gateway, redis, postgres, echo-service, slow-service, flaky-service. Uses `.env.docker` and `routes.docker.yaml` (which reference each service by its Compose service name).

```bash
docker compose up --build
```

The Postgres schema is applied automatically on first container startup via `docker-entrypoint-initdb.d`.

Shut everything down and remove volumes:

```bash
docker compose down -v
```

### Verify the gateway is up

```bash
curl http://localhost:8080/health
```

Expected response:

```json
{"status": "ok", "routes": 4}
```

---

## Proxy and Streaming

The `src/gateway/proxy/` folder contains everything about talking to upstream backends:

- `client.py` — a single long-lived `httpx.AsyncClient` shared across all requests, with tuned connection pool and timeouts.
- `streaming.py` — the actual proxy handler that forwards a request to the upstream backend and streams the response back.

**When to use streaming vs buffered:**

| Situation | Use |
|---|---|
| File uploads / downloads | Streaming — never buffer large files into RAM |
| Server-Sent Events / long-poll | Streaming — must forward bytes as they arrive |
| Large JSON responses | Streaming — reduces memory pressure and latency |
| Small JSON APIs | Either works; streaming is still fine and adds no cost |

**Rule of thumb:** a gateway should stream by default. It doesn't know in advance how large any request or response will be, and buffering breaks large-payload use cases silently. This implementation streams unconditionally.

---

## Route Targets

Each route sends traffic to one or more upstream backends. Two forms are supported:

**Single target** — the orchestrator (Docker DNS, Kubernetes Service) handles load balancing:

```yaml
- id: users-api
  path: /api/users/*
  target: http://user-service:8080
```

**Multiple targets** — the gateway itself round-robins between healthy instances, integrated with the circuit breaker. Use on bare metal or when you want application-level health awareness:

```yaml
- id: orders-api
  path: /api/orders/*
  targets:
    - http://orders-1.internal:8080
    - http://orders-2.internal:8080
    - http://orders-3.internal:8080
  load_balancer: round_robin
  health_check:
    path: /health
    interval_seconds: 10
    unhealthy_threshold: 3
  circuit_breaker:
    failure_threshold: 5
    cooldown_seconds: 30
```

Internally both forms normalize into a `targets` list, so the same code path serves them.

#### Path Rewriting

Each route can transform the incoming URL before forwarding upstream:

- **`path`** — the URL pattern to match. Exact match or `/*` suffix wildcard. Example: `path: /api/users/*` matches `/api/users`, `/api/users/42`, `/api/users/42/orders`, but not `/api/things`.
- **`strip_prefix`** — the leading portion of the path to remove before proxying (forwarding upstream). It rewrites the URL so the backend sees a clean path.
- **`add_prefix`** — an optional prefix to prepend after stripping.

Example:

```yaml
- id: users-api
  path: /api/users/*
  target: http://user-service:8080
  strip_prefix: /api/users
```

| Client request | Backend receives |
|---|---|
| `GET /api/users/42` | `GET http://user-service:8080/42` |
| `GET /api/users` | `GET http://user-service:8080/` |
| `GET /api/users/42/orders` | `GET http://user-service:8080/42/orders` |

### Combining exact and wildcard routes

You can define both an exact-match and a wildcard route for the same resource, letting each handle a different set of endpoints. The matcher prefers exact matches over wildcards, so requests are routed correctly with no extra config.

```yaml
- id: users-list
  path: /api/users            # exact — the collection endpoint
  methods: [GET, POST]
  target: http://user-service:8080
  strip_prefix: /api/users

- id: users-detail
  path: /api/users/*          # wildcard — individual users and sub-resources
  methods: [GET, PUT, DELETE]
  target: http://user-service:8080
  strip_prefix: /api/users
```

| Client request | Matched route | Backend receives |
|---|---|---|
| `GET /api/users` | `users-list` | `GET http://user-service:8080/` |
| `POST /api/users` | `users-list` | `POST http://user-service:8080/` |
| `GET /api/users/42` | `users-detail` | `GET http://user-service:8080/42` |
| `DELETE /api/users/42` | `users-detail` | `DELETE http://user-service:8080/42` |
| `GET /api/users/42/orders` | `users-detail` | `GET http://user-service:8080/42/orders` |

Useful when the collection and item endpoints need different middleware configurations — for example, tighter rate limits on `POST /api/users` (creation) than on `GET /api/users/{id}` (reads), or requiring `users:write` scope only for the collection route.

---

### Example: transform-only route (no auth, no rate limit)

Some public endpoints need only URL rewriting and header handling — no auth, no rate limiting, no custom middleware. Every built-in stage still runs automatically (RequestID, Metrics, Request/Response Transform, Proxy), so `middlewares:` can be empty:

```yaml
- id: public-status
  path: /status/*
  methods: [GET]
  target: http://status-service:8080
  strip_prefix: /status
  add_prefix: /v2
  middlewares: []
```

For every request:

- **RequestID** assigns a correlation id.
- **Request Transform** strips hop-by-hop headers, adds `X-Forwarded-For`.
- **Proxy** streams the request/response through the shared connection pool.
- **Response Transform** adds `X-Gateway-Duration-Ms` and echoes the request id.
- **Metrics** records the outcome.

`GET /status/health` reaches the backend as `GET http://status-service:8080/v2/health`.

---

## Route Storage Options (the operator view: 3 backends user can choose from)

Routes can be persisted in three different backends. The choice is a single env var — `GATEWAY_ROUTE_REPO_BACKEND` — with no code changes required.

| Backend | Value | When to use |
|---|---|---|
| YAML file | `file` | Local dev, single instance, git-versioned config. File may be missing or empty — the gateway boots either way and populates on first Admin API write. |
| Redis | `redis` | Multi-instance deployments. Publishes `gw:routes:changed` events on mutation for future pub/sub-based auto-reload. |
| Postgres | `postgres` | Audit trail, transactional CRUD, joins with operational data. Schema in `scripts/schema.sql`. |

Regardless of the backend, routes are read into an in-memory `RouteRegistry` at startup and on every `POST /admin/reload`. The registry is what every incoming request matches against, so the storage backend does not sit in the hot path.
The "hot path" is the code that runs on **every request**, dozens or hundreds of times per second. Route storage is deliberately kept off the hot path: the file, Redis, or Postgres backend is only touched at two moments — startup and reload. Between those two events, every incoming request is matched against the in-memory `RouteRegistry` with no I/O to the persistent store. This means the choice of storage backend affects boot time and Admin API latency, not per-request latency.

### Multi-instance behavior

Each gateway process holds its own in-memory `RouteRegistry`. If you run more than one gateway instance behind a load balancer, mutating a route on instance A does not automatically reload instance B — each instance must be reloaded (`POST /admin/reload`) or restarted. Redis-based auto-reload via pub/sub is planned but deferred; see `DECISIONS.md` → "Hot Reload".
Single instance is the default; multi-instance needs manual reload for now.

### Enabling and disabling routes

Every route has an `enabled: bool` field (default `true`). The route matcher **skips any route where `enabled` is false**, so a disabled route becomes a 404 without being removed. Toggle via the YAML file:

```yaml
- id: users-api
  path: /api/users/*
  target: http://user-service:8080
  enabled: false
```

Or via the Admin API (`PUT /admin/routes/{id}` with the whole route body and `enabled: false`), then `POST /admin/reload` if you edited the file directly.

---

## Tests

Run the full test suite:

```bash
just test
```

Run tests with coverage:

```bash
just test-all
```

All tests use the in-memory rate-limit store, a YAML route repo pointed at a temp file, and mocked upstreams via `respx` — no Docker, no Redis, no external services required.

---

## Middleware Reference

The gateway pipeline is a fixed sequence. Some stages always run; others are opt-in via a route's `middlewares:` list. All custom middlewares you add sit in a dedicated slot before the proxy.

| Middleware | Type | Runs | How to enable | Route config key |
|---|---|---|---|---|
| RequestID / Logging | Built-in | Always | Automatic | — |
| Metrics start | Built-in | Always | Automatic | — |
| Auth | Built-in | Optional | Add `auth` to `middlewares:` | `middleware_config.auth` |
| Rate Limit | Built-in | Optional | Add `rate_limit` to `middlewares:` | `middleware_config.rate_limit` |
| Request Transform | Built-in | Always | Automatic | — |
| *Your custom middlewares* | Registry | Optional | Add the name to `middlewares:` | `middleware_config.<name>` |
| Proxy | Built-in | Always | Automatic | `target` / `targets` |
| Response Transform | Built-in | Always | Automatic | — |
| Metrics end | Built-in | Always | Automatic | — |

### What the `middlewares:` list controls

- Includes `auth` → the Auth stage runs for this route.
- Includes `rate_limit` → the Rate Limit stage runs for this route.
- Includes any custom middleware name → that middleware runs in the slot between Request Transform and Proxy, in the order it appears in the list.

You **cannot** reorder Auth relative to Rate Limit through this list, nor can you place a custom middleware before Auth. The built-in order is fixed by design. \
Names in the `middlewares:` list are validated at startup and on every reload. Unknown names, reserved built-in names, and orderings that suggest the operator thought the list controls the built-in pipeline all produce WARN logs. Set `GATEWAY_STRICT_VALIDATION=true` to make startup abort on any validation issue; reload-time issues stay warning-only.

### Relationships between middlewares

- **Auth is optional even when Rate Limit is enabled.** Without Auth, the rate-limit key falls back to the client IP — safe, but coarser (a shared IP means a shared bucket).
- **Auth + Rate Limit** is the intended pairing: the key becomes `route:user_id`, so limits are per-user.

### What each middleware do

- **RequestID / Logging** — tags every request with a correlation id (uses one from the client if `X-Request-ID` is set, otherwise generates a UUID) and binds it into log context. Defined in `src/gateway/main.py`.
- **Metrics start / end** — records request count, duration, in-flight count for Prometheus. Definitions in `src/gateway/observability/metrics.py`.
- **Auth** — validates the JWT and enforces scopes. Injects verified identity headers for the backend. See `src/gateway/auth/` for the provider and the auth block inside `src/gateway/main.py`.
- **Rate Limit** — token-bucket per `route:user` (or `route:ip` if no user). Stores in `src/gateway/rate_limit/`.
- **Request Transform** — strips hop-by-hop and client-forbidden headers, adds `X-Forwarded-*`. In `src/gateway/proxy/streaming.py`.
- **Custom middlewares** — your modules in `src/gateway/middlewares/`, auto-imported and run in `middlewares:` list order.
- **Proxy** — streams the request to the chosen backend. In `src/gateway/proxy/`.
- **Response Transform** — adds `X-Gateway-Duration-Ms` and echoes the request id. Tail of `src/gateway/main.py`.

These are defined in `src/gateway/main.py` and cannot be disabled through configuration. If you need to change their behavior, that is a code change.

### Adding a Custom Middleware

1. Create a class in `src/gateway/middlewares/`:

    ```python
   """Injects a header configured per route."""
    from gateway.middlewares.base import (
        GatewayMiddleware, MiddlewareContext, MiddlewareResult, register_middleware
    )

    class HeaderInjector:
        name = "header_injector"
        def __init__(self, config: dict) -> None:
            self._name = config.get("name", "X-Custom")
            self._value = config.get("value", "")

        async def process(self, ctx: MiddlewareContext) -> MiddlewareResult:
            ctx.injected_headers[self._name] = self._value
            return MiddlewareResult()

    register_middleware("header_injector", lambda cfg: HeaderInjector(cfg))
    ```

2. Save it in `src/gateway/middlewares/`. It is auto-imported at startup — no edits to `main.py` needed.

3. Reference it in `routes.yaml`:

    ```yaml
    - id: example
      path: /example/*
      target: http://echo-service:8080
      middlewares: [auth, header_injector, rate_limit]
      middleware_config:
        header_injector:
          name: X-Test
          value: bla
    ```

4. Order in the `middlewares` list defines execution order.

5. There is no explicit `call_next`. Middlewares run sequentially. Return `MiddlewareResult()` to continue the chain or `MiddlewareResult(short_circuit=Response(...))` to stop it and send that response to the client.

6. Verify:

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/example/123
```

---

## Getting a JWT via Swagger

1. Open `http://localhost:8080/docs`.
2. Call `POST /mock-auth/token` with `{"sub":"user-1","scopes":["users:read"]}`.
3. Copy the `access_token` from the response.
4. Click **Authorize** at the top of the page and paste the token.
5. Subsequent Swagger calls include it automatically.

---

## Admin API

The Admin API is a set of HTTP endpoints for managing the gateway's runtime configuration without restarting the process. Every call must include the `x-admin-token` header with the value matching `GATEWAY_ADMIN_TOKEN`.

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/admin/routes` | List all currently loaded routes |
| POST | `/admin/routes` | Create a new route |
| PUT | `/admin/routes/{id}` | Update an existing route |
| DELETE | `/admin/routes/{id}` | Remove a route |
| POST | `/admin/reload` | Re-read routes from the repository and atomically swap the in-memory registry |

### Authentication

The gateway checks the `x-admin-token` header on every `/admin/*` request. If the header is missing or does not match `GATEWAY_ADMIN_TOKEN`, the gateway returns `401 Unauthorized` before running any admin action. This check is separate from the JWT-based auth used for regular proxied traffic — Admin API endpoints do not accept JWTs, and normal routes do not accept the admin token.

### Examples

List all routes:

```bash
curl -H "x-admin-token: admin-dev-token" http://localhost:8080/admin/routes
```

Add a new route:

```bash
curl -X POST http://localhost:8080/admin/routes \
  -H "x-admin-token: admin-dev-token" \
  -H "content-type: application/json" \
  -d '{
    "id": "orders-api",
    "path": "/api/orders/*",
    "methods": ["GET", "POST"],
    "target": "http://orders-service:8080",
    "strip_prefix": "/api/orders",
    "middlewares": ["auth", "rate_limit"],
    "middleware_config": {
      "auth": {"required": true, "scopes": ["orders:read"]},
      "rate_limit": {"capacity": 100, "refill_per_second": 5.0}
    }
  }'
```

Force a reload after editing `routes.yaml` directly:

```bash
curl -X POST -H "x-admin-token: admin-dev-token" http://localhost:8080/admin/reload
```

Set the admin token via environment variable — default is `admin-dev-token`, which must be rotated for any production deployment.

---

## Example Requests

See `examples/e2e_curl.sh` (Linux/macOS) or `examples/e2e_curl.ps1` (Windows) for a full walkthrough. A quick sample:

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/mock-auth/token \
  -H 'content-type: application/json' \
  -d '{"sub":"u1","scopes":["users:read"]}' | jq -r .access_token)

curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/users/1
```

## Advanced: Testing Auth Failures
The mock token endpoint lets you construct tokens with specific properties for testing auth failure paths. All examples assume the gateway is on `http://localhost:8080`.

### Case 0 — Valid token (200)

Issue a token with the exact scope the route requires, then send it:

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/mock-auth/token \
  -H 'content-type: application/json' \
  -d '{"sub":"user-1","scopes":["users:read"],"ttl_seconds":3600}' \
  | jq -r .access_token)

curl -si -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/users/42
```

Expected: `200 OK` with the echoed request body (echo-service is the local target for `/api/users/*`).

In Swagger: call `POST /mock-auth/token` with `{"sub":"user-1","scopes":["users:read"]}`, copy `access_token`, click **Authorize** at the top of the page, paste `Bearer <token>`, then hit any auth-required endpoint.

### Case 1 — No credentials (401)

Simply omit the `Authorization` header:

```bash
curl -si http://localhost:8080/api/users/42
```

Expected: `401 {"error":"missing token"}`.

In Swagger: do not click **Authorize**, then call an auth-required endpoint.

### Case 2 — Wrong scope (403)

Issue a token with a scope that does not match what the route requires:

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/mock-auth/token \
  -H 'content-type: application/json' \
  -d '{"sub":"user-1","scopes":["other:scope"],"ttl_seconds":3600}' \
  | jq -r .access_token)

curl -si -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/users/42
```

Expected: `403 {"error":"insufficient scope"}`.

In Swagger: call `POST /mock-auth/token` with `{"sub":"u1","scopes":["other:scope"]}`, click **Authorize**, paste the token, then hit an endpoint that requires `users:read`.

### Case 3 — Expired token (401)

Set the TTL to one second and wait:

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/mock-auth/token \
  -H 'content-type: application/json' \
  -d '{"sub":"user-1","scopes":["users:read"],"ttl_seconds":1}' \
  | jq -r .access_token)

sleep 2
curl -si -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/users/42
```

Expected: `401 {"error":"invalid token"}`.

### Case 4 — Tampered signature (401)

Issue a normal token, mutate any character, and send it:

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/mock-auth/token \
  -H 'content-type: application/json' \
  -d '{"sub":"user-1","scopes":["users:read"]}' \
  | jq -r .access_token)

BAD_TOKEN="${TOKEN}X"
curl -si -H "Authorization: Bearer $BAD_TOKEN" http://localhost:8080/api/users/42
```

Expected: `401 {"error":"invalid token"}`.

### Summary

| Case | How to build it | Expected status |
|---|---|---|
| Valid token | Correct scope, unexpired, unmodified | 200 |
| Missing token | Send no `Authorization` header | 401 |
| Wrong scope | `scopes: ["other:scope"]` in `/mock-auth/token` | 403 |
| Expired token | `ttl_seconds: 1`, then wait | 401 |
| Tampered signature | Append any character to a valid token | 401 |

Wrong-audience and wrong-issuer tokens cannot be produced by `/mock-auth/token` because it always signs with the configured `iss` and `aud`. To test those, mint a token yourself with a different secret or claims (there is example code in `tests/test_auth_middleware.py`).

---

## Circuit Breaker

Each backend has three states:

- **CLOSED** — normal; failures counted.
- **OPEN** — after `failure_threshold` consecutive failures, all requests fail fast with 503 for `cooldown_seconds`.
- **HALF-OPEN** — after cooldown, `half_open_max_calls` probes allowed. Success → CLOSED. Failure → back to OPEN.

Configured per route in `routes.yaml`. Prevents cascading failures when a backend degrades.

---

## Prometheus

Scrape `http://localhost:8080/metrics`.

```yaml
scrape_configs:
  - job_name: gateway
    scrape_interval: 5s
    static_configs:
      - targets: ["localhost:8080"]
```

---

## Configuration Reference

All settings load via `pydantic-settings` from environment variables (prefixed `GATEWAY_`) or a `.env` file.

### Backend selectors

| Variable | Values | Meaning |
|---|---|---|
| `GATEWAY_STORE_BACKEND` | `memory` \| `redis` | Where rate-limit counters live. |
| `GATEWAY_AUTH_BACKEND` | `mock` \| `oidc` | Auth provider. |
| `GATEWAY_ROUTE_REPO_BACKEND` | `file` \| `redis` \| `postgres` | Where route definitions are persisted. |

### Connection strings

| Variable | Default | Meaning |
|---|---|---|
| `GATEWAY_REDIS_URL` | `redis://localhost:6379/0` | Used by both the Redis rate-limit store and the Redis route repo. |
| `GATEWAY_POSTGRES_DSN` | `postgresql://gateway:gateway@localhost:5432/gateway` | Used only by the Postgres route repo. |
| `GATEWAY_ROUTES_FILE_PATH` | `./routes.yaml` | Path used by the YAML route repo. File may be missing or empty. |

### Auth

| Variable | Default | Meaning |
|---|---|---|
| `GATEWAY_JWT_SECRET` | `dev-secret-change-me` | HMAC secret for the mock provider. Must be changed outside dev. |
| `GATEWAY_JWT_ALGORITHM` | `HS256` | Signing algorithm. |
| `GATEWAY_JWT_ISSUER` | `mock-auth` | Validated against the `iss` claim. |
| `GATEWAY_JWT_AUDIENCE` | `api-gateway` | Validated against the `aud` claim. |

### Behavior

| Variable | Default | Meaning |
|---|---|---|
| `GATEWAY_RATE_LIMIT_FAIL_MODE` | `open` | `open` = allow request when store is unreachable. `closed` = return 503. |
| `GATEWAY_BACKEND_TIMEOUT_SECONDS` | `30` | Max upstream read/write time before returning 504. |
| `GATEWAY_BACKEND_CONNECT_TIMEOUT_SECONDS` | `5` | Max upstream connect time. |
| `GATEWAY_STRICT_VALIDATION` | `false` | If `true`, middleware-list validation errors abort startup instead of just logging warnings. Reload-time errors always downgrade to warnings so a bad admin update cannot kill a running gateway. |

### Observability

| Variable | Default | Meaning |
|---|---|---|
| `GATEWAY_LOG_LEVEL` | `INFO` | Standard log-level name. |
| `GATEWAY_LOG_FORMAT` | `pretty` | `pretty` for local dev, `json` for aggregators. |

### Admin

| Variable | Default | Meaning                                                                                                                                                                                                                                     |
|---|---|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `GATEWAY_ADMIN_TOKEN` | `admin-dev-token` | Required in `x-admin-token` header for `/admin/*` calls. Rotate for production. When any request arrives at an /admin/* endpoint, the Admin API router looks at the incoming `x-admin-token` header and compare it to the configured value. |

---

## Migration

Local dev uses in-memory rate limiting, YAML route storage, and a mock auth provider. Production swaps each of these for real services — one env var per swap, zero code changes.

### From local to Docker Compose

**What changes:**

- Backend URLs use **service names** instead of `localhost` — Docker's embedded DNS resolves `echo-service` to the container.
- Backend ports become **container internal ports** (`8080`), not the host-mapped ports (`9001–9003`).
- Redis URL becomes `redis://redis:6379/0`.
- Postgres DSN becomes `postgresql://gateway:gateway@postgres:5432/gateway`.

Files involved: `routes.docker.yaml` and `.env.docker`. Run `docker compose up --build`.

### Migrating rate limiting: in-memory → Redis

**What "Redis for rate limit" means:** the token-bucket counters live in Redis instead of the gateway's process memory. Redis is fast enough to keep sub-millisecond overhead, and all gateway instances share the same counters so a user gets one rate limit total, not one per instance. Atomicity comes from a Lua script.

Steps:

1. Set `GATEWAY_STORE_BACKEND=redis` and `GATEWAY_REDIS_URL=redis://<host>:6379/<db>`.
2. Restart the gateway.
3. Confirm the log line `gateway.started` still appears and responses carry `X-RateLimit-*` headers.
4. Verify fail-open by temporarily stopping Redis — requests should still succeed with a `rate_limit.store_error` warning logged. Set `GATEWAY_RATE_LIMIT_FAIL_MODE=closed` to switch to 503 instead.

### Migrating route storage: YAML → Redis or Postgres

**What "Redis for route repo" means:** route definitions live in Redis instead of a YAML file. Useful for multi-instance deployments — when one gateway instance mutates a route, all others receive a pub/sub notification and can reload their in-memory registry.

**What "Postgres for route repo" means:** routes live in a relational table with transactional CRUD, indexes, and space for an audit table. Best when you want an audit trail or want to join routes with operational data.

Redis steps:

1. Start Redis.
2. Set `GATEWAY_ROUTE_REPO_BACKEND=redis` and `GATEWAY_REDIS_URL=redis://<host>:6379/<db>`.
3. Seed initial data: `just seed-routes routes.yaml`.
4. Restart the gateway.

Postgres steps:

1. Start Postgres and apply the schema: `psql "$GATEWAY_POSTGRES_DSN" -f scripts/schema.sql` (Docker Compose applies this automatically).
2. Set `GATEWAY_ROUTE_REPO_BACKEND=postgres` and `GATEWAY_POSTGRES_DSN=...`.
3. Seed initial data: `just seed-routes routes.yaml`.
4. Restart the gateway.

### Migrating auth: mock → real OIDC provider

**What changes:** the mock provider signs JWTs with a static HS256 secret — fine for dev, unusable in production. A real IdP signs with RS256/ES256 and publishes its public keys at a JWKS endpoint. The gateway fetches and caches those keys, then verifies incoming tokens against them.

Steps:

1. Implement `OidcAuthProvider` (stub in `src/gateway/auth/`). It must fetch `<issuer>/.well-known/openid-configuration` at startup, cache JWKS with a TTL, refetch on key-id miss, and verify signature + `iss` + `aud` + `exp` + `nbf`.
2. Add env vars:

    ```
    GATEWAY_AUTH_BACKEND=oidc
    GATEWAY_OIDC_ISSUER=https://your-idp.example.com
    GATEWAY_OIDC_AUDIENCE=api-gateway
    GATEWAY_OIDC_JWKS_CACHE_TTL_SECONDS=3600
    ```

3. In `main.py`, swap the Swagger security scheme from `HTTPBearer` to `OAuth2AuthorizationCodeBearer` pointing at your IdP's `/authorize` and `/token`.
4. Delete `src/gateway/auth/mock_provider.py` and `src/gateway/auth/router.py`, and remove the conditional `include_router(mock_auth_router)` line in `main.py`.
5. Update `.env.docker` and production `.env`.

### Cross-cutting post-migration checks

- Test suite passes against the new backends (`just test`).
- `/metrics` includes new dimensions (Redis latency, JWKS fetch counts).
- Structured logs still include `request_id`.
- Load test confirms p95 latency stays within budget with real round-trips.