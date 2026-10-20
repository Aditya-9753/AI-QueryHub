"""Per-investigation budget (Ch 8.9): <= 10-15 LLM calls, <= 40 SQL queries."""
from dataclasses import dataclass

from app.core.config import get_settings


@dataclass
class Budget:
    max_llm_calls: int = 15
    max_queries: int = 40
    llm_calls: int = 0
    queries: int = 0

    @classmethod
    def from_settings(cls) -> "Budget":
        s = get_settings()
        return cls(max_llm_calls=s.qtrace_max_llm_calls, max_queries=s.qtrace_max_queries)

    def left(self) -> bool:
        return self.llm_calls < self.max_llm_calls and self.queries < self.max_queries

    def spend_llm(self, n: int = 1) -> None:
        self.llm_calls += n

    def spend_query(self, n: int = 1) -> None:
        self.queries += n

    def remaining(self) -> dict:
        return {"llm_calls": self.max_llm_calls - self.llm_calls, "queries": self.max_queries - self.queries}
