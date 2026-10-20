"""Validated SQL ko read-only engine par chalao + SHA-256 checksum (provenance)."""
import hashlib
import json
import time
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.core.config import get_settings
from app.db.session import readonly_engine

SAMPLE_ROWS = 100   # storage watch-item: experiment record me <= 100 sample rows


@dataclass
class ExecutionResult:
    sql: str
    sql_hash: str
    columns: list[str]
    rows: list[list]          # sample (<= SAMPLE_ROWS)
    all_rows: list[list]      # analytics ke liye (DB me store mat karo)
    row_count: int
    duration_ms: float
    checksum: str


def _jsonable(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def checksum_rows(rows: list[list]) -> str:
    """SHA-256 of sorted rows — exact replay me match hona chahiye."""
    canon = sorted(json.dumps(r, default=str) for r in rows)
    return sha256("\n".join(canon))


def sql_dialect(engine: Engine | None = None) -> str:
    name = (engine or readonly_engine).dialect.name
    return "postgres" if name.startswith("postgres") else name


def run_sql(sql: str, engine: Engine | None = None) -> ExecutionResult:
    engine = engine or readonly_engine
    timeout_ms = get_settings().statement_timeout_ms
    with engine.connect() as conn:
        if engine.dialect.name == "sqlite":
            conn.exec_driver_sql("PRAGMA query_only = ON")
        elif engine.dialect.name.startswith("postgres"):
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            conn.exec_driver_sql(f"SET LOCAL statement_timeout = {int(timeout_ms)}")
        t0 = time.perf_counter()
        res = conn.execute(text(sql))
        columns = list(res.keys())
        rows = [[_jsonable(v) for v in r] for r in res.fetchall()]
        duration_ms = (time.perf_counter() - t0) * 1000
        conn.rollback()
    return ExecutionResult(sql=sql, sql_hash=sha256(sql), columns=columns, rows=rows[:SAMPLE_ROWS],
                           all_rows=rows, row_count=len(rows), duration_ms=round(duration_ms, 2),
                           checksum=checksum_rows(rows))
