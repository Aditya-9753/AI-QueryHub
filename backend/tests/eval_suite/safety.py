"""Safety Block Rate (Ch 18): unsafe SQL firewall par block honi chahiye (target 100%), safe SQL pass.

    cd backend && python -m tests.eval_suite.safety
"""
import json
import time
from pathlib import Path

from app.services.sql_validator.firewall import firewall_check
from app.services.sql_validator.safety_rules import UnsafeSQL

UNSAFE = [
    "DROP TABLE orders", "DELETE FROM orders", "UPDATE orders SET amount = 0", "INSERT INTO orders VALUES (1)",
    "TRUNCATE orders", "ALTER TABLE orders ADD COLUMN x INT", "CREATE TABLE x (a INT)",
    "SELECT 1; DELETE FROM orders", "SELECT pg_sleep(10)", "SELECT pg_read_file('/etc/passwd')",
    "SELECT * FROM users", "SELECT password_hash FROM users", "SELECT * FROM audit_log",
    "SELECT * FROM information_schema.tables", "SELECT * FROM pg_catalog.pg_user", "SELECT name FROM sqlite_master",
    "SELECT * INTO backup FROM orders", "COPY orders TO '/tmp/x'", "GRANT ALL ON orders TO public",
    "SELECT email FROM customers", "SELECT * FROM customers", "WITH x AS (DELETE FROM orders RETURNING *) SELECT * FROM x",
    "SELECT 1 /* x */; DrOp TABLE orders -- y", "EXPLAIN ANALYZE DELETE FROM orders", "VACUUM orders",
]
SAFE = [
    "SELECT city, SUM(amount) FROM orders GROUP BY city", "SELECT COUNT(*) FROM orders",
    "WITH t AS (SELECT city FROM orders) SELECT * FROM t", "SELECT method, SUM(amount) FROM payments GROUP BY method",
    "SELECT city FROM orders UNION SELECT city FROM payments",
]


def main() -> None:
    def blocked(sql: str) -> bool:
        try:
            firewall_check(sql, role="analyst")
            return False
        except UnsafeSQL:
            return True
        except Exception:
            return True
    unsafe = [{"sql": s, "blocked": blocked(s)} for s in UNSAFE]
    safe = [{"sql": s, "blocked": blocked(s)} for s in SAFE]
    res = {"unsafe_total": len(unsafe), "unsafe_blocked": sum(x["blocked"] for x in unsafe),
           "block_rate": sum(x["blocked"] for x in unsafe) / len(unsafe),
           "safe_total": len(safe), "safe_passed": sum(not x["blocked"] for x in safe),
           "missed": [x["sql"] for x in unsafe if not x["blocked"]],
           "false_blocks": [x["sql"] for x in safe if x["blocked"]],
           "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    out = Path(__file__).parent / "results"
    out.mkdir(exist_ok=True)
    (out / "safety_latest.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
