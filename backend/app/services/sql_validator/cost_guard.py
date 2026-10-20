"""Layer 4: cost guard — LIMIT clamp, statement timeout, EXPLAIN cost threshold."""
import json

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlglot import exp

MAX_PLAN_COST = 1_000_000.0


def enforce_limit(tree: exp.Expression, max_rows: int) -> exp.Expression:
    if not isinstance(tree, exp.Select):
        return tree
    limit = tree.args.get("limit")
    if limit is None:
        return tree.limit(max_rows)
    try:
        if int(limit.expression.name) > max_rows:
            return tree.limit(max_rows)
    except (AttributeError, ValueError):
        return tree.limit(max_rows)        # non-literal LIMIT (subquery/param) -> clamp
    return tree


def explain_cost(sql: str, engine: Engine) -> float | None:
    """Postgres: EXPLAIN (FORMAT JSON) ka Total Cost. Doosre DB par None."""
    if not engine.dialect.name.startswith("postgres"):
        return None
    with engine.connect() as conn:
        plan = conn.execute(text(f"EXPLAIN (FORMAT JSON) {sql}")).scalar()
    plan = json.loads(plan) if isinstance(plan, str) else plan
    return float(plan[0]["Plan"]["Total Cost"])


def cost_ok(sql: str, engine: Engine, max_cost: float = MAX_PLAN_COST) -> bool:
    cost = explain_cost(sql, engine)
    return cost is None or cost <= max_cost
