from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.api.routes.query import execute_query
from app.core.security import CurrentUser, get_current_user
from app.db.session import get_db
from app.schemas.api import QueryRequest, QueryResponse, SavedQueryIn, SavedQueryOut
from app.services.llm.fallback import get_llm
from app.services.query_executor.datasources import DataSourceError, engine_for
from app.services.query_executor.executor import sql_dialect
from app.services.sql_validator.firewall import firewall_check
from app.services.sql_validator.safety_rules import UnsafeSQL

router = APIRouter(prefix="/saved-queries", tags=["saved-queries"])


def _own(db: Session, user: CurrentUser, sq_id: str) -> models.SavedQuery:
    sq = db.get(models.SavedQuery, sq_id)
    if sq is None or sq.user_id != user.id:
        raise HTTPException(404, "saved query not found")
    return sq


@router.get("", response_model=list[SavedQueryOut])
def list_saved(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(models.SavedQuery).where(models.SavedQuery.user_id == user.id)
                      .order_by(models.SavedQuery.created_at.desc())).all()


@router.post("", response_model=SavedQueryOut, status_code=201)
def save(body: SavedQueryIn, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        _, engine = engine_for(db, body.datasource_id)
        firewall_check(body.sql, role=user.role, dialect=sql_dialect(engine))   # unsafe SQL save hi nahi hota
    except (DataSourceError, UnsafeSQL) as e:
        raise HTTPException(400, f"cannot save: {e}") from e
    sq = models.SavedQuery(user_id=user.id, **body.model_dump())
    db.add(sq)
    db.commit()
    return sq


@router.post("/{sq_id}/run", response_model=QueryResponse)
def run_saved(sq_id: str, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
              llm=Depends(get_llm)):
    sq = _own(db, user, sq_id)
    req = QueryRequest(question=sq.question, mode=sq.mode if sq.mode in ("ASK", "ANALYZE") else None,
                       sql=sq.sql, datasource_id=sq.datasource_id)
    return execute_query(req, user, db, llm, allow_manual=True)


@router.delete("/{sq_id}", status_code=204)
def delete(sq_id: str, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(_own(db, user, sq_id))
    db.commit()
