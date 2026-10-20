"""Phase 2 'Done when' (noise -> early exit), data issue exit, Q-step parser."""
import os
import tempfile
from datetime import date

import numpy as np
import pytest

from app.schemas.qtrace import QuestionSpec
from app.services.orchestrator.qtrace import QTraceConfig, QTracePlus
from app.services.orchestrator.question_parser import QuestionParseError, parse_rules
from app.services.rag.semantic_layer import SemanticLayer, daily_sales_metrics
from tests.eval_suite.benchmark import engine_for, scenario_data

LAYER = SemanticLayer(daily_sales_metrics())
VALUES = {"city": ["Delhi", "Mumbai", "Pune"], "category": ["Electronics", "Fashion", "Grocery"]}


def _run(kind: str, city: str = "Delhi", seed: int = 3, **extra):
    s = {"id": f"T-{kind}", "kind": kind, "city": city, "period_base": "2026-01", "period_current": "2026-02",
         **extra}
    base, planted = scenario_data(s, seed)
    eng = engine_for(planted, os.path.join(tempfile.gettempdir(), f"qh_test_{kind}_{os.getpid()}.db"))
    spec = QuestionSpec(metric="revenue", filters={"city": city}, period_current="2026-02", period_base="2026-01",
                        period_yoy="2025-02")
    try:
        return QTracePlus(eng, LAYER, config=QTraceConfig(n_boot=400, n_perm=400)).run(spec=spec)
    finally:
        eng.dispose()


def test_noise_only_exits_early():
    r = _run("noise_only")
    assert r.status == "within_normal"
    assert r.verify["gate"]["method"] == "ets" and abs(r.verify["gate"]["z"]) <= 1.96
    assert r.findings == [] and r.claims[0].claim_type == "fact" and "normal" in r.claims[0].sentence
    assert r.grounding["violations"] == 0
    assert r.budget["queries"] <= 6                       # sirf Verify queries chali


def test_missing_days_is_data_issue():
    r = _run("missing_days", start="2026-02-12", n_days=3)
    assert r.status == "data_issue"
    failed = [c for c in r.verify["health"]["checks"] if not c["passed"]]
    assert failed[0]["check_name"] == "completeness" and failed[0]["observed"] == "0.893"


def test_strong_mix_shift_is_found_and_localized():
    r = _run("mix_shift", category="Electronics", start="2026-02-01", end="2026-02-28", factor=0.55)
    assert r.status == "completed"
    dim = r.finding("revenue.dim:category")
    assert dim is not None and dim.data["top_segment"] == "Electronics"
    keys = [f.hypothesis_id for f in r.ranked_supported()]
    assert "revenue.category_mix" in keys
    assert r.grounding["violations"] == 0


def test_parser_rules():
    s = parse_rules("Feb me Delhi revenue kyun gira?", LAYER, VALUES, latest=date(2026, 2, 28))
    assert (s.metric, s.filters, s.period_current, s.period_base, s.period_yoy, s.intent) == \
        ("revenue", {"city": "Delhi"}, "2026-02", "2026-01", "2025-02", "root_cause")
    s = parse_rules("Jan vs Feb 2026 Mumbai Electronics orders", LAYER, VALUES)
    assert (s.metric, s.period_base, s.period_current) == ("orders", "2026-01", "2026-02")
    assert s.filters == {"city": "Mumbai", "category": "Electronics"}
    s = parse_rules("December me Pune ka AOV kyun badha", LAYER, VALUES, latest=date(2026, 2, 28))
    assert (s.metric, s.period_current, s.period_base) == ("aov", "2025-12", "2025-11")
    with pytest.raises(QuestionParseError):
        parse_rules("Delhi ka haal kya hai?", LAYER, VALUES)


def test_deterministic_rederive():
    """Same data + same seeds => same findings (re-derive stability)."""
    a = _run("mix_shift", category="Fashion", start="2026-02-05", end="2026-02-28", factor=0.6)
    b = _run("mix_shift", category="Fashion", start="2026-02-05", end="2026-02-28", factor=0.6)
    sa = {f.hypothesis_id: (f.status, round(f.share_of_delta, 9), f.ci) for f in a.findings}
    sb = {f.hypothesis_id: (f.status, round(f.share_of_delta, 9), f.ci) for f in b.findings}
    assert sa == sb and np.isclose(a.explained or 0, b.explained or 0)
