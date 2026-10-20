"""ASK / ANALYZE: question -> LLM SQL -> firewall -> read-only execution -> answer (+ history, audit)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.core.security import CurrentUser, get_current_user
from app.db.base import new_id
from app.db.session import get_db
from app.schemas.api import HistoryOut, QueryRequest, QueryResponse
from app.services.experiments.recorder import log_audit, record_llm_call
from app.services.llm.fallback import get_llm
from app.services.llm.llm_client import LLMError
from app.services.orchestrator.ask import AskError, LLMCallLog, resolve_mode, run_ask
from app.services.query_executor.datasources import DataSourceError, engine_for
from app.services.rag.semantic_layer import load_semantic_layer

router = APIRouter(tags=["query"])

LLM_HELP = "LLM unavailable — .env me GROQ_API_KEY (ya GEMINI_API_KEY) set karo, ya Ollama chalao."


def _finish(db: Session, user: CurrentUser, hist: models.QueryHistory, calls: list[LLMCallLog], **fields) -> None:
    for k, v in fields.items():
        setattr(hist, k, v)
    hist.llm_calls = len(calls)
    db.add(hist)
    for step, prompt, resp in calls:
        record_llm_call(db, None, step, resp.model, prompt, resp.text, tokens_in=resp.tokens_in,
                        tokens_out=resp.tokens_out, latency_ms=resp.latency_ms)
    log_audit(db, user.id, "query", object_ref=hist.id, sql=hist.sql,      # commits
              blocked=hist.status == "blocked", reason=hist.error)


def execute_query(req: QueryRequest, user: CurrentUser, db: Session, llm) -> QueryResponse:
    try:
        ds_id, engine = engine_for(db, req.datasource_id)
    except DataSourceError as e:
        raise HTTPException(400, {"message": str(e), "status": "error"}) from e
    mode, warnings = resolve_mode(req.question, req.mode)
    hist = models.QueryHistory(id=new_id(), user_id=user.id, datasource_id=ds_id, question=req.question,
                               mode=mode, sql=req.sql, generated=req.sql is None, status="running")
    try:
        res = run_ask(req.question, user.role, llm, engine=engine, mode=mode, sql=req.sql,
                      layer=load_semantic_layer(db))
    except AskError as e:
        _finish(db, user, hist, e.llm_calls, status=e.status, sql=e.sql, error=e.message)
        raise HTTPException(400, {"message": e.message, "status": e.status, "sql": e.sql,
                                  "history_id": hist.id}) from e
    except LLMError as e:
        _finish(db, user, hist, [], status="llm_error", error=str(e)[:1000])
        detail = str(e).replace("all LLM providers failed: ", "")
        configured = any(p in detail for p in ("groq:", "gemini:"))
        msg = (f"LLM call fail hua: {detail[:400]}" if configured else LLM_HELP)
        raise HTTPException(503, {"message": msg, "status": "llm_error", "history_id": hist.id}) from e

    r = res.result
    _finish(db, user, hist, res.llm_calls, status="ok", sql=res.sql, row_count=r.row_count, duration_ms=r.duration_ms)
    return QueryResponse(
        history_id=hist.id, question=req.question, mode=res.mode, datasource_id=ds_id, generated=res.generated,
        attempts=res.attempts, sql=res.sql, columns=r.columns, rows=r.rows, row_count=r.row_count,
        duration_ms=r.duration_ms, checksum=r.checksum, answer=res.answer, answer_source=res.answer_source,
        warnings=warnings + res.warnings,
    )


@router.post("/query", response_model=QueryResponse)
def run_query(req: QueryRequest, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
              llm=Depends(get_llm)):
    return execute_query(req, user, db, llm)


@router.get("/query/history", response_model=list[HistoryOut])
def history(limit: int = 50, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(models.QueryHistory).where(models.QueryHistory.user_id == user.id)
                      .order_by(models.QueryHistory.created_at.desc()).limit(min(limit, 200))).all()
