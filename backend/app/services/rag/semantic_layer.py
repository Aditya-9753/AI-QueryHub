"""Semantic layer = SQL ka single source of truth. LLM formula nahi likhta, sirf metric name + params chunta hai."""
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date

from sqlglot import exp


class UnknownMetric(KeyError):
    pass


@dataclass(frozen=True)
class MetricDef:
    name: str
    definition: str
    table: str
    expression: str
    time_column: str = "created_at"
    base_filter: str | None = None
    grain: str = "day"
    dimensions: tuple[str, ...] = ("city", "category", "channel")
    version: int = 1
    # data health (Step V) ke liye
    key_columns: tuple[str, ...] = ("order_id",)
    required_columns: tuple[str, ...] = ("amount", "city", "category", "status")
    updated_column: str | None = "updated_at"
    unit: str = "count"                       # inr | count | ratio


DEFAULT_METRICS = [
    MetricDef("revenue", "Non-cancelled orders ka total amount", "orders", "SUM(amount)",
              base_filter="status <> 'cancelled'", unit="inr"),
    MetricDef("orders", "Non-cancelled orders ki count", "orders", "COUNT(*)",
              base_filter="status <> 'cancelled'"),
    MetricDef("placed_orders", "Saare placed orders (cancelled samet)", "orders", "COUNT(*)"),
    MetricDef("aov", "Average order value = revenue / orders", "orders",
              "SUM(amount) * 1.0 / NULLIF(COUNT(*), 0)", base_filter="status <> 'cancelled'", unit="inr"),
    MetricDef("cancel_rate", "Cancelled orders / total orders", "orders",
              "AVG(CASE WHEN status = 'cancelled' THEN 1.0 ELSE 0.0 END)", unit="ratio"),
    MetricDef("payments_revenue", "Payments table se revenue (reconciliation path)", "payments",
              "SUM(amount)", time_column="paid_at", dimensions=("city", "method"), key_columns=("id",),
              required_columns=("amount", "city"), updated_column=None, unit="inr"),
]


def daily_sales_metrics(table: str = "daily_sales") -> list[MetricDef]:
    """Benchmark generator ka aggregated fact table: date, city, category, orders, cancelled, revenue."""
    common = dict(table=table, time_column="date", dimensions=("city", "category"),
                  key_columns=("date", "city", "category"), required_columns=("revenue", "orders", "city", "category"),
                  updated_column=None)
    return [
        MetricDef("revenue", "Net revenue (cancelled excluded)", expression="SUM(revenue)", unit="inr", **common),
        MetricDef("orders", "Non-cancelled orders", expression="SUM(orders - cancelled)", **common),
        MetricDef("placed_orders", "Saare placed orders", expression="SUM(orders)", **common),
        MetricDef("aov", "Revenue / non-cancelled orders",
                  expression="SUM(revenue) * 1.0 / NULLIF(SUM(orders - cancelled), 0)", unit="inr", **common),
        MetricDef("cancel_rate", "Cancelled / placed", expression="SUM(cancelled) * 1.0 / NULLIF(SUM(orders), 0)",
                  unit="ratio", **common),
    ]


def _lit(v: str) -> str:
    """Values hamesha quoted literal ban kar jaati hain (injection-safe)."""
    return exp.Literal.string(str(v)).sql()


def month_bounds(period: str) -> tuple[str, str]:
    """'2026-02' -> ('2026-02-01', '2026-03-01')  (end exclusive)."""
    y, m = (int(x) for x in period.split("-")[:2])
    start = date(y, m, 1)
    end = date(y + (m == 12), m % 12 + 1, 1)
    return start.isoformat(), end.isoformat()


def shift_period(period: str, months: int) -> str:
    y, m = (int(x) for x in period.split("-")[:2])
    idx = y * 12 + (m - 1) + months
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def period_days(period: str) -> int:
    start, end = month_bounds(period)
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def with_overrides(base: list[MetricDef], rows) -> list[MetricDef]:
    """metric_definitions table (admin edits) code defaults ko override karti hai: definition, formula, grain, version.
    rows: objects with name / definition / formula_sql / grain / version."""
    from dataclasses import replace

    by_name = {r.name: r for r in rows}
    out = []
    for m in base:
        r = by_name.get(m.name)
        out.append(m if r is None else replace(m, definition=r.definition, expression=r.formula_sql,
                                                grain=r.grain, version=r.version))
    return out


def load_semantic_layer(db) -> "SemanticLayer":
    """Pipeline / ASK ke liye: DEFAULT_METRICS + DB overrides (Semantic Layer page se badli definitions)."""
    from sqlalchemy import select

    from app import models

    rows = db.scalars(select(models.MetricDefinition)).all()
    return SemanticLayer(with_overrides(DEFAULT_METRICS, rows))


class SemanticLayer:
    def __init__(self, metrics: list[MetricDef] | None = None) -> None:
        self._metrics = {m.name: m for m in (metrics or DEFAULT_METRICS)}

    def metrics(self) -> list[MetricDef]:
        return list(self._metrics.values())

    def names(self) -> list[str]:
        return list(self._metrics)

    def get(self, name: str) -> MetricDef:
        try:
            return self._metrics[name]
        except KeyError as e:
            raise UnknownMetric(name) from e

    @property
    def version(self) -> str:
        blob = json.dumps([asdict(m) for m in self.metrics()], sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()[:12]

    def grounded(self, metric: str, dimensions: list[str] | tuple[str, ...] = ()) -> bool:
        m = self._metrics.get(metric)
        return m is not None and all(d in m.dimensions for d in dimensions)

    def where(self, metric: str, filters: dict[str, str] | None, start: str | None, end: str | None,
              apply_base_filter: bool = True, as_of: str | None = None) -> list[str]:
        m = self.get(metric)
        filters = filters or {}
        for col in filters:
            if col not in m.dimensions:
                raise ValueError(f"'{col}' is not a dimension of metric '{metric}'")
        where = [m.base_filter] if (m.base_filter and apply_base_filter) else []
        where += [f"{col} = {_lit(v)}" for col, v in filters.items()]
        if start:
            where.append(f"{m.time_column} >= {_lit(start)}")
        if end:
            where.append(f"{m.time_column} < {_lit(end)}")
        if as_of and m.updated_column:     # Ch 17: dataset version — baad me aaya/badla data replay ko nahi badalta
            where.append(f"{m.updated_column} <= {_lit(as_of)}")
        return where

    def render(self, metric: str, filters: dict[str, str] | None = None, start: str | None = None,
               end: str | None = None, group_by: tuple[str, ...] = (), per_day: bool = False,
               as_of: str | None = None) -> str:
        m = self.get(metric)
        for col in group_by:
            if col not in m.dimensions:
                raise ValueError(f"'{col}' is not a dimension of metric '{metric}'")
        where = self.where(metric, filters, start, end, as_of=as_of)

        keys = list(group_by)
        select = list(group_by)
        if per_day:
            select.insert(0, f"DATE({m.time_column}) AS day")
            keys.insert(0, f"DATE({m.time_column})")
        select.append(f"{m.expression} AS {m.name}")

        sql = f"SELECT {', '.join(select)} FROM {m.table}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        if keys:
            sql += " GROUP BY " + ", ".join(keys) + " ORDER BY " + ", ".join(keys)
        return sql
