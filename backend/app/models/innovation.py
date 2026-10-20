"""11.2 Innovation layer tables (v2 + v3 columns)."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, new_id, utcnow


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    question: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(20))                       # ASK | ANALYZE | INVESTIGATE
    status: Mapped[str] = mapped_column(String(20), default="created")  # created | queued | running | completed | failed
    datasource_id: Mapped[str | None] = mapped_column(String(64))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExperimentRun(Base):
    __tablename__ = "experiment_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"), index=True)
    dataset_version: Mapped[str | None] = mapped_column(String(255))
    model_version: Mapped[str | None] = mapped_column(String(120))
    stop_reason: Mapped[str | None] = mapped_column(String(64))
    residual_share: Mapped[float | None] = mapped_column(Float)
    semantic_layer_version: Mapped[str | None] = mapped_column(String(64))
    replay_mode: Mapped[str] = mapped_column(String(20), default="original")  # original | exact | rederive
    status: Mapped[str | None] = mapped_column(String(20))                    # completed | data_issue | within_normal
    duration_ms: Mapped[float | None] = mapped_column(Float)
    summary: Mapped[dict | None] = mapped_column(JSON)   # aggregates only (no raw rows) — storage watch-item
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Hypothesis(Base):
    __tablename__ = "hypotheses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("experiment_runs.id"), index=True)
    key: Mapped[str | None] = mapped_column(String(120))                # e.g. "revenue.aov"
    statement: Mapped[str] = mapped_column(Text)
    metric: Mapped[str | None] = mapped_column(String(64))
    dimensions: Mapped[list] = mapped_column(JSON, default=list)
    test_type: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(20))                     # metric_tree | drilldown | template | llm
    prior: Mapped[float] = mapped_column(Float, default=0.5)
    priority: Mapped[float] = mapped_column(Float, default=0.0)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("hypotheses.id"))
    depth: Mapped[int] = mapped_column(Integer, default=0)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="proposed")


class ExperimentStep(Base):
    """Append-only timeline — har state change ek nayi row."""
    __tablename__ = "experiment_steps"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("experiment_runs.id"), index=True)
    type: Mapped[str] = mapped_column(String(40))
    input_ref: Mapped[str | None] = mapped_column(String(255))
    output_ref: Mapped[str | None] = mapped_column(String(255))
    from_state: Mapped[str | None] = mapped_column(String(20))
    to_state: Mapped[str | None] = mapped_column(String(20))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class QueryPlan(Base):
    __tablename__ = "query_plans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("experiment_runs.id"), index=True)
    hypothesis_id: Mapped[str | None] = mapped_column(ForeignKey("hypotheses.id"), index=True)
    purpose: Mapped[str | None] = mapped_column(String(80))
    metric: Mapped[str] = mapped_column(String(64))
    tables: Mapped[list] = mapped_column(JSON, default=list)
    columns: Mapped[list] = mapped_column(JSON, default=list)
    test_type: Mapped[str] = mapped_column(String(20))
    sql: Mapped[str | None] = mapped_column(Text)


class QueryExecution(Base):
    __tablename__ = "query_executions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    plan_id: Mapped[str | None] = mapped_column(ForeignKey("query_plans.id"), index=True)
    sql: Mapped[str] = mapped_column(Text)
    sql_hash: Mapped[str] = mapped_column(String(64), index=True)
    duration_ms: Mapped[float] = mapped_column(Float)
    row_count: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64))                   # SHA-256 of sorted rows
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EvidenceNode(Base):
    __tablename__ = "evidence_nodes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("experiment_runs.id"), index=True)
    type: Mapped[str] = mapped_column(String(30))                       # query | finding | insight | challenge
    source_ref: Mapped[str | None] = mapped_column(String(255))
    value: Mapped[dict | None] = mapped_column(JSON)


class EvidenceEdge(Base):
    __tablename__ = "evidence_edges"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("experiment_runs.id"), index=True)
    from_node: Mapped[str] = mapped_column(ForeignKey("evidence_nodes.id"))
    to_node: Mapped[str] = mapped_column(ForeignKey("evidence_nodes.id"))
    relation: Mapped[str] = mapped_column(String(30))                   # supported_by | contradicted_by


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("experiment_runs.id"), index=True)
    hypothesis_id: Mapped[str | None] = mapped_column(ForeignKey("hypotheses.id"))
    key: Mapped[str | None] = mapped_column(String(160))
    statement: Mapped[str] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(String(20))
    method: Mapped[str | None] = mapped_column(String(60))
    evidence_score: Mapped[float | None] = mapped_column(Float)
    share_of_delta: Mapped[float | None] = mapped_column(Float)
    amount: Mapped[float | None] = mapped_column(Float)
    ci_low: Mapped[float | None] = mapped_column(Float)
    ci_high: Mapped[float | None] = mapped_column(Float)
    p_value: Mapped[float | None] = mapped_column(Float)
    q_value: Mapped[float | None] = mapped_column(Float)
    score_components: Mapped[dict | None] = mapped_column(JSON)
    label: Mapped[str | None] = mapped_column(String(20))               # Strong | Moderate | Weak | Insufficient
    gate_failed: Mapped[str | None] = mapped_column(String(20))
    notes: Mapped[list | None] = mapped_column(JSON)


class Challenge(Base):
    __tablename__ = "challenges"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    finding_id: Mapped[str] = mapped_column(ForeignKey("findings.id"), index=True)
    type: Mapped[str] = mapped_column(String(40))
    origin: Mapped[str] = mapped_column(String(10))                     # auto | user
    status: Mapped[str] = mapped_column(String(20), default="pending")  # passed | failed | upheld | revised | overturned
    result: Mapped[dict | None] = mapped_column(JSON)


class MetricDefinition(Base):
    """Semantic layer — business metrics ki official SQL definitions."""
    __tablename__ = "metric_definitions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    definition: Mapped[str] = mapped_column(Text)
    formula_sql: Mapped[str] = mapped_column(Text)
    grain: Mapped[str] = mapped_column(String(20), default="day")
    version: Mapped[int] = mapped_column(Integer, default=1)
