"""Request / response models for the HTTP API (Ch 14)."""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Mode = Literal["ASK", "ANALYZE", "INVESTIGATE"]
Role = Literal["admin", "analyst", "viewer"]
EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


# ------------------------------------------------------------------ auth
class SignupIn(BaseModel):
    email: str = Field(pattern=EMAIL_RE, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=120)


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str | None = None
    role: str
    is_active: bool = True
    created_at: datetime | None = None


class AuthOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


# ------------------------------------------------------------------ query
class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    mode: Literal["ASK", "ANALYZE"] | None = None   # None => auto
    sql: str | None = None                           # Monaco me edit kiya hua SQL => LLM skip
    datasource_id: str | None = None


class QueryResponse(BaseModel):
    history_id: str
    question: str
    mode: Mode
    datasource_id: str
    generated: bool
    attempts: int
    sql: str
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    duration_ms: float
    checksum: str
    answer: str
    answer_source: Literal["llm", "template"]
    warnings: list[str] = []
    trace: list[dict[str, Any]] = []          # pipeline stages + timings
    profile: dict[str, Any] | None = None      # deterministic insights (analytics/result_profile.py)


class HistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    question: str
    mode: str
    datasource_id: str | None
    sql: str | None
    generated: bool
    status: str
    error: str | None
    row_count: int | None
    duration_ms: float | None
    created_at: datetime


class SavedQueryIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    question: str
    sql: str
    mode: Literal["ASK", "ANALYZE"] = "ASK"
    datasource_id: str | None = None
    chart_spec: dict | None = None


class SavedQueryOut(SavedQueryIn):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime


# ------------------------------------------------------------------ datasources + schema
class DataSourceIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: Literal["postgres", "sqlite"]
    conn_secret_ref: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,63}$",
                                 description="Env var ka NAAM jisme connection URL hai (password yahan kabhi nahi)")
    readonly_role: str | None = None


class DataSourceOut(DataSourceIn):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_id: str
    is_default: bool = False


class ConnectionTestOut(BaseModel):
    ok: bool
    dialect: str
    tables: int
    duration_ms: float
    error: str | None = None


class SchemaColumnOut(BaseModel):
    name: str
    type: str
    sensitive: bool = False
    values: list[str] = []
    min: str | None = None
    max: str | None = None


class SchemaTableOut(BaseModel):
    name: str
    columns: list[SchemaColumnOut]


class SchemaOut(BaseModel):
    datasource_id: str
    dialect: str
    tables: list[SchemaTableOut]


# ------------------------------------------------------------------ experiments etc.
class ExperimentCreate(BaseModel):
    question: str
    mode: Mode = "INVESTIGATE"


class ExperimentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    question: str
    mode: str
    status: str
    created_at: datetime
    user_id: str | None = None
    owner: str | None = None


class ReplayRequest(BaseModel):
    mode: Literal["exact", "rederive"] = "exact"


class ChallengeCreate(BaseModel):
    finding_id: str
    type: str = "custom"
    description: str | None = None


class ChallengeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    finding_id: str
    type: str
    origin: str
    status: str
    result: dict | None


class MetricIn(BaseModel):
    name: str
    definition: str
    formula_sql: str
    grain: str = "day"


class MetricOut(MetricIn):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version: int


class ReportIn(BaseModel):
    name: str
    question: str
    sql: str
    chart_spec: dict | None = None
    schedule: str | None = None


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str | None
    action: str
    object_ref: str | None
    sql_hash: str | None
    blocked: bool
    reason: str | None
    ts: datetime
