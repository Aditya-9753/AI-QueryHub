"""INVESTIGATE runner: experiment -> Q-TRACE+ -> save_run. Celery worker ya background thread dono isi ko bulate hain."""
import logging
from datetime import datetime

from sqlalchemy import select

from app import models
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.experiments.recorder import record_step, save_run
from app.services.experiments.versioning import dataset_version, model_version
from app.services.orchestrator.qtrace import QTraceConfig, QTracePlus
from app.services.query_executor.datasources import engine_for
from app.services.rag.semantic_layer import load_semantic_layer

log = logging.getLogger("queryhub.runner")


def optional_llm():
    """LLM sirf tab jab key configured ho; warna pipeline fully deterministic (template narrative)."""
    s = get_settings()
    if not (s.groq_api_key or s.gemini_api_key):
        return None
    from app.services.llm.fallback import get_llm
    return get_llm()


def run_pipeline(db, exp: models.Experiment, *, llm=None, config: QTraceConfig | None = None,
                 replay_mode: str = "original") -> models.ExperimentRun:
    user = db.get(models.User, exp.user_id)
    role = user.role if user else "analyst"
    _, engine = engine_for(db, exp.datasource_id)
    layer = load_semantic_layer(db)              # metric_definitions (admin edits) + code defaults
    run = models.ExperimentRun(experiment_id=exp.id, replay_mode=replay_mode, status="running",
                               semantic_layer_version=layer.version)
    db.add(run)
    db.commit()

    def on_step(step: dict) -> None:            # live timeline: har step turant DB me
        db.add(models.ExperimentStep(run_id=run.id, type=f"{step['phase']}:{step['type']}"[:40],
                                     input_ref=step.get("ref"), from_state=step.get("from"), to_state=step.get("to"),
                                     ts=datetime.fromisoformat(step["ts"])))
        db.commit()

    report = QTracePlus(engine, layer, role=role, llm=llm, config=config, on_step=on_step).run(question=exp.question)
    return save_run(db, exp.id, report, semantic_layer_version=layer.version,
                    dataset_version=report.dataset_version or dataset_version(datetime.now(), None),
                    model_version=model_version(report.llm_calls), replay_mode=replay_mode, run=run)


def execute_experiment(experiment_id: str, llm=None, config: QTraceConfig | None = None) -> str | None:
    with SessionLocal() as db:
        exp = db.get(models.Experiment, experiment_id)
        if exp is None:
            return None
        exp.status, exp.error = "running", None
        db.commit()
        try:
            run = run_pipeline(db, exp, llm=llm if llm is not None else optional_llm(), config=config)
            exp = db.get(models.Experiment, experiment_id)
            exp.status = "completed"
            db.commit()
            return run.id
        except Exception as e:  # noqa: BLE001 — user ko error dikhana hai, worker crash nahi
            log.exception("investigation failed")
            db.rollback()
            exp = db.get(models.Experiment, experiment_id)
            exp.status, exp.error = "failed", f"{e.__class__.__name__}: {e}"[:2000]
            for r in db.scalars(select(models.ExperimentRun).where(models.ExperimentRun.experiment_id == experiment_id,
                                                                    models.ExperimentRun.status == "running")):
                r.status = "failed"
            db.commit()
            return None


def record_user_challenge(db, finding: models.Finding, ctype: str, results: list[dict], verdict: str) -> models.Challenge:
    ch = models.Challenge(finding_id=finding.id, type=ctype, origin="user", status=verdict,
                          result={"checks": results, "verdict": verdict})
    db.add(ch)
    record_step(db, finding.run_id, "Ch:user_challenge", from_state=finding.status, to_state=verdict,
                input_ref=finding.key)
    db.commit()
    return ch
