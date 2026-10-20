"""Layer 2: sqlglot AST rules (Ch 13.5). Regex nahi — comments/case/CTE se bypass nahi hota."""
import sqlglot
from sqlglot import exp

BLOCKED_FUNCS = {"pg_sleep", "pg_read_file", "pg_read_binary_file", "pg_ls_dir", "dblink",
                 "lo_import", "lo_export", "load_extension"}
BLOCKED_NODES = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create,
                 exp.Alter, exp.Command, exp.Into)
SET_OPS = (getattr(exp, "SetOperation", exp.Union),)


class UnsafeSQL(Exception):
    pass


def _func_name(node: exp.Expression) -> str:
    if isinstance(node, exp.Anonymous):
        return (node.name or "").lower()
    return node.sql_name().lower()


def check_sql(sql: str, allowed_tables: set[str], max_rows: int = 5000, dialect: str = "postgres") -> str:
    try:
        stmts = sqlglot.parse(sql, read=dialect)
    except sqlglot.errors.ParseError as e:
        raise UnsafeSQL(f"could not parse SQL: {e}") from e
    if len(stmts) != 1 or stmts[0] is None:
        raise UnsafeSQL("exactly one statement allowed")
    tree = stmts[0]
    if not isinstance(tree, (exp.Select, *SET_OPS)):
        raise UnsafeSQL("only SELECT allowed")
    for node in tree.walk():
        if isinstance(node, BLOCKED_NODES):
            raise UnsafeSQL(f"blocked node: {type(node).__name__}")
        if isinstance(node, exp.Func):
            name = _func_name(node)
            if name in BLOCKED_FUNCS:
                raise UnsafeSQL(f"blocked function: {name}")
    ctes = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    for t in tree.find_all(exp.Table):
        name = t.name.lower()
        if name not in allowed_tables and name not in ctes:
            raise UnsafeSQL(f"table not allowed: {name}")
    if isinstance(tree, exp.Select) and not tree.args.get("limit"):
        tree = tree.limit(max_rows)          # automatic LIMIT injection
    return tree.sql(dialect=dialect)
