"""Phase 3 'Done when': Ch 13.8 jaisa output — lekin poore Q-TRACE+ pipeline se (SQL -> maths), hardcoded nahi."""
import pytest

from app.schemas.qtrace import SUPPORTED_LIKE, HypStatus
from tests.eval_suite import worked_example as we


@pytest.fixture(scope="module")
def report():
    return we.run()


def shares(r):
    return {d["factor"]: d for d in r.decomposition}


def test_verify_and_totals(report):
    assert report.status == "completed"
    g = report.verify["gate"]
    assert g["method"] == "ets" and g["status"] == "anomaly" and g["z"] < -1.96
    assert report.verify["health"]["ok"]
    assert report.core["T0"] == pytest.approx(5.00e7)
    assert report.core["T1"] == pytest.approx(4.0608e7)
    assert report.core["rel_change"] == pytest.approx(-0.188, abs=1e-3)
    assert report.core["per_day_change"] == pytest.approx(-0.101, abs=1e-3)


def test_log_decomposition_from_sql(report):
    s = shares(report)
    assert s["days"]["share"] == pytest.approx(0.489, abs=1e-3)
    assert s["orders_per_day"]["share"] == pytest.approx(0.017, abs=1e-3)
    assert s["aov"]["share"] == pytest.approx(0.494, abs=1e-3)
    assert s["days"]["amount"] / 1e5 == pytest.approx(-45.95, abs=0.01)
    assert s["mix"]["share"] == pytest.approx(0.445, abs=1e-3)
    assert s["rate"]["share"] == pytest.approx(0.049, abs=1e-3)
    assert s["mix"]["amount"] / 1e5 == pytest.approx(-41.8, abs=0.05)


def test_findings_and_statuses(report):
    f = report.finding
    mix = f("revenue.category_mix")
    assert mix.data["mix"] == pytest.approx(-440) and mix.data["rate"] == pytest.approx(-48)
    assert mix.data["dimension"] == "category" and mix.data["top_segment"] == "Electronics"
    assert f("revenue.days").status in SUPPORTED_LIKE and f("revenue.days").label == "Strong"
    assert f("revenue.days").score == pytest.approx(0.915, abs=0.002)
    assert mix.status == HypStatus.UPHELD and mix.label == "Strong"
    assert mix.score == pytest.approx(0.89, abs=0.02)
    assert f("revenue.orders_per_day").status == HypStatus.REJECTED          # CI includes 0 (-0.4%)
    assert f("tpl.data_issue").status == HypStatus.REJECTED
    assert {c["type"] for c in mix.challenges} >= {"seasonality", "small_sample", "data_quality", "simpson",
                                                     "market_wide"}
    assert all(c["passed"] for c in mix.challenges)


def test_did_and_reconciliation(report):
    conc = report.finding("tpl.concurrent_event")
    assert report.controls == ["Mumbai", "Pune"]
    if conc is not None:
        assert conc.data["did"] == pytest.approx(-0.086, abs=1e-3)
        assert conc.data["control_change"] == pytest.approx(-0.02, abs=1e-3)
    assert report.reconciliation["cqa"] == 1.0
    assert report.reconciliation["diff_rel"] == pytest.approx(-0.008, abs=1e-4)


def test_trust_layer(report):
    assert report.grounding["violations"] == 0
    assert report.claims and all(c.evidence_node_ids for c in report.claims)
    assert report.explained == pytest.approx(0.983, abs=0.002)
    node_ids = {n["id"] for n in report.graph["nodes"]}
    assert all(i in node_ids for c in report.claims for i in c.evidence_node_ids)
    assert len(report.queries) <= report.budget["max_queries"]


def test_without_normalization_old_qtrace_mistake():
    """Purana Q-TRACE: raw orders 10,000 -> 9,000 dekh kar 'order volume gira' ko supported bolta (Ch 10.4)."""
    r = we.run(we.QTraceConfig(per_day=False))
    orders = r.finding("revenue.orders")
    assert orders is not None and orders.status in SUPPORTED_LIKE
    assert orders.effect == pytest.approx(-0.10, abs=1e-3)
