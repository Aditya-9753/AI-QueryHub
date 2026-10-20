"""Step T: hypotheses from 4 sources — metric tree, drill-down, templates, LLM (grounded)."""
from collections.abc import Callable

from app.schemas.qtrace import Hypothesis, HypStatus, QuestionSpec
from app.services.hypothesis_engine.mapper import ground
from app.services.hypothesis_engine.metric_tree import factor_keys, metric_tree_hypotheses
from app.services.hypothesis_engine.scorer import assign_prior
from app.services.hypothesis_engine.templates import template_hypotheses
from app.services.rag.semantic_layer import SemanticLayer

LLMExtras = Callable[[QuestionSpec], list[Hypothesis]]


def generate_hypotheses(spec: QuestionSpec, llm_extras: LLMExtras | None = None,
                        layer: SemanticLayer | None = None, per_day: bool = True,
                        skip_templates: set[str] = frozenset()) -> list[Hypothesis]:
    """Deterministic pehle; LLM extras sirf grounding pass karein to GROUNDED (warna UNGROUNDED, user approve kar
    sakta hai). Drill-down hypotheses R->A loop ke andar bante hain (drilldown.py)."""
    layer = layer or SemanticLayer()
    hyps = metric_tree_hypotheses(spec.metric, per_day=per_day)
    hyps += template_hypotheses(spec, skip_covered=factor_keys(spec.metric, per_day), skip=skip_templates)
    if llm_extras is not None:
        for h in llm_extras(spec):
            hyps.append(ground(assign_prior(h.model_copy(update={"source": "llm"})), layer))
    seen, out = set(), []
    for h in hyps:
        if h.id not in seen:
            seen.add(h.id)
            out.append(h if h.status != HypStatus.PROPOSED else h.model_copy(update={"status": HypStatus.GROUNDED}))
    return out
