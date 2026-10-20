"""Demo business data seed karta hai (orders + payments).

Run:  cd backend && python ../database/seed_data/seed_demo.py
Feb 2026 Delhi me Electronics share 30% -> ~24% planted hai (Ch 10 worked example jaisa).
"""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

import numpy as np  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db.session import engine  # noqa: E402
from tests.eval_suite.generator import base_daily, expand_to_orders, plant  # noqa: E402

DDL = [
    "DROP TABLE IF EXISTS payments",
    "DROP TABLE IF EXISTS orders",
    """CREATE TABLE orders (
        order_id INTEGER PRIMARY KEY,
        customer_id INTEGER,
        city TEXT NOT NULL,
        category TEXT NOT NULL,
        channel TEXT NOT NULL,
        amount NUMERIC NOT NULL,
        status TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL)""",
    """CREATE TABLE payments (
        id INTEGER PRIMARY KEY,
        order_id INTEGER,
        city TEXT NOT NULL,
        method TEXT NOT NULL,
        amount NUMERIC NOT NULL,
        paid_at TIMESTAMP NOT NULL)""",
    "CREATE INDEX ix_orders_created_city ON orders (created_at, city)",
    "CREATE INDEX ix_payments_paid_city ON payments (paid_at, city)",
]

CITY_SCALE = {"Delhi": 110, "Mumbai": 120, "Pune": 60}


def build(target_engine, start: str = "2025-01-01", end: str = "2026-02-28", factor: float = 0.737,
          seed: int = 7, scale: dict | None = None) -> tuple[int, int]:
    rng = np.random.default_rng(seed)
    daily = base_daily(start, end, rng, cities=scale or CITY_SCALE)
    daily = plant(daily, {"kind": "mix_shift", "city": "Delhi", "category": "Electronics",
                          "start": "2026-02-01", "end": "2026-02-28", "factor": factor}, rng)
    orders, payments = expand_to_orders(daily, rng)
    with target_engine.begin() as conn:
        for stmt in DDL:
            conn.execute(text(stmt))
    orders.to_sql("orders", target_engine, if_exists="append", index=False, chunksize=20000)
    payments.to_sql("payments", target_engine, if_exists="append", index=False, chunksize=20000)
    return len(orders), len(payments)


def main() -> None:
    n_orders, n_payments = build(engine)
    print(f"seeded {n_orders:,} orders and {n_payments:,} payments into {engine.url}")


if __name__ == "__main__":
    main()
