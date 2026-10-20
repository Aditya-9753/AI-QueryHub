-- =====================================================================
-- AI QueryHub — demo BUSINESS schema (jo data Q-TRACE+ analyse karta hai)
-- App / experiment tables Alembic se bante hain (database/migrations/).
-- =====================================================================

CREATE TABLE IF NOT EXISTS customers (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT,
    city        TEXT NOT NULL,
    segment     TEXT,                       -- vip | regular | occasional (lifetime spend)
    email       TEXT,                       -- sensitive (policy layer block karta hai)
    phone       TEXT,                       -- sensitive
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS products (
    id        BIGSERIAL PRIMARY KEY,
    name      TEXT NOT NULL,
    category  TEXT NOT NULL,
    price     NUMERIC(12, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    order_id     BIGSERIAL PRIMARY KEY,
    customer_id  BIGINT REFERENCES customers(id),
    city         TEXT NOT NULL,
    category     TEXT NOT NULL,
    channel      TEXT NOT NULL DEFAULT 'app',     -- app | web
    amount       NUMERIC(12, 2) NOT NULL,
    status       TEXT NOT NULL DEFAULT 'placed',  -- placed | cancelled
    created_at   TIMESTAMPTZ NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_orders_created_city ON orders (created_at, city);

CREATE TABLE IF NOT EXISTS payments (
    id        BIGSERIAL PRIMARY KEY,
    order_id  BIGINT REFERENCES orders(order_id),
    city      TEXT NOT NULL,
    method    TEXT NOT NULL,                      -- upi | card | cod
    amount    NUMERIC(12, 2) NOT NULL,
    paid_at   TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_payments_paid_city ON payments (paid_at, city);

-- ---------------------------------------------------------------------
-- Layer 1 safety: read-only role (Ch 13.5 / Ch 16)
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'queryhub_ro') THEN
        CREATE ROLE queryhub_ro LOGIN PASSWORD 'change-me';
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO queryhub_ro;
GRANT SELECT ON orders, payments, customers, products TO queryhub_ro;
ALTER ROLE queryhub_ro SET default_transaction_read_only = on;
ALTER ROLE queryhub_ro SET statement_timeout = '5s';
