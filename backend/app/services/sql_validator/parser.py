"""sqlglot parse helpers."""
import sqlglot
from sqlglot import exp

from app.services.sql_validator.safety_rules import UnsafeSQL


def parse_single(sql: str, dialect: str = "postgres") -> exp.Expression:
    try:
        stmts = sqlglot.parse(sql, read=dialect)
    except sqlglot.errors.ParseError as e:
        raise UnsafeSQL(f"could not parse SQL: {e}") from e
    if len(stmts) != 1 or stmts[0] is None:
        raise UnsafeSQL("exactly one statement allowed")
    return stmts[0]


def tables_in(tree: exp.Expression) -> set[str]:
    return {t.name.lower() for t in tree.find_all(exp.Table)}


def columns_in(tree: exp.Expression) -> set[str]:
    return {c.name.lower() for c in tree.find_all(exp.Column)}
