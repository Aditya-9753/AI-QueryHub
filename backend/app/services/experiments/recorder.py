"""Experiment record (Rec): run + hypotheses + plans/executions + findings + challenges + decompositions +
baselines + health checks + evidence graph + claims + llm_calls — sab ek transaction me."""
import hashlib
from datetime import datetime

from sqlalchemy.orm import Session

from app import models
from app.services.query_executor.executor import ExecutionResult


def log_audit(db: Session, user_id: str | None, action: str, object_ref: str | None = None,
              sql: str | None = None, blocked: bool = False, reason: str | None = None) -> None:
    db.add(models.AuditLog(user_id=user_id, action=action, object_ref=object_ref,
                           sql_hash=hashlib.sha256(sql.encode()).hexdigest() if sql else None,
                           blocked=blocked, reason=reason))
    db.commit()


def record_step(db: Session, run_id: str, type: str, from_state: str | None = None, to_state: str | None = None,
                input_ref: str | None = None, output_ref: str | None = None) -> None:
    db.add(models.ExperimentStep(run_id=run_id, type=type, from_state=from_state, to_state=to_state,
                                 input_ref=input_ref, output_ref=output_ref))


def record_execution(db: Session, plan_id: str | None, result: ExecutionResult) -> models.QueryExecution:
    row = models.QueryExecution(plan_id=plan_id, sql=result.sql, sql_hash=result.sql_hash,
                                duration_ms=result.duration_ms, row_count=result.row_count,
                                checksum=result.checksum)
    db.add(row)
    return row


def record_llm_call(db: Session, run_id: str | None, step: str, model: str, prompt: str, response: str,
                    temperature: float = 0.0, tokens_in: int | None = None, tokens_out: int | None = None,
                    latency_ms: float | None = None) -> None:
    db.add(models.LLMCall(run_id=run_id, step=step, model=model,
                          prompt_hash=hashlib.sha256(prompt.encode()).hexdigest(), prompt=prompt,
                          response=response, temperature=temperature, tokens_in=tokens_in,
                          tokens_out=tokens_out, latency_ms=latency_ms))


def _ts(s: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(s) if s else None
    except ValueError:
        return None


def save_run(db: Session, experiment_id: str, report, *, semantic_layer_version: str | None = None,
             dataset_version: str | None = None, model_version: str | None = None,
             replay_mode: str = "original", run: models.ExperimentRun | None = None) -> models.ExperimentRun:
    """InvestigationReport (orchestrator/qtrace.py) -> saari tables. Raw result rows store nahi hote —
    sirf aggregates + SHA-256 checksums (Ch 2.3 storage watch-item).
    `run` diya ho (live timeline wala) to steps pehle hi likhe ja chuke hain — sirf baaki fields bharte hain."""
    summary = report.summary()
    live = run is not None
    if run is None:
        run = models.ExperimentRun(experiment_id=experiment_id, replay_mode=replay_mode)
        db.add(run)
    run.dataset_version, run.model_version = dataset_version, model_version
    run.stop_reason, run.residual_share = report.stop_reason, report.residual_share
    run.semantic_layer_version, run.status = semantic_layer_version, report.status
    run.duration_ms, run.summary = report.duration_ms, summary
    db.flush()

    if not live:
        for s in report.steps:
            db.add(models.ExperimentStep(run_id=run.id, type=f"{s['phase']}:{s['type']}"[:40],
                                         input_ref=s.get("ref"), from_state=s.get("from"), to_state=s.get("to"),
                                         ts=_ts(s.get("ts"))))

    hyp_ids: dict[str, str] = {}
    for h in sorted(report.hypotheses, key=lambda h: h.depth):
        f = report.finding(h.id)
        row = models.Hypothesis(run_id=run.id, key=h.id, statement=h.statement, metric=h.metric,
                                dimensions=h.dimensions, test_type=h.test_type, source=h.source, prior=h.prior,
                                priority=h.priority, parent_id=hyp_ids.get(h.parent_id or ""), depth=h.depth,
                                status=h.status.value,
                                rejection_reason="; ".join(f.notes) if f is not None and f.notes else None)
        db.add(row)
        db.flush()
        hyp_ids[h.id] = row.id

    for q in report.queries:
        plan = models.QueryPlan(run_id=run.id, hypothesis_id=hyp_ids.get(q.hypothesis_key or ""), purpose=q.purpose,
                                metric=q.metric or "-", tables=[q.table] if q.table else [], columns=[],
                                test_type=q.purpose.split(":")[0][:20], sql=q.sql)
        db.add(plan)
        db.flush()
        db.add(models.QueryExecution(plan_id=plan.id, sql=q.sql, sql_hash=q.sql_hash, duration_ms=q.duration_ms,
                                     row_count=q.row_count, checksum=q.checksum))

    finding_ids: dict[str, str] = {}
    for f in report.findings:
        ci = f.ci or (None, None)
        row = models.Finding(run_id=run.id, hypothesis_id=hyp_ids.get(f.hypothesis_id), key=f.hypothesis_id,
                             statement=f.statement, status=f.status.value, method=f.method[:60],
                             evidence_score=f.score, share_of_delta=f.share_of_delta, amount=f.amount, ci_low=ci[0],
                             ci_high=ci[1], p_value=f.p_value, q_value=f.q_value, score_components=f.components,
                             label=f.label, gate_failed="DC/SA" if f.label == "Insufficient" else None, notes=f.notes)
        db.add(row)
        db.flush()
        finding_ids[f.hypothesis_id] = row.id
        for c in f.challenges:
            db.add(models.Challenge(finding_id=row.id, type=c["type"], origin=c.get("origin", "auto"),
                                    status="passed" if c["passed"] else "failed", result=c))

    for d in report.decomposition:
        db.add(models.Decomposition(run_id=run.id, factor=d["factor"], method=d["method"][:10],
                                    delta_value=d["amount"], share=d["share"]))

    gate = report.verify.get("gate") or {}
    band = gate.get("band") or {}
    db.add(models.Baseline(run_id=run.id, metric=report.spec.metric, method=str(gate.get("method", "none")).upper()[:10],
                           forecast=band.get("forecast"), sigma=band.get("sigma"), z_score=gate.get("z")))
    for c in (report.verify.get("health") or {}).get("checks", []):
        db.add(models.DataHealthCheck(run_id=run.id, check_name=c["check_name"], expected=c["expected"][:120],
                                      observed=c["observed"][:120], passed=c["passed"]))

    node_ids: dict[str, str] = {}
    for n in summary["graph"].get("nodes", []):
        row = models.EvidenceNode(run_id=run.id, type=n["data"].get("kind", "node")[:30], source_ref=n["id"],
                                  value=n["data"])
        db.add(row)
        db.flush()
        node_ids[n["id"]] = row.id
    for e in summary["graph"].get("edges", []):
        if e["source"] in node_ids and e["target"] in node_ids:
            db.add(models.EvidenceEdge(run_id=run.id, from_node=node_ids[e["source"]], to_node=node_ids[e["target"]],
                                       relation=e["label"]))
    for c in report.claims:
        db.add(models.Claim(run_id=run.id, finding_id=finding_ids.get(c.finding_key or ""), sentence=c.sentence,
                            claim_type=c.claim_type, evidence_node_ids=[node_ids.get(i, i) for i in c.evidence_node_ids]))
    for step, prompt, resp in report.llm_calls:
        record_llm_call(db, run.id, step, resp.model, prompt, resp.text, tokens_in=resp.tokens_in,
                        tokens_out=resp.tokens_out, latency_ms=resp.latency_ms)
    db.commit()
    return run
