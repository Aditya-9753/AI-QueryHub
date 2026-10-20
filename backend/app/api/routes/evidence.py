from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db.session import get_db

router = APIRouter(tags=["evidence"])


@router.get("/findings/{finding_id}/evidence")
def finding_evidence(finding_id: str, db: Session = Depends(get_db)):
    finding = db.get(models.Finding, finding_id)
    if finding is None:
        raise HTTPException(404, "finding not found")
    nodes = db.scalars(select(models.EvidenceNode).where(models.EvidenceNode.run_id == finding.run_id)).all()
    edges = db.scalars(select(models.EvidenceEdge).where(models.EvidenceEdge.run_id == finding.run_id)).all()
    claims = db.scalars(select(models.Claim).where(models.Claim.finding_id == finding_id)).all()
    return {
        "nodes": [{"id": n.id, "type": n.type, "source_ref": n.source_ref, "value": n.value} for n in nodes],
        "edges": [{"from": e.from_node, "to": e.to_node, "relation": e.relation} for e in edges],
        "claims": [{"sentence": c.sentence, "claim_type": c.claim_type,
                    "evidence_node_ids": c.evidence_node_ids} for c in claims],
    }
