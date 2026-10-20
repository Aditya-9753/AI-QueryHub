"""Eval Dashboard data (Ch 18): latest benchmark / ablation / calibration / golden results."""
import json
from pathlib import Path

from fastapi import APIRouter, Depends

from app.core.security import get_current_user

router = APIRouter(prefix="/eval", tags=["eval"], dependencies=[Depends(get_current_user)])
RESULTS = Path(__file__).resolve().parents[3] / "tests" / "eval_suite" / "results"


def _load(name: str):
    p = RESULTS / f"{name}_latest.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


@router.get("/latest")
def latest():
    return {k: _load(k) for k in ("benchmark", "ablation", "calibration", "golden", "safety")}
