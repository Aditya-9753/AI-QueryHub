"""INVESTIGATE API (Ch 14): create, run (Celery / thread / sync), status, timeline, hypotheses,
decomposition (waterfall), evidence graph, replay (exact / rederive), export (JSON / PDF)."""
import threading

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.core.security import ANALYST_ROLES, CurrentUser, get_current_user, require_role
from app.db.session import get_db
from app.schemas.api import ExperimentOut, ReplayRequest
from app.services.experiments import replay
from app.services.experiments.export import to_pdf
from app.services.experiments.runner import execute_experiment
from app.services.query_executor.datasources import DataSourceError, engine_for

router = APIRouter(prefix="/experiments", tags=["experiments"])


class ExperimentIn(BaseModel):
    question: str
    mode: str = "INVESTIGATE"
    datasource_id: str | None = None


def can_read(exp: models.Experiment, user: CurrentUser) -> bool:
    """Owner / admin sab dekhte hain; completed runs team library hain — har role padh sakta hai."""
    return exp.user_id == user.id or user.role == "admin" or exp.status == "completed"


def _get(db: Session, experiment_id: str, user: CurrentUser, write: bool = False) -> models.Experiment:
    exp = db.get(models.Experiment, experiment_id)
    if exp is None or not can_read(exp, user):
        raise HTTPException(404, "experiment not found")
    if write and exp.user_id != user.id and user.role != "admin":
        raise HTTPException(403, "sirf owner ya admin is experiment ko chala / badal sakta hai")
    return exp


def _latest_run(db: Session, experiment_id: str) -> models.ExperimentRun | None:
    return db.scalars(select(models.ExperimentRun).where(models.ExperimentRun.experiment_id == experiment_id)
                      .order_by(models.ExperimentRun.created_at.desc())).first()


@router.post("", response_model=ExperimentOut)
def create_experiment(body: ExperimentIn, user: CurrentUser = Depends(require_role(*ANALYST_ROLES)),
                      db: Session = Depends(get_db)):
    try:
        engine_for(db, body.datasource_id)
    except DataSourceError as e:
        raise HTTPException(400, str(e)) from e
    exp = models.Experiment(user_id=user.id, question=body.question, mode=body.mode, datasource_id=body.datasource_id)
    db.add(exp)
    db.commit()
    return exp


@router.get("", response_model=list[ExperimentOut])
def list_experiments(scope: str = "mine", user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """scope=mine: apne runs · scope=team: sabke completed runs (viewer ke liye hamesha team)."""
    q = (select(models.Experiment, models.User.name, models.User.email)
         .join(models.User, models.User.id == models.Experiment.user_id, isouter=True))
    if scope == "team" or user.role not in ANALYST_ROLES:
        q = q.where(models.Experiment.status == "completed")
    else:
        q = q.where(models.Experiment.user_id == user.id)
    rows = db.execute(q.order_by(models.Experiment.created_at.desc()).limit(50)).all()
    return [ExperimentOut(id=e.id, question=e.question, mode=e.mode, status=e.status, created_at=e.created_at,
                          user_id=e.user_id, owner=name or (email or "").split("@")[0] or None)
            for e, name, email in rows]


@router.post("/{experiment_id}/run", status_code=202)
def run_experiment(experiment_id: str, sync: bool = False, user: CurrentUser = Depends(require_role(*ANALYST_ROLES)),
                   db: Session = Depends(get_db)):
    """sync=true: request me hi chalao (dev/tests). Warna Celery (Redis up ho) ya background thread."""
    exp = _get(db, experiment_id, user, write=True)
    if exp.status in ("queued", "running"):
        raise HTTPException(409, f"already {exp.status}")
    if sync:
        execute_experiment(exp.id)
        db.refresh(exp)
        return {"id": exp.id, "status": exp.status, "runner": "sync", "error": exp.error}
    exp.status = "queued"
    db.commit()
    from app.worker import broker_available, run_investigation

    if broker_available():
        run_investigation.apply_async(args=[exp.id], retry=False)
        runner = "celery"
    else:
        threading.Thread(target=execute_experiment, args=(exp.id,), daemon=True).start()
        runner = "thread"
    return {"id": exp.id, "status": "queued", "runner": runner}


@router.get("/{experiment_id}")
def get_experiment(experiment_id: str, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    exp = _get(db, experiment_id, user)
    run = _latest_run(db, experiment_id)
    s = (run.summary or {}) if run else {}
    gate = (s.get("verify") or {}).get("gate") or {}
    band = gate.get("band") or {}
    findings = s.get("findings", [])
    # Ch 14.1 response shape (compact) + poora `report` UI ke liye
    compact = {
        "verify": {"data_health": "pass" if ((s.get("verify") or {}).get("health") or {}).get("ok") else
                   ("fail" if s else None), "z_score": gate.get("z"),
                   "band": [band.get("low"), band.get("high")] if band else None, "method": gate.get("method")},
        "spec": s.get("spec"), "stop_reason": s.get("stop_reason"), "residual_share": s.get("residual_share"),
        "findings": [{"hypothesis_id": f["key"], "statement": f["statement"], "share_of_delta": f["share_of_delta"],
                      "score": f["score"], "label": f["label"],
                      "challenges": [{"type": c["type"], "result": "pass" if c["passed"] else "fail"}
                                     for c in f.get("challenges", [])]}
                     for f in findings if f["status"] in ("supported", "upheld", "revised")],
        "rejected": [f["key"] for f in findings if f["status"] in ("rejected", "overturned")],
        "claims": s.get("claims", []),
    }
    return {"id": exp.id, "question": exp.question, "mode": exp.mode, "status": exp.status, "error": exp.error,
            **compact,
            "datasource_id": exp.datasource_id, "created_at": exp.created_at, "user_id": exp.user_id,
            "run": None if run is None else {
                "id": run.id, "created_at": run.created_at, "replay_mode": run.replay_mode,
                "dataset_version": run.dataset_version, "model_version": run.model_version,
                "semantic_layer_version": run.semantic_layer_version, "duration_ms": run.duration_ms},
            "report": run.summary if run else None}


@router.get("/{experiment_id}/timeline")
def timeline(experiment_id: str, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _get(db, experiment_id, user)
    run = _latest_run(db, experiment_id)
    if run is None:
        return []
    steps = db.scalars(select(models.ExperimentStep).where(models.ExperimentStep.run_id == run.id)
                       .order_by(models.ExperimentStep.ts)).all()
    return [{"type": s.type, "ref": s.input_ref, "from": s.from_state, "to": s.to_state, "ts": s.ts} for s in steps]


@router.get("/{experiment_id}/hypotheses")
def hypotheses(experiment_id: str, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _get(db, experiment_id, user)
    run = _latest_run(db, experiment_id)
    if run is None:
        return []
    rows = db.scalars(select(models.Hypothesis).where(models.Hypothesis.run_id == run.id)).all()
    by_id = {h.id: h.key for h in rows}
    return [{"id": h.key, "db_id": h.id, "statement": h.statement, "source": h.source, "status": h.status,
             "priority": h.priority, "prior": h.prior, "parent_id": by_id.get(h.parent_id), "depth": h.depth,
             "test_type": h.test_type, "metric": h.metric, "rejection_reason": h.rejection_reason} for h in rows]


@router.get("/{experiment_id}/decomposition")
def decomposition(experiment_id: str, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Waterfall data: base total -> frontier factors (children parent ki jagah) -> current total."""
    _get(db, experiment_id, user)
    run = _latest_run(db, experiment_id)
    s = (run.summary or {}) if run else {}
    if s.get("status") != "completed":
        return {"status": s.get("status"), "steps": []}
    rows, findings = s["decomposition"], {f["key"]: f for f in s["findings"]}
    steps = []
    for top in [r for r in rows if r["depth"] == 0]:
        kids = [r for r in rows if r.get("parent") == top["hypothesis"]]
        for r in (kids if kids and all(k["hypothesis"] in findings for k in kids) else [top]):
            f = findings.get(r["hypothesis"])
            steps.append({"key": r["hypothesis"], "factor": r["factor"], "amount": r["amount"], "share": r["share"],
                          "status": f["status"] if f else "not_tested", "label": f.get("label") if f else None,
                          "dimension": r.get("dimension")})
    core = s["core"]
    return {"status": "completed", "unit": core["unit"], "base": core["T0"], "current": core["T1"],
            "period_base": s["spec"]["period_base"], "period_current": s["spec"]["period_current"], "steps": steps,
            "residual": core["T1"] - core["T0"] - sum(st["amount"] for st in steps)}


@router.get("/{experiment_id}/evidence")
def evidence(experiment_id: str, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    _get(db, experiment_id, user)
    run = _latest_run(db, experiment_id)
    s = (run.summary or {}) if run else {}
    return {"graph": s.get("graph", {"nodes": [], "edges": []}), "claims": s.get("claims", []),
            "queries": s.get("queries", []), "grounding": s.get("grounding", {})}


@router.post("/{experiment_id}/replay")
def replay_experiment(experiment_id: str, body: ReplayRequest,
                      user: CurrentUser = Depends(require_role(*ANALYST_ROLES)), db: Session = Depends(get_db)):
    # exact replay = verification (koi bhi analyst kar sakta hai); re-derive naya run likhta hai -> owner/admin
    exp = _get(db, experiment_id, user, write=body.mode != "exact")
    run = db.scalars(select(models.ExperimentRun).where(models.ExperimentRun.experiment_id == experiment_id,
                                                         models.ExperimentRun.replay_mode == "original")
                     .order_by(models.ExperimentRun.created_at.desc())).first()
    if run is None:
        raise HTTPException(409, "experiment abhi tak run nahi hua")
    if body.mode == "exact":
        return replay.exact_replay(db, run)
    return replay.rederive(db, exp, run)


@router.get("/{experiment_id}/export")
def export(experiment_id: str, format: str = "json", user: CurrentUser = Depends(get_current_user),
           db: Session = Depends(get_db)):
    exp = _get(db, experiment_id, user)
    run = _latest_run(db, experiment_id)
    data = {"id": exp.id, "question": exp.question, "status": exp.status,
            "run": {"id": run.id, "dataset_version": run.dataset_version, "model_version": run.model_version,
                    "semantic_layer_version": run.semantic_layer_version} if run else None,
            "report": run.summary if run else None, "timeline": timeline(experiment_id, user, db)}
    if format == "pdf":
        if run is None:
            raise HTTPException(409, "no run to export")
        try:
            pdf = to_pdf(data, run.summary or {})
        except ImportError as e:
            raise HTTPException(501, "PDF ke liye `pip install fpdf2`") from e
        return Response(pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="experiment-{exp.id[:8]}.pdf"'})
    return data
