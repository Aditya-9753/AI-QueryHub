"""Schema viewer — role-filtered (app tables aur blocked columns ka 'sensitive' flag)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, get_current_user
from app.db.session import get_db
from app.schemas.api import SchemaColumnOut, SchemaOut, SchemaTableOut
from app.services.query_executor.datasources import DataSourceError, engine_for
from app.services.query_executor.executor import sql_dialect
from app.services.rag.schema_context import schema_snapshot

router = APIRouter(prefix="/schema", tags=["schema"])


@router.get("", response_model=SchemaOut)
def get_schema(datasource_id: str | None = None, refresh: bool = False,
               user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        ds_id, engine = engine_for(db, datasource_id)
        tables = schema_snapshot(engine, user.role, refresh=refresh)
    except DataSourceError as e:
        raise HTTPException(400, str(e)) from e
    except SQLAlchemyError as e:
        raise HTTPException(502, f"schema read failed: {e.__class__.__name__}") from e
    return SchemaOut(
        datasource_id=ds_id, dialect=sql_dialect(engine),
        tables=[SchemaTableOut(name=t.name, columns=[SchemaColumnOut(**c.__dict__) for c in t.columns])
                for t in tables],
    )
