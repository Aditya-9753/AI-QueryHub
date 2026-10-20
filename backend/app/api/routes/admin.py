"""Admin control center: users (create / role / status), org-wide usage overview, query log, audit, system config.
Sab endpoints sirf admin ke liye (router dependency)."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.core.config import get_settings
from app.core.security import DEV_USER_ID, CurrentUser, hash_password, require_role
from app.db.session import get_db
from app.schemas.api import AuditOut, Role, SignupIn, UserOut, UserUpdate
from app.services.experiments.recorder import log_audit

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_role("admin"))])


class UserCreate(SignupIn):
    role: Role = "viewer"


def _since(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def _day(ts: datetime) -> str:
    return ts.date().isoformat()


@router.get("/audit", response_model=list[AuditOut])
def audit(limit: int = 100, blocked_only: bool = False, db: Session = Depends(get_db)):
    q = select(models.AuditLog).order_by(models.AuditLog.ts.desc()).limit(min(limit, 500))
    if blocked_only:
        q = q.where(models.AuditLog.blocked.is_(True))
    return db.scalars(q).all()


@router.get("/users", response_model=list[UserOut])
def users(db: Session = Depends(get_db)):
    return db.scalars(select(models.User).where(models.User.id != DEV_USER_ID)
                      .order_by(models.User.created_at)).all()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, admin: CurrentUser = Depends(require_role("admin")), db: Session = Depends(get_db)):
    """Admin team member ka account banata hai (default viewer) — public signup ki zaroorat nahi."""
    email = body.email.strip().lower()
    if db.scalar(select(models.User).where(models.User.email == email)):
        raise HTTPException(409, "email already registered")
    user = models.User(email=email, name=body.name, role=body.role, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    log_audit(db, admin.id, "user_create", object_ref=user.id, reason=f"role={user.role}")
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: str, body: UserUpdate, admin: CurrentUser = Depends(require_role("admin")),
                db: Session = Depends(get_db)):
    if user_id == admin.id:
        raise HTTPException(409, "apna khud ka role / status nahi badal sakte")
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(404, "user not found")
    changes = body.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(user, k, v)
    db.commit()
    log_audit(db, admin.id, "user_update", object_ref=user_id, reason=str(changes))
    return user


@router.get("/overview")
def overview(days: int = 14, db: Session = Depends(get_db)):
    """Org-wide usage (sirf admin dekhta hai): users by role, query volume / outcome per day + per role,
    top users, LLM usage per model, investigations by status, firewall blocks."""
    days = max(1, min(days, 90))
    since = _since(days)
    user_rows = db.execute(select(models.User.id, models.User.email, models.User.name, models.User.role,
                                  models.User.is_active).where(models.User.id != DEV_USER_ID)).all()
    who = {u.id: u for u in user_rows}

    queries = db.execute(select(models.QueryHistory.user_id, models.QueryHistory.status, models.QueryHistory.created_at,
                                models.QueryHistory.duration_ms, models.QueryHistory.generated)
                         .where(models.QueryHistory.created_at >= since)).all()
    daily: dict[str, Counter] = {(since + timedelta(days=i + 1)).date().isoformat(): Counter() for i in range(days)}
    per_role: dict[str, Counter] = defaultdict(Counter)
    per_user: dict[str, Counter] = defaultdict(Counter)
    for q in queries:
        daily.setdefault(_day(q.created_at), Counter())[q.status] += 1
        role = who[q.user_id].role if q.user_id in who else "dev"
        per_role[role][q.status] += 1
        per_user[q.user_id][q.status] += 1
    status = Counter(q.status for q in queries)
    durations = [q.duration_ms for q in queries if q.duration_ms is not None]

    llm = db.execute(select(models.LLMCall.model, func.count(), func.sum(models.LLMCall.tokens_in),
                            func.sum(models.LLMCall.tokens_out), func.avg(models.LLMCall.latency_ms))
                     .where(models.LLMCall.created_at >= since).group_by(models.LLMCall.model)).all()
    exp_status = dict(db.execute(select(models.Experiment.status, func.count()).group_by(models.Experiment.status)).all())
    blocked_audit = db.scalar(select(func.count()).select_from(models.AuditLog)
                              .where(models.AuditLog.blocked.is_(True), models.AuditLog.ts >= since)) or 0

    top = sorted(per_user.items(), key=lambda kv: -sum(kv[1].values()))[:8]
    return {
        "days": days,
        "users": {"total": len(user_rows), "active": sum(1 for u in user_rows if u.is_active),
                  "by_role": dict(Counter(u.role for u in user_rows))},
        "queries": {"total": len(queries), "ok": status.get("ok", 0), "blocked": status.get("blocked", 0),
                    "errors": status.get("error", 0) + status.get("llm_error", 0),
                    "manual_sql": sum(1 for q in queries if not q.generated),
                    "avg_ms": round(sum(durations) / len(durations), 1) if durations else None,
                    "daily": [{"date": d, "ok": c.get("ok", 0), "blocked": c.get("blocked", 0),
                               "errors": c.get("error", 0) + c.get("llm_error", 0)} for d, c in sorted(daily.items())],
                    "by_role": {r: {"total": sum(c.values()), "ok": c.get("ok", 0), "blocked": c.get("blocked", 0)}
                                for r, c in per_role.items()}},
        "top_users": [{"id": uid, "email": who[uid].email if uid in who else "dev@local",
                       "name": who[uid].name if uid in who else "dev", "role": who[uid].role if uid in who else "dev",
                       "total": sum(c.values()), "ok": c.get("ok", 0), "blocked": c.get("blocked", 0)} for uid, c in top],
        "llm": [{"model": m, "calls": n, "tokens_in": int(ti or 0), "tokens_out": int(to or 0),
                 "avg_latency_ms": round(lat, 1) if lat is not None else None} for m, n, ti, to, lat in llm],
        "experiments": exp_status,
        "firewall_blocks": blocked_audit,
    }


@router.get("/queries")
def query_log(limit: int = 100, status: str | None = None, db: Session = Depends(get_db)):
    """Poore org ki query history (har user ka sawaal, SQL, outcome) — monitoring + misuse detection."""
    q = (select(models.QueryHistory, models.User.email, models.User.name, models.User.role)
         .join(models.User, models.User.id == models.QueryHistory.user_id, isouter=True)
         .order_by(models.QueryHistory.created_at.desc()).limit(min(limit, 500)))
    if status:
        q = q.where(models.QueryHistory.status == status)
    return [{"id": h.id, "question": h.question, "mode": h.mode, "status": h.status, "error": h.error, "sql": h.sql,
             "generated": h.generated, "row_count": h.row_count, "duration_ms": h.duration_ms, "llm_calls": h.llm_calls,
             "created_at": h.created_at, "user": {"id": h.user_id, "email": email, "name": name, "role": role}}
            for h, email, name, role in db.execute(q).all()]


@router.get("/system")
def system():
    """Effective config — values only jo secret nahi hain (keys sirf configured true/false)."""
    s = get_settings()
    return {
        "environment": s.environment,
        "auth": {"supabase": bool(s.supabase_url or s.supabase_jwt_secret), "jwt_default_secret": s.jwt_secret == "change-me",
                 "token_ttl_min": s.jwt_expire_minutes},
        "llm": {"groq": {"configured": bool(s.groq_api_key), "model": s.groq_model},
                "gemini": {"configured": bool(s.gemini_api_key), "model": s.gemini_model},
                "ollama": {"url": s.ollama_url, "model": s.ollama_model}, "temperature": s.llm_temperature,
                "answer_sentence": s.llm_answer, "sql_repair_retries": s.ask_max_retries},
        "firewall": {"max_rows": s.max_rows, "statement_timeout_ms": s.statement_timeout_ms,
                     "max_plan_cost": s.max_plan_cost, "datasource_env_prefix": s.datasource_env_prefix},
        "qtrace": {"max_queries": s.qtrace_max_queries, "max_llm_calls": s.qtrace_max_llm_calls,
                   "explained_target": s.qtrace_explained_target, "fdr_q": s.qtrace_fdr_q},
        "rag": {"schema_rag": s.schema_rag},
        "monitoring": {"sentry": bool(s.sentry_dsn)},
        "database": {"app": s.database_url.split(":", 1)[0], "readonly": s.readonly_database_url.split(":", 1)[0]},
    }
