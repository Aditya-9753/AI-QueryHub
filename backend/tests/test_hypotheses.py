from app.schemas.qtrace import Hypothesis, HypStatus, QuestionSpec
from app.services.hypothesis_engine.drilldown import js_divergence, rank_dimensions
from app.services.hypothesis_engine.generator import generate_hypotheses
from app.services.hypothesis_engine.metric_tree import children_of
from app.services.orchestrator.budget import Budget
from app.services.orchestrator.priority import HypothesisQueue
from app.services.orchestrator.stopping import should_drilldown, stop_reason

SPEC = QuestionSpec(metric="revenue", filters={"city": "Delhi"}, period_current="2026-02",
                    period_base="2026-01", period_yoy="2025-02", intent="root_cause")


def test_four_sources_dedup():
    hyps = generate_hypotheses(SPEC)
    ids = {h.id for h in hyps}
    assert {"revenue.days", "revenue.orders_per_day", "revenue.aov"} <= ids
    assert "tpl.seasonality" in ids and "tpl.data_issue" in ids
    assert "tpl.calendar" not in ids            # metric-tree 'days' already cover karta hai


def test_llm_extras_grounding():
    def extras(_):
        return [Hypothesis(id="llm.competitor", statement="Competitor sale", metric="revenue",
                           dimensions=["competitor"], source="llm", test_type="corr"),
                Hypothesis(id="llm.channel", statement="App outage", metric="revenue",
                           dimensions=["channel"], source="llm", test_type="mix_rate")]
    by_id = {h.id: h for h in generate_hypotheses(SPEC, llm_extras=extras)}
    assert by_id["llm.competitor"].status == HypStatus.UNGROUNDED
    assert by_id["llm.channel"].status == HypStatus.GROUNDED
    assert by_id["llm.channel"].prior == 0.3


def test_metric_tree_children():
    aov = next(h for h in generate_hypotheses(SPEC) if h.id == "revenue.aov")
    kids = children_of(aov)
    assert {k.id for k in kids} == {"revenue.category_mix", "revenue.segment_aov"}
    assert all(k.depth == 1 and k.parent_id == "revenue.aov" for k in kids)


def test_priority_queue_order():
    q = HypothesisQueue()
    hyps = {h.id: h for h in generate_hypotheses(SPEC)}
    q.push(hyps["revenue.days"], exp_share=0.5, cost=1)
    q.push(hyps["revenue.aov"], exp_share=0.9, cost=1)
    q.push(hyps["tpl.seasonality"], exp_share=0.9, cost=3)
    assert [q.pop().id for _ in range(3)] == ["revenue.aov", "revenue.days", "tpl.seasonality"]


def test_stop_rule():
    b = Budget(max_llm_calls=2, max_queries=5)
    assert stop_reason(0.85, b, queue_empty=False) == "explained>=0.80"
    assert stop_reason(0.5, b, queue_empty=False) is None
    b.spend_query(5)
    assert stop_reason(0.5, b, queue_empty=False) == "budget_exhausted"
    assert should_drilldown(0.45, 0) and not should_drilldown(0.45, 2) and not should_drilldown(0.2, 0)


def test_drilldown_prefers_concentrated_dimension():
    ranked = rank_dimensions({
        "category": ({"E": 300, "F": 120, "G": 80}, {"E": 212, "F": 118, "G": 80}),
        "channel": ({"app": 250, "web": 250}, {"app": 205, "web": 205}),
    })
    assert ranked[0]["dimension"] == "category" and ranked[0]["segments"] == ["E"]
    assert js_divergence([0.5, 0.5], [0.5, 0.5]) == 0.0
