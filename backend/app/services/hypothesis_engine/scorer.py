"""Hypothesis prior by source (Ch 8.4). Final evidence score evidence/scorer.py me hai."""
from app.schemas.qtrace import Hypothesis

PRIOR_BY_SOURCE = {"metric_tree": 0.5, "drilldown": 0.4, "template": 0.4, "llm": 0.3}


def assign_prior(h: Hypothesis) -> Hypothesis:
    return h.model_copy(update={"prior": PRIOR_BY_SOURCE[h.source]})
