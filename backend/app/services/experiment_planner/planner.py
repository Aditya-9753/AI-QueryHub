"""Hypothesis -> semantic-layer SQL plans. LLM sirf parameters bharta hai; SQL template se aata hai."""
from app.schemas.qtrace import Hypothesis, QuestionSpec
from app.services.experiment_planner.query_plan import QueryPlan
from app.services.rag.semantic_layer import SemanticLayer, month_bounds


def plan_for(h: Hypothesis, spec: QuestionSpec, layer: SemanticLayer) -> list[QueryPlan]:
    m = layer.get(spec.metric)
    base, cur = month_bounds(spec.period_base), month_bounds(spec.period_current)
    group_by: tuple[str, ...] = tuple(h.dimensions)
    filters = dict(spec.filters)
    plans: list[QueryPlan] = []

    def add(purpose: str, start: str, end: str, flt: dict, gb: tuple[str, ...], per_day: bool = True):
        sql = layer.render(spec.metric, filters=flt, start=start, end=end, group_by=gb, per_day=per_day)
        plans.append(QueryPlan(hypothesis_id=h.id, purpose=purpose, metric=spec.metric, tables=[m.table],
                               columns=list(gb), test_type=h.test_type, sql=sql))

    if h.test_type == "did":
        city_free = {k: v for k, v in filters.items() if k != "city"}
        add("treated+controls_base", *base, city_free, ("city",), per_day=False)
        add("treated+controls_current", *cur, city_free, ("city",), per_day=False)
    elif h.test_type == "yoy" and spec.period_yoy:
        yoy_base = month_bounds(_shift_year(spec.period_base))
        add("last_year_base", *yoy_base, filters, group_by, per_day=False)
        add("last_year_current", *month_bounds(spec.period_yoy), filters, group_by, per_day=False)
    else:
        add("base_period", *base, filters, group_by)
        add("current_period", *cur, filters, group_by)
    return plans


def _shift_year(period: str, years: int = -1) -> str:
    y, m = period.split("-")
    return f"{int(y) + years:04d}-{m}"
