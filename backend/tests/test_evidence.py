import pytest

from app.services.analytics.fdr import benjamini_hochberg
from app.services.evidence.graph import EvidenceGraph
from app.services.evidence.scorer import (
    cross_query_agreement,
    data_coverage,
    evidence_score,
    old_score,
    statistical_strength,
)


def test_bh_worked_example():
    r = benjamini_hochberg({"H4": .001, "H2": .003, "H5": .048, "H3": .41, "H1": .62}, q=0.10)
    assert r["H4"] == (pytest.approx(0.005), True)
    assert r["H2"] == (pytest.approx(0.0075), True)
    assert r["H5"] == (pytest.approx(0.08), True)
    assert r["H3"] == (pytest.approx(0.5125), False)
    assert r["H1"] == (pytest.approx(0.62), False)


def test_scores_from_doc():
    old = {"DC": .9, "SA": .8, "SS": .7, "CQA": 1.0, "SC": .9, "ES": .9}
    assert old_score(old, 0.5) == pytest.approx(0.71)
    assert evidence_score(old, 0.5) == (0.433, "Weak")
    mix = {"DC": 1, "SA": 1, "SS": .9, "CQA": 1, "SC": 1, "ES": .445}
    assert evidence_score(mix, 0) == (0.891, "Strong")
    cal = {"DC": 1, "SA": 1, "SS": 1, "CQA": 1, "SC": 1, "ES": .489}
    assert evidence_score(cal, 0) == (0.915, "Strong")
    assert evidence_score({**mix, "DC": 0.5}, 0) == (None, "Insufficient")
    assert evidence_score(mix, 1.0)[0] == 0.0          # decisive contradiction


def test_components():
    assert data_coverage(28, 28, 0.002) == pytest.approx(0.998)
    assert statistical_strength(0.01, 0.05, 0.1, -0.01, 0.02) == 0.0   # CI includes 0
    assert cross_query_agreement([100]) == 0.5
    assert cross_query_agreement([100, 99.2]) == 1.0


def test_graph():
    g = EvidenceGraph()
    g.add_node("I", "insight", "Feb drop")
    g.add_node("F3", "finding", "Orders/day")
    g.add_edge("I", "F3", "contradicted_by")
    assert g.has_contradiction("I")
    rf = g.to_react_flow()
    assert len(rf["nodes"]) == 2 and rf["edges"][0]["animated"]
    with pytest.raises(ValueError):
        g.add_edge("I", "F3", "likes")
