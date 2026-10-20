import pytest

from app.schemas.qtrace import QuestionSpec
from app.services.experiment_planner.planner import plan_for
from app.services.experiment_planner.test_selector import select_test
from app.services.hypothesis_engine.generator import generate_hypotheses
from app.services.rag.semantic_layer import SemanticLayer, month_bounds
from app.services.sql_validator.firewall import firewall_check

LAYER = SemanticLayer()
SPEC = QuestionSpec(metric="revenue", filters={"city": "Delhi"}, period_current="2026-02",
                    period_base="2026-01", period_yoy="2025-02", intent="root_cause")


def test_month_bounds():
    assert month_bounds("2026-02") == ("2026-02-01", "2026-03-01")
    assert month_bounds("2025-12") == ("2025-12-01", "2026-01-01")


def test_render_passes_firewall():
    sql = LAYER.render("revenue", filters={"city": "Delhi"}, start="2026-02-01", end="2026-03-01",
                       group_by=("category",), per_day=True)
    assert "status <> 'cancelled'" in sql
    assert firewall_check(sql, role="viewer")


def test_render_rejects_unknown_dimension():
    with pytest.raises(ValueError):
        LAYER.render("revenue", filters={"email": "x"})


def test_render_quotes_values():
    sql = LAYER.render("revenue", filters={"city": "Delhi' OR 1=1 --"})
    assert "'Delhi'' OR 1=1 --'" in sql
    firewall_check(sql, role="analyst")


def test_plans_for_every_hypothesis():
    for h in generate_hypotheses(SPEC):
        for p in plan_for(h, SPEC, LAYER):
            firewall_check(p.sql, role="analyst")


def test_select_test():
    assert select_test("two_groups") == "welch_t"
    assert select_test("two_groups", daily=True) == "permutation"
