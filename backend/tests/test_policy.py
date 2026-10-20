import pytest

from app.services.sql_validator.firewall import firewall_check
from app.services.sql_validator.safety_rules import UnsafeSQL


@pytest.mark.parametrize("sql, msg", [
    ("SELECT * FROM users", "table not allowed: users"),
    ("SELECT * FROM audit_log", "table not allowed: audit_log"),
    ("SELECT name FROM sqlite_master", "table not allowed: sqlite_master"),
    ("SELECT * FROM information_schema.tables", "system catalog"),
    ("SELECT usename FROM pg_catalog.pg_user", "table not allowed"),
])
def test_app_and_system_tables_blocked_even_for_admin(sql, msg):
    with pytest.raises(UnsafeSQL, match=msg):
        firewall_check(sql, role="admin")


def test_business_tables_open_for_analyst():
    assert firewall_check("SELECT region FROM sales_2026", role="analyst")
    with pytest.raises(UnsafeSQL):
        firewall_check("SELECT region FROM sales_2026", role="viewer")


def test_snapshot_sensitive_map_for_star():
    with pytest.raises(UnsafeSQL, match="SELECT \\*"):
        firewall_check("SELECT * FROM leads", role="analyst", sensitive_tables={"leads": {"email"}})
    assert firewall_check("SELECT * FROM leads", role="analyst", sensitive_tables={})
