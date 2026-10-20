from pydantic import BaseModel


class QueryPlan(BaseModel):
    hypothesis_id: str
    purpose: str                  # e.g. "base_period", "current_period", "control"
    metric: str
    tables: list[str]
    columns: list[str] = []
    test_type: str
    sql: str
