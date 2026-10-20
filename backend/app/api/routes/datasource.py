"""Database connection screen ka backend. Connection URL kabhi API/DB me nahi — sirf env var ka naam."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.core.security import CurrentUser, get_current_user, require_role
from app.db.session import get_db, readonly_engine
from app.schemas.api import ConnectionTestOut, DataSourceIn, DataSourceOut
from app.services.experiments.recorder import log_audit
from app.services.query_executor.datasources import (
    DEFAULT_ID,
    DEFAULT_REF,
    DataSourceError,
    engine_for,
    ref_allowed,
    test_connection,
)
from app.services.query_executor.executor import sql_dialect

router = APIRouter(prefix="/datasources", tags=["datasources"])


def _default() -> DataSourceOut:
    return DataSourceOut(id=DEFAULT_ID, name="Default (READONLY_DATABASE_URL)", kind=sql_dialect(readonly_engine),
                         conn_secret_ref=DEFAULT_REF, readonly_role="queryhub_ro", owner_id="system", is_default=True)


@router.get("", response_model=list[DataSourceOut])
def list_datasources(_: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(models.DataSource).order_by(models.DataSource.created_at)).all()
    return [_default(), *[DataSourceOut.model_validate(r) for r in rows]]


@router.post("", response_model=DataSourceOut, status_code=201)
def create_datasource(body: DataSourceIn, user: CurrentUser = Depends(require_role("admin")),
                      db: Session = Depends(get_db)):
    if not ref_allowed(body.conn_secret_ref) or body.conn_secret_ref == DEFAULT_REF:
        raise HTTPException(400, "conn_secret_ref 'DS_' se shuru hona chahiye (e.g. DS_SALES_URL)")
    ds = models.DataSource(owner_id=user.id, **body.model_dump())
    db.add(ds)
    db.commit()
    log_audit(db, user.id, "datasource_create", object_ref=ds.id)
    return ds


@router.post("/{datasource_id}/test", response_model=ConnectionTestOut)
def test_datasource(datasource_id: str, _: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        _, engine = engine_for(db, datasource_id)
    except DataSourceError as e:
        return ConnectionTestOut(ok=False, dialect="unknown", tables=0, duration_ms=0, error=str(e))
    return test_connection(engine)


@router.delete("/{datasource_id}", status_code=204)
def delete_datasource(datasource_id: str, user: CurrentUser = Depends(require_role("admin")),
                      db: Session = Depends(get_db)):
    ds = db.get(models.DataSource, datasource_id)
    if ds is None:
        raise HTTPException(404, "datasource not found")
    db.delete(ds)
    db.commit()
    log_audit(db, user.id, "datasource_delete", object_ref=datasource_id)
