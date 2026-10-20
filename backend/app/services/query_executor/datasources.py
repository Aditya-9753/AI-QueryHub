"""Datasource -> read-only engine.

Secrets kabhi DB me nahi jaate (Ch 2.5 / 16): `conn_secret_ref` sirf ek env var ka NAAM hai
(`DS_` prefix, ya default `READONLY_DATABASE_URL`). URL backend `.env` / environment se resolve hota hai.
"""
import os
import time
from functools import lru_cache

from dotenv import dotenv_values
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session

from app import models
from app.core.config import get_settings
from app.db.session import make_engine, readonly_engine
from app.services.query_executor.executor import sql_dialect
from app.services.sql_validator.policy import table_allowed

DEFAULT_ID = "default"
DEFAULT_REF = "READONLY_DATABASE_URL"


class DataSourceError(Exception):
    pass


def ref_allowed(ref: str) -> bool:
    return ref == DEFAULT_REF or ref.startswith(get_settings().datasource_env_prefix)


def _env() -> dict[str, str]:
    values: dict[str, str] = {}
    for path in ("../.env", ".env"):
        values.update({k: v for k, v in dotenv_values(path).items() if v})
    values.update(os.environ)
    return values


def resolve_url(ref: str) -> str:
    if not ref_allowed(ref):
        prefix = get_settings().datasource_env_prefix
        raise DataSourceError(f"conn_secret_ref '{ref}' allowed nahi — env var ka naam '{prefix}' se shuru hona chahiye")
    if ref == DEFAULT_REF:
        return get_settings().readonly_database_url
    url = _env().get(ref)
    if not url:
        raise DataSourceError(f"env var '{ref}' set nahi hai — backend .env me add karke server restart karo")
    return url


@lru_cache(maxsize=16)
def _engine_for_url(url: str) -> Engine:
    return make_engine(url)


def engine_for(db: Session, datasource_id: str | None) -> tuple[str, Engine]:
    if not datasource_id or datasource_id == DEFAULT_ID:
        return DEFAULT_ID, readonly_engine
    ds = db.get(models.DataSource, datasource_id)
    if ds is None:
        raise DataSourceError("datasource not found")
    try:
        return ds.id, _engine_for_url(resolve_url(ds.conn_secret_ref))
    except ArgumentError as e:
        raise DataSourceError(f"invalid connection URL in '{ds.conn_secret_ref}'") from e


def test_connection(engine: Engine) -> dict:
    t0 = time.perf_counter()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        tables = sum(table_allowed("admin", t) for t in inspect(engine).get_table_names())  # app tables nahi gine
        return {"ok": True, "dialect": sql_dialect(engine), "tables": tables,
                "duration_ms": round((time.perf_counter() - t0) * 1000, 1), "error": None}
    except Exception as e:  # connection errors: message user ko dikhao (URL/password nahi)
        msg = str(getattr(e, "orig", e)).splitlines()[0][:300]
        return {"ok": False, "dialect": engine.dialect.name, "tables": 0,
                "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
                "error": f"{e.__class__.__name__}: {msg}"}
