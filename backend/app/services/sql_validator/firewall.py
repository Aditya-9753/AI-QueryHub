"""4-layer SQL firewall entrypoint (Ch 16). Layer 1 (read-only DB role) executor me enforce hota hai."""
from sqlalchemy.engine import Engine

from app.core.config import get_settings
from app.services.sql_validator.cost_guard import cost_ok, enforce_limit
from app.services.sql_validator.parser import parse_single
from app.services.sql_validator.policy import allowed_tables, check_policy
from app.services.sql_validator.safety_rules import UnsafeSQL, check_sql


def firewall_check(sql: str, role: str = "analyst", dialect: str = "postgres", max_rows: int | None = None,
                   engine: Engine | None = None, sensitive_tables: dict[str, set[str]] | None = None) -> str:
    settings = get_settings()
    max_rows = max_rows or settings.max_rows
    safe = check_sql(sql, allowed_tables(role), max_rows=max_rows, dialect=dialect)   # layer 2 (AST)
    tree = parse_single(safe, dialect)
    check_policy(tree, role, sensitive_tables)                                         # layer 3 (RBAC)
    out = enforce_limit(tree, max_rows).sql(dialect=dialect)                           # layer 4 (LIMIT)
    if engine is not None and not cost_ok(out, engine, settings.max_plan_cost):        # layer 4 (EXPLAIN)
        raise UnsafeSQL("query too expensive (EXPLAIN cost above limit)")
    return out
