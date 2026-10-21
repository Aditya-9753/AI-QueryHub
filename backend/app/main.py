"""FastAPI entrypoint.  uvicorn app.main:app --reload"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text

from app import models
from app.api.router import api_router
from app.core.config import get_settings
from app.core.security import DEV_USER_ID
from app.db.session import SessionLocal, engine
from app.services.rag.semantic_layer import SemanticLayer

log = logging.getLogger("queryhub")
settings = get_settings()
ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(ALEMBIC_INI)), "head")


def harden_postgres() -> None:
    """Supabase `public` schema ki tables PostgREST (anon key) se bhi pahunchti hain. RLS on + koi policy nahi =
    us API se kuch nahi dikhta; backend table owner ke roop me connect hota hai, isliye uspe asar nahi. Idempotent."""
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        tables = conn.execute(text(
            "select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace "
            "where n.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity")).scalars().all()
        for t in tables:
            conn.execute(text(f'alter table public."{t}" enable row level security'))
    if tables:
        log.info("RLS enabled on %d public tables", len(tables))


def bootstrap() -> None:
    """Default semantic-layer metrics (+ AUTH_DISABLED me dev user) seed karo (idempotent)."""
    with SessionLocal() as db:
        if settings.auth_disabled and db.get(models.User, DEV_USER_ID) is None:
            db.add(models.User(id=DEV_USER_ID, email="dev@local", role="admin"))
        existing = set(db.scalars(select(models.MetricDefinition.name)).all())
        for m in SemanticLayer().metrics():
            if m.name not in existing:
                db.add(models.MetricDefinition(name=m.name, definition=m.definition,
                                               formula_sql=m.expression, grain=m.grain, version=m.version))
        db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.jwt_secret == "change-me" and settings.environment != "dev":
        log.warning("JWT_SECRET default hai — production se pehle badlo!")
    if settings.auto_migrate:
        try:
            run_migrations()
        except Exception as e:
            log.error("alembic upgrade failed: %s", e)
    try:
        harden_postgres()
    except Exception as e:
        log.warning("RLS hardening skipped: %s", e)
    try:
        bootstrap()
    except Exception as e:
        log.warning("bootstrap skipped: %s", e)
    yield


if settings.sentry_dsn:      # Ch 2.5 monitoring (optional)
    import sentry_sdk

    sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment, traces_sample_rate=0.0,
                    send_default_pii=False)

app = FastAPI(title=settings.app_name, version="0.3.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "app": settings.app_name, "env": settings.environment}
