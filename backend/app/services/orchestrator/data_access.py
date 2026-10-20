"""Pipeline ka data layer: semantic-layer SQL -> 4-layer firewall -> read-only execute.

Har query ek QueryRecord banti hai (purpose, hypothesis, SQL, checksum) — evidence provenance + exact replay ke liye.
Same SQL dobara maanga jaaye to cache se (budget kharch nahi hota).
"""
from dataclasses import asdict, dataclass, field

import pandas as pd
from sqlalchemy.engine import Engine

from app.services.orchestrator.budget import Budget
from app.services.query_executor.executor import ExecutionResult, run_sql, sql_dialect
from app.services.rag.semantic_layer import SemanticLayer
from app.services.sql_validator.firewall import firewall_check

MAX_ROWS = 50_000


@dataclass
class QueryRecord:
    """Evidence node (Ch 6.2): query_id, metric definition, filters, time window, duration, SHA-256 checksum.
    Dataset version + schema snapshot run-level par (sab queries ke liye same) graph node me jodte hain."""
    id: str
    purpose: str
    hypothesis_key: str | None
    metric: str | None
    table: str | None
    sql: str
    sql_hash: str
    checksum: str
    row_count: int
    duration_ms: float
    metric_definition: str | None = None
    filters: dict = field(default_factory=dict)
    time_window: list = field(default_factory=list)
    group_by: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class DataAccess:
    def __init__(self, engine: Engine, layer: SemanticLayer, role: str = "analyst", budget: Budget | None = None,
                 as_of: str | None = None):
        self.engine, self.layer, self.role = engine, layer, role
        self.budget = budget or Budget()
        self.dialect = sql_dialect(engine)
        self.as_of = as_of
        self.records: list[QueryRecord] = []
        self._cache: dict[str, tuple[ExecutionResult, QueryRecord]] = {}

    def run(self, sql: str, purpose: str, hypothesis_key: str | None = None, metric: str | None = None,
            table: str | None = None, **provenance) -> tuple[ExecutionResult, QueryRecord]:
        safe = firewall_check(sql, role=self.role, dialect=self.dialect, max_rows=MAX_ROWS)
        if safe in self._cache:
            return self._cache[safe]
        self.budget.spend_query()
        res = run_sql(safe, self.engine)
        rec = QueryRecord(f"Q{len(self.records) + 1:02d}", purpose, hypothesis_key, metric, table, safe,
                          res.sql_hash, res.checksum, res.row_count, res.duration_ms, **provenance)
        self.records.append(rec)
        self._cache[safe] = (res, rec)
        return res, rec

    def definition(self, metric: str) -> str:
        m = self.layer.get(metric)
        return f"{m.name} v{m.version}: {m.expression} FROM {m.table}" + (f" WHERE {m.base_filter}" if m.base_filter else "")

    def scalar(self, sql: str, purpose: str, **kw):
        res, _ = self.run(sql, purpose, **kw)
        return res.all_rows[0][0] if res.all_rows else None

    def daily(self, metric: str, filters: dict[str, str], start: str, end: str, group_by: tuple[str, ...] = (),
              purpose: str | None = None, hypothesis_key: str | None = None) -> tuple[pd.DataFrame, QueryRecord]:
        sql = self.layer.render(metric, filters=filters, start=start, end=end, group_by=tuple(group_by), per_day=True,
                                as_of=self.as_of)
        res, rec = self.run(sql, purpose or f"daily:{metric}", hypothesis_key, metric, self.layer.get(metric).table,
                            metric_definition=self.definition(metric), filters=dict(filters), time_window=[start, end],
                            group_by=list(group_by))
        df = pd.DataFrame(res.all_rows, columns=res.columns)
        if df.empty:
            df = pd.DataFrame({c: [] for c in ["day", *group_by, metric]})
        df["day"] = pd.to_datetime(df["day"]).dt.normalize()
        df[metric] = pd.to_numeric(df[metric], errors="coerce").fillna(0.0).astype(float)
        for g in group_by:
            df[g] = df[g].where(df[g].notna(), "(null)").astype(str)
        return df, rec
