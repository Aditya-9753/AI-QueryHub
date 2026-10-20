"""Grounding mapper: hypothesis ke metric/columns semantic layer me hain? Nahi => UNGROUNDED."""
from app.schemas.qtrace import Hypothesis, HypStatus
from app.services.rag.semantic_layer import SemanticLayer


def ground(h: Hypothesis, layer: SemanticLayer) -> Hypothesis:
    ok = layer.grounded(h.metric, h.dimensions)
    return h.model_copy(update={"status": HypStatus.GROUNDED if ok else HypStatus.UNGROUNDED})
