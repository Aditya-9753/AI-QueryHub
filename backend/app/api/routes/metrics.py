"""Semantic layer CRUD (v3). Yahan ki definitions pipeline (ASK + INVESTIGATE) sach me use karti hai."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.core.security import CurrentUser, require_role
from app.db.session import get_db, readonly_engine
from app.schemas.api import MetricIn, MetricOut
from app.services.experiments.recorder import log_audit
from app.services.query_executor.executor import sql_dialect
from app.services.rag.semantic_layer import DEFAULT_METRICS, SemanticLayer, with_overrides
from app.services.sql_validator.firewall import firewall_check
from app.services.sql_validator.safety_rules import UnsafeSQL

router = APIRouter(prefix="/metrics", tags=["semantic-layer"])


@router.get("", response_model=list[MetricOut])
def list_metrics(db: Session = Depends(get_db)):
    return db.scalars(select(models.MetricDefinition).order_by(models.MetricDefinition.name)).all()


@router.post("", response_model=MetricOut)
def upsert_metric(body: MetricIn, admin: CurrentUser = Depends(require_role("admin")), db: Session = Depends(get_db)):
    if body.name not in {m.name for m in DEFAULT_METRICS}:
        raise HTTPException(422, "naya metric code me (rag/semantic_layer.py) define karo; yahan sirf definition/formula edit")
    # Formula ko render karke 4-layer firewall se check karo — galat / unsafe formula save hi nahi hota
    try:
        layer = SemanticLayer(with_overrides(DEFAULT_METRICS, [models.MetricDefinition(**body.model_dump(), version=1)]))
        firewall_check(layer.render(body.name, start="2026-01-01", end="2026-02-01"), role="admin",
                       dialect=sql_dialect(readonly_engine))
    except (UnsafeSQL, ValueError) as e:
        raise HTTPException(400, f"invalid formula: {e}") from e
    m = db.scalars(select(models.MetricDefinition).where(models.MetricDefinition.name == body.name)).first()
    if m is None:
        m = models.MetricDefinition(**body.model_dump(), version=1)
        db.add(m)
    else:
        if (m.definition, m.formula_sql, m.grain) == (body.definition, body.formula_sql, body.grain):
            raise HTTPException(409, "no change")
        m.definition, m.formula_sql, m.grain = body.definition, body.formula_sql, body.grain
        m.version += 1                     # replay me "metric definition badli" warning ke liye
    db.commit()
    log_audit(db, admin.id, "metric_update", object_ref=f"{m.name} v{m.version}")
    return m
