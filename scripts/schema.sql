-- Postgres schema for PostgresRouteRepository.
-- Apply via: psql $GATEWAY_POSTGRES_DSN -f scripts/schema.sql
-- Docker Compose auto-applies this on postgres container init.

CREATE TABLE IF NOT EXISTS routes (
    id                  TEXT PRIMARY KEY,
    path                TEXT NOT NULL,
    methods             TEXT[] NOT NULL DEFAULT ARRAY['GET'],
    targets             JSONB NOT NULL,
    load_balancer       TEXT NOT NULL DEFAULT 'round_robin',
    strip_prefix        TEXT,
    add_prefix          TEXT,
    enabled             BOOLEAN NOT NULL DEFAULT TRUE,
    priority            INTEGER NOT NULL DEFAULT 0,
    middlewares         JSONB NOT NULL DEFAULT '[]'::jsonb,
    middleware_config   JSONB NOT NULL DEFAULT '{}'::jsonb,
    health_check        JSONB,
    circuit_breaker     JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_routes_enabled_priority
    ON routes (enabled, priority DESC);

CREATE OR REPLACE FUNCTION routes_touch_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_routes_touch ON routes;
CREATE TRIGGER trg_routes_touch
    BEFORE UPDATE ON routes
    FOR EACH ROW EXECUTE FUNCTION routes_touch_updated_at();

CREATE TABLE IF NOT EXISTS routes_audit (
    audit_id    BIGSERIAL PRIMARY KEY,
    route_id    TEXT NOT NULL,
    action      TEXT NOT NULL,
    snapshot    JSONB NOT NULL,
    changed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);