"""Schema snapshot — schema viewer aur LLM prompt dono ke liye.

Role ke hisaab se filtered: blocked tables/columns LLM prompt me kabhi nahi jaate.
Low-cardinality text columns ke values aur date columns ki range bhi (LLM ko "Delhi" ki spelling
aur "February = kaunsa saal" pata chale).
"""
import time
from dataclasses import dataclass, field, replace

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.services.sql_validator.policy import SENSITIVE_COLUMNS, policy_for, table_allowed

CACHE_TTL_S = 600
MAX_TABLES = 40
MAX_DISTINCT = 20

_cache: dict[str, tuple[float, list]] = {}


@dataclass
class ColumnInfo:
    name: str
    type: str
    sensitive: bool = False
    values: list[str] = field(default_factory=list)
    min: str | None = None
    max: str | None = None


@dataclass
class TableInfo:
    name: str
    columns: list[ColumnInfo]


def _is_temporal(t: str) -> bool:
    t = t.upper()
    return "DATE" in t or "TIME" in t


def _is_text(t: str) -> bool:
    t = t.upper()
    return any(k in t for k in ("CHAR", "TEXT", "STRING"))


def _scalar_row(engine: Engine, sql: str):
    with engine.connect() as conn:
        if engine.dialect.name == "sqlite":
            conn.exec_driver_sql("PRAGMA query_only = ON")
        rows = conn.execute(text(sql)).all()
        conn.rollback()
    return rows


def _profile(engine: Engine) -> list[TableInfo]:
    insp = inspect(engine)
    q = engine.dialect.identifier_preparer.quote
    out = []
    for tname in sorted(insp.get_table_names())[:MAX_TABLES]:
        if not table_allowed("admin", tname):          # app / system tables kabhi nahi
            continue
        cols = []
        for c in insp.get_columns(tname):
            ci = ColumnInfo(c["name"], str(c["type"]))
            lname = ci.name.lower()
            try:
                if _is_temporal(ci.type):
                    lo, hi = _scalar_row(engine, f"SELECT MIN({q(ci.name)}), MAX({q(ci.name)}) FROM {q(tname)}")[0]
                    ci.min, ci.max = (str(lo) if lo is not None else None), (str(hi) if hi is not None else None)
                elif _is_text(ci.type) and lname not in SENSITIVE_COLUMNS and not lname.endswith("id"):
                    rows = _scalar_row(engine, f"SELECT DISTINCT {q(ci.name)} FROM {q(tname)} "
                                               f"WHERE {q(ci.name)} IS NOT NULL LIMIT {MAX_DISTINCT + 1}")
                    if len(rows) <= MAX_DISTINCT:
                        ci.values = sorted(str(r[0]) for r in rows)
            except Exception:  # profiling best-effort hai (permissions / huge tables)
                pass
            cols.append(ci)
        out.append(TableInfo(tname, cols))
    return out


def clear_cache() -> None:
    _cache.clear()


def schema_snapshot(engine: Engine, role: str, refresh: bool = False) -> list[TableInfo]:
    key = str(engine.url)                       # password masked hota hai
    hit = _cache.get(key)
    if refresh or hit is None or time.time() - hit[0] > CACHE_TTL_S:
        hit = (time.time(), _profile(engine))
        _cache[key] = hit
    blocked = policy_for(role).blocked_columns
    return [
        TableInfo(t.name, [replace(c, sensitive=c.name.lower() in blocked) for c in t.columns])
        for t in hit[1] if table_allowed(role, t.name)
    ]


def sensitive_tables(tables: list[TableInfo]) -> dict[str, set[str]]:
    out = {t.name: {c.name.lower() for c in t.columns if c.sensitive} for t in tables}
    return {k: v for k, v in out.items() if v}


def table_doc(t: TableInfo) -> str:
    """LLM prompt ke liye table description — sensitive columns hata kar."""
    parts = []
    for c in t.columns:
        if c.sensitive:
            continue
        s = f"{c.name} {c.type}"
        if c.values:
            s += f" -- values: {', '.join(c.values)}"
        if c.min is not None:
            s += f" -- range: {c.min} .. {c.max}"
        parts.append(s)
    return f"TABLE {t.name} (\n  " + ",\n  ".join(parts) + "\n)"
