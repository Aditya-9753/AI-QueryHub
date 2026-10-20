"""SQL firewall (Ch 13.5 / 13.8)."""
import pytest

from app.services.sql_validator.firewall import firewall_check
from app.services.sql_validator.safety_rules import UnsafeSQL, check_sql

ALLOWED = {"orders", "payments"}


def test_limit_injected():
    out = check_sql("SELECT city, SUM(amount) FROM orders GROUP BY city", ALLOWED)
    assert out.endswith("LIMIT 5000")


@pytest.mark.parametrize("sql, msg", [
    ("DROP TABLE orders", "only SELECT allowed"),
    ("SELECT * FROM users", "table not allowed: users"),
    ("SELECT pg_sleep(10)", "blocked function: pg_sleep"),
    ("SELECT 1; DELETE FROM orders", "exactly one statement allowed"),
    ("DELETE FROM orders", "only SELECT allowed"),
    ("SELECT * INTO backup FROM orders", "blocked node"),
])
def test_blocked(sql, msg):
    with pytest.raises(UnsafeSQL, match=msg):
        check_sql(sql, ALLOWED)


def test_cte_allowed():
    sql = "WITH t AS (SELECT city FROM orders) SELECT * FROM t"
    assert "LIMIT" in check_sql(sql, ALLOWED)


def test_comment_bypass_blocked():
    with pytest.raises(UnsafeSQL):
        check_sql("SELECT 1 /* harmless */; DrOp TABLE orders -- x", ALLOWED)


def test_rbac_sensitive_columns():
    with pytest.raises(UnsafeSQL, match="column not allowed"):
        firewall_check("SELECT email FROM customers", role="analyst")
    with pytest.raises(UnsafeSQL, match="SELECT \\*"):
        firewall_check("SELECT * FROM customers", role="analyst")
    assert "email" in firewall_check("SELECT email FROM customers", role="admin")


def test_viewer_tables():
    with pytest.raises(UnsafeSQL, match="table not allowed"):
        firewall_check("SELECT * FROM customers", role="viewer")


def test_limit_clamped():
    assert firewall_check("SELECT city FROM orders LIMIT 999999", role="admin").endswith("LIMIT 5000")
    assert firewall_check("SELECT city FROM orders LIMIT 10", role="admin").endswith("LIMIT 10")
