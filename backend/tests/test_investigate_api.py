"""Phase 4 'Done when': INVESTIGATE end-to-end via API — run, waterfall, evidence, exact replay checksum match,
re-derive stability, export (JSON/PDF), user challenge."""
import os
import sys
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "database" / "seed_data"))
import seed_demo  # noqa: E402


@pytest.fixture(scope="module")
def experiment(client):
    path = os.path.join(tempfile.gettempdir(), f"qh_orders_{os.getpid()}.db")
    if os.path.exists(path):
        os.remove(path)
    eng = create_engine(f"sqlite:///{path}")
    seed_demo.build(eng, factor=0.55, scale={"Delhi": 60, "Mumbai": 66, "Pune": 40})
    eng.dispose()
    os.environ["DS_TEST_INVESTIGATE"] = f"sqlite:///{path}"
    ds = client.post("/api/datasources", json={"name": "Investigate demo", "kind": "sqlite",
                                               "conn_secret_ref": "DS_TEST_INVESTIGATE"}).json()
    exp = client.post("/api/experiments", json={"question": "Feb me Delhi revenue kyun gira?",
                                                "datasource_id": ds["id"]}).json()
    run = client.post(f"/api/experiments/{exp['id']}/run", params={"sync": True}).json()
    assert run["status"] == "completed", run
    yield exp["id"]
    del os.environ["DS_TEST_INVESTIGATE"]


def test_report(client, experiment):
    body = client.get(f"/api/experiments/{experiment}").json()
    rep = body["report"]
    assert body["status"] == "completed" and rep["status"] == "completed"
    assert rep["spec"]["filters"] == {"city": "Delhi"} and rep["parse_source"] == "rules"
    assert rep["grounding"]["violations"] == 0
    assert body["run"]["model_version"].startswith("deterministic")
    keys = {f["key"] for f in rep["findings"] if f["status"] in ("supported", "upheld", "revised")}
    assert "revenue.days" in keys and ("revenue.category_mix" in keys or "revenue.dim:category" in keys)


def test_waterfall_sums_to_total(client, experiment):
    w = client.get(f"/api/experiments/{experiment}/decomposition").json()
    assert w["status"] == "completed" and w["steps"]
    assert abs(w["residual"]) < 1e-6 * abs(w["current"] - w["base"]) + 1e-6


def test_timeline_hypotheses_evidence(client, experiment):
    assert len(client.get(f"/api/experiments/{experiment}/timeline").json()) > 5
    hyps = client.get(f"/api/experiments/{experiment}/hypotheses").json()
    assert {"metric_tree", "template", "drilldown"} <= {h["source"] for h in hyps}
    ev = client.get(f"/api/experiments/{experiment}/evidence").json()
    ids = {n["id"] for n in ev["graph"]["nodes"]}
    assert "I" in ids and any(i.startswith("Q") for i in ids)
    assert all(i in ids for c in ev["claims"] for i in c["evidence_node_ids"])


def test_exact_replay_checksums_match(client, experiment):
    r = client.post(f"/api/experiments/{experiment}/replay", json={"mode": "exact"}).json()
    assert r["queries"] > 5 and r["match"] is True and r["matched"] == r["queries"]


def test_rederive_is_stable(client, experiment):
    r = client.post(f"/api/experiments/{experiment}/replay", json={"mode": "rederive"}).json()
    assert r["mode"] == "rederive" and r["stable"] is True


def test_export(client, experiment):
    js = client.get(f"/api/experiments/{experiment}/export").json()
    assert js["report"]["status"] == "completed" and js["timeline"]
    pdf = client.get(f"/api/experiments/{experiment}/export", params={"format": "pdf"})
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"


def test_user_challenge(client, experiment):
    findings = client.get(f"/api/experiments/{experiment}/findings").json()
    cal = next(f for f in findings if f["key"] == "revenue.days")
    ch = client.post("/api/challenges", json={"finding_id": cal["id"], "type": "data_quality"})
    assert ch.status_code == 200, ch.text
    assert ch.json()["origin"] == "user" and ch.json()["status"] == "upheld"
    bad = client.post("/api/challenges", json={"finding_id": cal["id"], "type": "custom"})
    assert bad.status_code == 422
    listed = client.get(f"/api/findings/{cal['id']}/challenges").json()
    assert any(c["origin"] == "user" for c in listed)


def test_provenance_and_dataset_version(client, experiment):
    """Ch 6.2 evidence node fields + Ch 17 as_of / dataset version."""
    body = client.get(f"/api/experiments/{experiment}").json()
    assert body["run"]["dataset_version"].startswith("asof=") and "data_through=" in body["run"]["dataset_version"]
    nodes = client.get(f"/api/experiments/{experiment}/evidence").json()["graph"]["nodes"]
    queries = [n["data"] for n in nodes if n["data"]["kind"] == "query"]
    q = next(d for d in queries if d["purpose"].startswith("core:"))
    for k in ("query_id", "dataset_version", "schema_snapshot", "metric_definition", "filters", "time_window",
              "duration_ms", "checksum", "analysis_method"):
        assert q.get(k) not in (None, "", []), k
    assert "updated_at <=" in q["sql"]                     # as_of snapshot filter
    assert any(n["data"].get("claim_ids") for n in nodes)  # node -> linked claim IDs


def test_doc_response_shape(client, experiment):
    """Ch 14.1: verify{data_health, z_score, band}, spec, stop_reason, residual_share, findings, rejected, claims."""
    b = client.get(f"/api/experiments/{experiment}").json()
    assert b["verify"]["data_health"] == "pass" and b["verify"]["z_score"] is not None
    assert {"spec", "stop_reason", "residual_share", "findings", "rejected", "claims"} <= b.keys()
    assert b["findings"] and all("share_of_delta" in f for f in b["findings"]) and b["rejected"]


def test_hypothesis_fields_and_shapley(client, experiment):
    rep = client.get(f"/api/experiments/{experiment}").json()["report"]
    h = next(x for x in rep["hypotheses"] if x["id"] == "revenue.aov")
    assert h["comparison_period"] == "2026-01 -> 2026-02" and h["expected_direction"] == "down"
    assert "amount" in h["required_columns"] and h["confounders"]
    core = rep["core"]
    assert abs(sum(core["shapley"].values()) - core["abs_change"]) < 1e-6 * abs(core["abs_change"])
    assert any(c["check_name"] == "outlier_days" for c in rep["verify"]["health"]["checks"])


def test_metric_edit_is_validated_and_triggers_replay_warning(client, experiment):
    """Semantic layer page ki edits pipeline use karti hai; badalne par replay warning (Ch 17)."""
    bad = client.post("/api/metrics", json={"name": "revenue", "definition": "x", "formula_sql": "pg_sleep(5)"})
    assert bad.status_code == 400
    old = next(m for m in client.get("/api/metrics").json() if m["name"] == "revenue")
    ok = client.post("/api/metrics", json={"name": "revenue", "definition": old["definition"] + " (edited)",
                                           "formula_sql": "SUM(amount * 1.0)", "grain": "day"})
    assert ok.status_code == 200 and ok.json()["version"] == old["version"] + 1
    r = client.post(f"/api/experiments/{experiment}/replay", json={"mode": "exact"}).json()
    assert r["match"] is True and r["warnings"]          # stored SQL same result, lekin definition badli
    client.post("/api/metrics", json={k: old[k] for k in ("name", "definition", "formula_sql", "grain")})
