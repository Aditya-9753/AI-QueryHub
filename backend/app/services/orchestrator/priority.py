"""F27: Priority(h) = prior(h) x ExpShare(h) / Cost(h)  + priority queue."""
import heapq
import itertools

from app.schemas.qtrace import Hypothesis


def priority(prior: float, exp_share: float, cost: float) -> float:
    return prior * exp_share / max(cost, 1e-9)


class HypothesisQueue:
    """Max-priority queue. ExpShare sasti probe query se aata hai; Cost = expected LLM calls + queries."""

    def __init__(self) -> None:
        self._heap: list[tuple[float, int, Hypothesis]] = []
        self._counter = itertools.count()

    def push(self, h: Hypothesis, exp_share: float = 1.0, cost: float = 1.0) -> None:
        h.priority = priority(h.prior, exp_share, cost)
        heapq.heappush(self._heap, (-h.priority, next(self._counter), h))

    def pop(self) -> Hypothesis:
        return heapq.heappop(self._heap)[2]

    def items(self) -> list[Hypothesis]:
        return [h for _, _, h in self._heap]

    def __len__(self) -> int:
        return len(self._heap)

    def __bool__(self) -> bool:
        return bool(self._heap)
