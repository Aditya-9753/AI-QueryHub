"""Layer 3: RBAC table/column policy.

- App tables (users, experiments, audit_log, ...) aur system catalogs kisi bhi role ko SQL se nahi dikhte.
- Sensitive columns role ke hisaab se block; SELECT * un tables par jinke sensitive columns hain — block.
"""
from dataclasses import dataclass

from sqlglot import exp

import app.models  # noqa: F401  — Base.metadata me app tables register karne ke liye
from app.db.base import Base
from app.services.sql_validator.parser import columns_in, tables_in
from app.services.sql_validator.safety_rules import UnsafeSQL

SYSTEM_SCHEMAS = {"information_schema", "pg_catalog"}
SYSTEM_PREFIXES = ("pg_", "sqlite_")
SENSITIVE_COLUMNS = frozenset({"email", "phone", "password_hash", "conn_secret_ref"})
SEMANTIC_TABLES = frozenset({"orders", "payments"})          # viewer sirf semantic-layer tables
KNOWN_SENSITIVE_TABLES = {"customers": {"email", "phone"}}   # schema snapshot na ho tab ka fallback


def app_tables() -> frozenset[str]:
    return frozenset(Base.metadata.tables) | {"alembic_version"}


class AllExcept:
    """`name in AllExcept(denied)` => business table hai (app/system table nahi)."""

    def __init__(self, denied: frozenset[str]) -> None:
        self.denied = denied

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name not in self.denied and not name.startswith(SYSTEM_PREFIXES)


@dataclass(frozen=True)
class Policy:
    tables: frozenset[str] | None          # None => saari business tables
    blocked_columns: frozenset[str]


ROLE_POLICIES = {
    "admin": Policy(None, frozenset({"password_hash", "conn_secret_ref"})),
    "analyst": Policy(None, SENSITIVE_COLUMNS),
    "viewer": Policy(SEMANTIC_TABLES, SENSITIVE_COLUMNS),
}


def policy_for(role: str) -> Policy:
    return ROLE_POLICIES.get(role, ROLE_POLICIES["viewer"])


def allowed_tables(role: str):
    p = policy_for(role)
    denied = app_tables()
    if p.tables is None:
        return AllExcept(denied)
    return {t for t in p.tables if t not in denied}


def table_allowed(role: str, name: str) -> bool:
    return name.lower() in allowed_tables(role)


def check_policy(tree: exp.Expression, role: str, sensitive_tables: dict[str, set[str]] | None = None) -> None:
    for t in tree.find_all(exp.Table):
        if (t.db or "").lower() in SYSTEM_SCHEMAS:
            raise UnsafeSQL(f"system catalog not allowed: {t.db}.{t.name}")
    policy = policy_for(role)
    used = columns_in(tree) & policy.blocked_columns
    if used:
        raise UnsafeSQL(f"column not allowed for role '{role}': {', '.join(sorted(used))}")
    if any(True for _ in tree.find_all(exp.Star)):
        known = sensitive_tables if sensitive_tables is not None else KNOWN_SENSITIVE_TABLES
        hit = {t for t in tables_in(tree) if set(known.get(t, set())) & policy.blocked_columns}
        if hit:
            raise UnsafeSQL(f"SELECT * not allowed on table with sensitive columns: {', '.join(sorted(hit))}")


# backward-compatible naam
check_columns = check_policy
