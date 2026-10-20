"""Challenge This Finding (Ch 6.3, 8.6): battery ka koi check ya custom (LLM counter-hypotheses).
Original finding kabhi overwrite nahi hoti — challenge alag row + timeline step."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.core.security import CurrentUser, get_current_user
from app.db.session import get_db
from app.schemas.api import ChallengeCreate, ChallengeOut
from app.schemas.qtrace import SUPPORTED_LIKE, Hypothesis
from app.services.challenge.battery import BATTERY_TYPES, run_challenge_battery
from app.services.challenge.generator import counter_hypotheses
from app.services.challenge.resolver import resolve
from app.services.experiments.runner import optional_llm, record_user_challenge
from app.services.hypothesis_engine.mapper import ground
from app.services.orchestrator.qtrace import QTracePlus, _jsonable
from app.services.query_executor.datasources import engine_for
from app.services.rag.semantic_layer import load_semantic_layer

router = APIRouter(tags=["challenges"])


def _pipeline_for(db: Session, finding: models.Finding, user: CurrentUser):
    run = db.get(models.ExperimentRun, finding.run_id)
    exp = db.get(models.Experiment, run.experiment_id)
    if exp.user_id != user.id and user.role != "admin":
        raise HTTPException(404, "finding not found")
    _, engine = engine_for(db, exp.datasource_id)
    pipe = QTracePlus(engine, load_semantic_layer(db), role=user.role)
    report = pipe.run(question=exp.question)       # deterministic: same data => same findings
    return pipe, report


@router.post("/challenges", response_model=ChallengeOut)
def create_challenge(body: ChallengeCreate, user: CurrentUser = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    finding = db.get(models.Finding, body.finding_id)
    if finding is None:
        raise HTTPException(404, "finding not found")
    pipe, report = _pipeline_for(db, finding, user)
    f = report.finding(finding.key)
    if f is None:
        raise HTTPException(409, "finding re-derive me nahi mili (data badal gaya?) — replay karke dekho")

    if body.type in BATTERY_TYPES or body.type == "battery":
        ctx = pipe._battery_ctx(f)
        results = [r for r in run_challenge_battery(ctx) if body.type == "battery" or r.type == body.type]
        if not results:
            raise HTTPException(422, f"'{body.type}' check is finding par lagu nahi hota")
        verdict = resolve(results)
        return record_user_challenge(db, finding, body.type, _jsonable([r.to_dict() for r in results]), verdict)

    if body.type != "custom" or not body.description:
        raise HTTPException(422, f"type: {', '.join(BATTERY_TYPES)}, battery, ya custom (+ description)")
    llm = optional_llm()
    if llm is None:
        raise HTTPException(503, "custom challenge ke liye LLM chahiye (.env me GROQ_API_KEY)")
    results = []
    for h in counter_hypotheses(f.statement, body.description, report.spec.metric, list(pipe.metric.dimensions), llm):
        h = ground(h, pipe.layer)
        if h.status.value == "ungrounded":
            results.append({"statement": h.statement, "status": "ungrounded"})
            continue
        cf = pipe._t_llm(h)
        results.append({"statement": cf.statement, "status": cf.status.value, "share": cf.share_of_delta,
                        "ci": cf.ci, "p": cf.p_value})
    stronger = [r for r in results if r["status"] in {s.value for s in SUPPORTED_LIKE}
                and abs(r.get("share", 0)) > abs(f.share_of_delta)]
    weaker = [r for r in results if r["status"] in {s.value for s in SUPPORTED_LIKE}]
    verdict = "overturned" if stronger else "revised" if weaker else "upheld"
    return record_user_challenge(db, finding, "custom", _jsonable(results), verdict)


@router.get("/findings/{finding_id}/challenges", response_model=list[ChallengeOut])
def list_challenges(finding_id: str, db: Session = Depends(get_db)):
    return db.scalars(select(models.Challenge).where(models.Challenge.finding_id == finding_id)).all()


@router.get("/experiments/{experiment_id}/findings")
def findings_of(experiment_id: str, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    exp = db.get(models.Experiment, experiment_id)
    if exp is None or (exp.user_id != user.id and user.role != "admin"):
        raise HTTPException(404, "experiment not found")
    run = db.scalars(select(models.ExperimentRun).where(models.ExperimentRun.experiment_id == experiment_id)
                     .order_by(models.ExperimentRun.created_at.desc())).first()
    if run is None:
        return []
    out = []
    for f in db.scalars(select(models.Finding).where(models.Finding.run_id == run.id)).all():
        chs = db.scalars(select(models.Challenge).where(models.Challenge.finding_id == f.id)).all()
        out.append({"id": f.id, "key": f.key, "statement": f.statement, "status": f.status, "label": f.label,
                    "score": f.evidence_score, "share": f.share_of_delta,
                    "challenges": [{"id": c.id, "type": c.type, "origin": c.origin, "status": c.status,
                                    "result": c.result} for c in chs]})
    return out


_ = Hypothesis  # re-export for type checkers
