from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.db.session import get_db
from app.schemas.qtrace import Hypothesis, HypStatus, QuestionSpec
from app.services.hypothesis_engine.generator import generate_hypotheses

router = APIRouter(prefix="/hypotheses", tags=["hypotheses"])


@router.post("/generate", response_model=list[Hypothesis])
def generate(spec: QuestionSpec):
    """Preview: deterministic hypotheses (metric tree + templates). LLM extras Phase 4 me."""
    return generate_hypotheses(spec)


@router.post("/{hypothesis_id}/approve")
def approve(hypothesis_id: str, db: Session = Depends(get_db)):
    h = db.get(models.Hypothesis, hypothesis_id)
    if h is None:
        raise HTTPException(404, "hypothesis not found")
    if h.status != HypStatus.UNGROUNDED.value:
        raise HTTPException(409, f"sirf ungrounded hypothesis approve hoti hai (current: {h.status})")
    db.add(models.ExperimentStep(run_id=h.run_id, type="hypothesis_approved", input_ref=h.id,
                                 from_state=h.status, to_state=HypStatus.GROUNDED.value))
    h.status = HypStatus.GROUNDED.value
    db.commit()
    return {"id": h.id, "status": h.status}
