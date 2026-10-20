"""Reproducibility (Ch 17).

exact:    stored SQL dobara same datasource par, LLM call nahi; har query ka checksum match hona chahiye.
rederive: poora Q-TRACE+ fresh (LLM ho to naya output), findings purane run se compare.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services.query_executor.datasources import engine_for
from app.services.query_executor.executor import run_sql


def exact_replay(db: Session, run: models.ExperimentRun, engine=None) -> dict:
    if engine is None:
        exp = db.get(models.Experiment, run.experiment_id)
        _, engine = engine_for(db, exp.datasource_id if exp else None)
    rows = db.execute(
        select(models.QueryPlan, models.QueryExecution)
        .join(models.QueryExecution, models.QueryExecution.plan_id == models.QueryPlan.id)
        .where(models.QueryPlan.run_id == run.id)
    ).all()
    details = []
    for plan, ex in rows:
        try:
            result = run_sql(ex.sql, engine)
            replayed, error = result.checksum, None
        except Exception as e:  # noqa: BLE001
            replayed, error = None, f"{e.__class__.__name__}"
        details.append({"purpose": plan.purpose, "sql_hash": ex.sql_hash, "original": ex.checksum,
                        "replayed": replayed, "match": replayed == ex.checksum, "error": error})
    return {"run_id": run.id, "mode": "exact", "queries": len(details),
            "matched": sum(d["match"] for d in details),
            "match": bool(details) and all(d["match"] for d in details), "details": details,
            "warnings": definition_warnings(db, run)}


def definition_warnings(db: Session, run: models.ExperimentRun) -> list[str]:
    """Ch 17: run ke baad metric definition badli ho to replay me warning."""
    from app.services.rag.semantic_layer import load_semantic_layer

    current = load_semantic_layer(db).version
    if run.semantic_layer_version and run.semantic_layer_version != current:
        return [f"Semantic layer badal chuki hai (run: {run.semantic_layer_version}, ab: {current}) — exact replay "
                "purani stored SQL chalata hai; re-derive nayi definitions use karega."]
    return []


def compare_runs(old: dict, new: dict) -> dict:
    """Findings (key wise): status / label / share ka farq."""
    o = {f["key"]: f for f in old.get("findings", [])}
    n = {f["key"]: f for f in new.get("findings", [])}
    diff = []
    for k in sorted(set(o) | set(n)):
        a, b = o.get(k), n.get(k)
        diff.append({"key": k, "status_old": a and a["status"], "status_new": b and b["status"],
                     "share_old": a and a["share_of_delta"], "share_new": b and b["share_of_delta"],
                     "label_old": a and a["label"], "label_new": b and b["label"],
                     "same": bool(a and b and a["status"] == b["status"] and a["label"] == b["label"]
                                  and abs((a["share_of_delta"] or 0) - (b["share_of_delta"] or 0)) < 1e-6)})
    return {"status_old": old.get("status"), "status_new": new.get("status"),
            "stable": all(d["same"] for d in diff), "findings": diff}


def rederive(db: Session, exp: models.Experiment, old_run: models.ExperimentRun, llm=None) -> dict:
    from app.services.experiments.runner import optional_llm, run_pipeline

    warnings = definition_warnings(db, old_run)
    new_run = run_pipeline(db, exp, llm=llm if llm is not None else optional_llm(), replay_mode="rederive")
    return {"run_id": new_run.id, "mode": "rederive", "warnings": warnings,
            **compare_runs(old_run.summary or {}, new_run.summary or {})}
