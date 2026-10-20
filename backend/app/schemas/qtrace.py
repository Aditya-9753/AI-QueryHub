"""Core Pydantic models (Ch 11.4)."""
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

TestType = Literal[
    "log_decomp", "mix_rate", "did", "bootstrap", "chi2", "corr",
    "yoy", "data_health",          # templates (seasonality, data issue) ke liye
]


class HypStatus(str, Enum):
    PROPOSED = "proposed"; GROUNDED = "grounded"; UNGROUNDED = "ungrounded"
    PLANNED = "planned"; TESTED = "tested"; SUPPORTED = "supported"
    REJECTED = "rejected"; INCONCLUSIVE = "inconclusive"; CHALLENGED = "challenged"
    UPHELD = "upheld"; REVISED = "revised"; OVERTURNED = "overturned"
    NOT_TESTED = "not_tested"


SUPPORTED_LIKE = {HypStatus.SUPPORTED, HypStatus.UPHELD, HypStatus.REVISED}


class QuestionSpec(BaseModel):
    metric: str
    filters: dict[str, str] = {}
    period_current: str
    period_base: str
    period_yoy: str | None = None
    intent: Literal["lookup", "compare", "trend", "root_cause"] = "root_cause"
    normalize: Literal["none", "per_day"] = "per_day"
    controls: list[str] = []


class Hypothesis(BaseModel):
    id: str
    statement: str
    metric: str                                   # semantic-layer name
    dimensions: list[str] = []
    comparison_period: str | None = None
    expected_direction: Literal["up", "down", "any"] = "any"
    required_columns: list[str] = []
    confounders: list[str] = []
    source: Literal["metric_tree", "drilldown", "template", "llm"]
    prior: float = 0.5
    priority: float = 0.0
    parent_id: str | None = None
    depth: int = 0
    test_type: TestType
    status: HypStatus = HypStatus.PROPOSED


class Finding(BaseModel):
    hypothesis_id: str
    statement: str = ""
    share_of_delta: float
    effect: float
    ci: tuple[float, float] | None = None
    p_value: float | None = None
    q_value: float | None = None
    components: dict[str, float] = {}             # DC, SA, SS, CQA, SC, ES
    contradiction_penalty: float = 0.0            # CP: 0 / 0.3 / 0.6 / 1
    score: float | None = None                    # None => INSUFFICIENT / not scored
    label: Literal["Strong", "Moderate", "Weak", "Insufficient"] | None = None
    challenges: list[dict] = Field(default_factory=list)
    # pipeline details (v3 implementation)
    status: HypStatus = HypStatus.TESTED
    method: str = ""
    amount: float | None = None                   # share x (R1 - R0)
    deterministic: bool = False
    mde: float | None = None
    parent_id: str | None = None
    depth: int = 0
    source: str = "metric_tree"
    claim_type: Literal["fact", "association"] = "association"
    notes: list[str] = Field(default_factory=list)
    data: dict = Field(default_factory=dict)      # test-specific numbers (n, n_req, segments, did, ...)


class Claim(BaseModel):
    sentence: str
    claim_type: Literal["fact", "association", "interpretation", "recommendation"]
    evidence_node_ids: list[str]                  # empty => validator blocks it
    finding_key: str | None = None
