"""11.3 New tables in v3.0."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, new_id, utcnow


class LLMCall(Base):
    """Exact replay + free-tier cost tracking."""
    __tablename__ = "llm_calls"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("experiment_runs.id"), index=True)
    step: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(120))
    prompt_hash: Mapped[str] = mapped_column(String(64), index=True)
    prompt: Mapped[str] = mapped_column(Text)
    response: Mapped[str] = mapped_column(Text)
    temperature: Mapped[float] = mapped_column(Float, default=0.0)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Baseline(Base):
    __tablename__ = "baselines"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("experiment_runs.id"), index=True)
    metric: Mapped[str] = mapped_column(String(64))
    method: Mapped[str] = mapped_column(String(10))                     # ETS | STL | YoY
    forecast: Mapped[float | None] = mapped_column(Float)
    sigma: Mapped[float | None] = mapped_column(Float)
    z_score: Mapped[float | None] = mapped_column(Float)


class Decomposition(Base):
    __tablename__ = "decompositions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("experiment_runs.id"), index=True)
    factor: Mapped[str] = mapped_column(String(64))
    method: Mapped[str] = mapped_column(String(10))                     # log | mix | rate | shapley
    delta_value: Mapped[float] = mapped_column(Float)
    share: Mapped[float | None] = mapped_column(Float)


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    finding_id: Mapped[str | None] = mapped_column(ForeignKey("findings.id"), index=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("experiment_runs.id"), index=True)
    sentence: Mapped[str] = mapped_column(Text)
    claim_type: Mapped[str] = mapped_column(String(20))                 # fact | association | interpretation | recommendation
    evidence_node_ids: Mapped[list] = mapped_column(JSON, default=list)


class DataHealthCheck(Base):
    __tablename__ = "data_health_checks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("experiment_runs.id"), index=True)
    check_name: Mapped[str] = mapped_column(String(40))
    expected: Mapped[str] = mapped_column(String(120))
    observed: Mapped[str] = mapped_column(String(120))
    passed: Mapped[bool] = mapped_column(Boolean)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(40))
    object_ref: Mapped[str | None] = mapped_column(String(255))
    sql_hash: Mapped[str | None] = mapped_column(String(64))
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str | None] = mapped_column(Text)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

