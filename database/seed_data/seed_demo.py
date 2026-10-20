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

from app.core.config import Settings  # noqa: E402
from app.db.session import engine, make_engine  # noqa: E402
from tests.eval_suite.generator import base_daily, expand_to_orders, plant  # noqa: E402

DDL = [
    "DROP TABLE IF EXISTS payments",
    "DROP TABLE IF EXISTS orders",
    "DROP TABLE IF EXISTS customers",
    """CREATE TABLE customers (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        city TEXT NOT NULL,
        segment TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        created_at TIMESTAMP NOT NULL)""",
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
FIRST = ["Aarav", "Diya", "Kabir", "Isha", "Vihaan", "Ananya", "Arjun", "Meera", "Rohan", "Saanvi", "Kunal", "Tara"]
LAST = ["Sharma", "Verma", "Iyer", "Khan", "Patel", "Reddy", "Gupta", "Das", "Nair", "Singh"]


def build_customers(orders, rng):
    """Synthetic customers (sab nakli: example.com emails, +91-90000 series phones) — role demo ke liye:
    viewer ko table hi nahi dikhti, analyst ko email/phone blocked, admin ko sab."""
    import pandas as pd

    g = orders.groupby("customer_id").agg(city=("city", lambda s: s.mode().iat[0]), spend=("amount", "sum"),
                                          first=("created_at", "min")).reset_index()
    hi, lo = g["spend"].quantile(0.9), g["spend"].quantile(0.3)
    ids = g["customer_id"].to_numpy()
    first = [FIRST[i % len(FIRST)] for i in ids]
    last = [LAST[(i // len(FIRST)) % len(LAST)] for i in ids]
    signup = pd.to_datetime(g["first"]) - pd.to_timedelta(rng.integers(0, 120, len(g)), unit="D")
    return pd.DataFrame({
        "id": ids, "name": [f"{a} {b}" for a, b in zip(first, last)], "city": g["city"],
        "segment": ["vip" if s >= hi else "occasional" if s <= lo else "regular" for s in g["spend"]],
        "email": [f"{a.lower()}.{b.lower()}{i}@example.com" for a, b, i in zip(first, last, ids)],
        "phone": [f"+91-90000-{i:05d}" for i in ids],
        "created_at": signup.dt.strftime("%Y-%m-%d %H:%M:%S"),
    })


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
    build_customers(orders, rng).to_sql("customers", target_engine, if_exists="append", index=False, chunksize=20000)
    orders.to_sql("orders", target_engine, if_exists="append", index=False, chunksize=20000)
    payments.to_sql("payments", target_engine, if_exists="append", index=False, chunksize=20000)
    return len(orders), len(payments)


def main() -> None:
    """`python seed_demo.py [DB_URL]` — URL na do to DATABASE_URL. Deploy (Render) par demo data alag read-only
    SQLite file me jaata hai: `python seed_demo.py sqlite:///./demo.db`."""
    target = make_engine(Settings(database_url=sys.argv[1]).database_url) if len(sys.argv) > 1 else engine
    n_orders, n_payments = build(target)
    print(f"seeded {n_orders:,} orders and {n_payments:,} payments into {target.url.render_as_string(hide_password=True)}")


if __name__ == "__main__":
    main()
