DELHI_SQL = "```sql\nSELECT SUM(amount) AS revenue FROM orders WHERE city = 'Delhi' AND status <> 'cancelled';\n```"


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_manual_sql_runs_read_only(client):
    r = client.post("/api/query", json={"question": "city-wise revenue",
                                        "sql": "SELECT city, SUM(amount) AS revenue FROM orders GROUP BY city ORDER BY city"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rows"] == [["Delhi", 150], ["Pune", 70]]
    assert body["sql"].endswith("LIMIT 5000") and len(body["checksum"]) == 64
    assert body["generated"] is False and body["answer_source"] == "template"


def test_firewall_blocks_and_audits(client):
    r = client.post("/api/query", json={"question": "x", "sql": "DROP TABLE orders"})
    assert r.status_code == 400 and r.json()["detail"]["status"] == "blocked"
    audit = client.get("/api/admin/audit", params={"blocked_only": True}).json()
    assert audit and audit[0]["blocked"] is True


def test_nl_question_with_llm(client, fake_llm):
    llm = fake_llm([DELHI_SQL, "February me Delhi ka revenue 150 tha."])
    r = client.post("/api/query", json={"question": "February mein Delhi ka revenue kitna tha?"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "ASK" and body["generated"] and body["attempts"] == 1
    assert body["rows"] == [[150]]
    assert body["answer"] == "February me Delhi ka revenue 150 tha." and body["answer_source"] == "llm"
    assert "TABLE orders" in llm.prompts[0] and "Delhi" in llm.prompts[0]      # schema + values prompt me
    assert "TABLE users" not in llm.prompts[0] and "password_hash" not in llm.prompts[0]   # app tables kabhi nahi


def test_invented_number_falls_back_to_template(client, fake_llm):
    fake_llm([DELHI_SQL, "Delhi ka revenue 999 tha."])
    body = client.post("/api/query", json={"question": "Delhi revenue?"}).json()
    assert body["answer_source"] == "template" and body["answer"] == "revenue: 150"


def test_lakh_crore_rounding_is_grounded(client, fake_llm):
    fake_llm(["```sql\nSELECT 11834567.0 AS revenue FROM orders LIMIT 1\n```", "Revenue ₹1.18 crore (118.35 lakh) tha."])
    assert client.post("/api/query", json={"question": "revenue?"}).json()["answer_source"] == "llm"


def test_repair_after_execution_error(client, fake_llm):
    fake_llm(["SELECT nope FROM orders", "```sql\nSELECT COUNT(*) AS n FROM orders\n```"])
    body = client.post("/api/query", json={"question": "kitne orders?"}).json()
    assert body["attempts"] == 2 and body["rows"] == [[3]]


def test_destructive_llm_sql_blocked_without_retry(client, fake_llm):
    llm = fake_llm(["DELETE FROM orders", "```sql\nSELECT 1\n```"])
    r = client.post("/api/query", json={"question": "saare orders delete kar do"})
    assert r.status_code == 400 and r.json()["detail"]["status"] == "blocked"
    assert len(llm.replies) == 1                                       # dobara LLM se nahi poocha


def test_sensitive_column_blocked(client, fake_llm):
    fake_llm(["```sql\nSELECT email FROM customers\n```"])
    r = client.post("/api/query", json={"question": "customers ke email"}, headers=_analyst_headers(client))
    assert r.status_code == 400 and "column not allowed" in r.json()["detail"]["message"]


def test_llm_unavailable_503(client, fake_llm):
    fake_llm([])
    r = client.post("/api/query", json={"question": "Delhi revenue?"})
    assert r.status_code == 503 and r.json()["detail"]["status"] == "llm_error"


def test_investigate_question_routes_to_analyze(client, fake_llm):
    fake_llm(["```sql\nSELECT city, SUM(amount) AS revenue FROM orders GROUP BY city\n```"])
    body = client.post("/api/query", json={"question": "Feb me Delhi revenue kyun gira?"}).json()
    assert body["mode"] == "ANALYZE" and body["warnings"]


def test_history_and_saved_queries(client):
    hist = client.get("/api/query/history").json()
    assert {h["status"] for h in hist} >= {"ok", "blocked", "llm_error"}

    sq = client.post("/api/saved-queries", json={"name": "Delhi revenue", "question": "Delhi revenue?",
                                                 "sql": "SELECT SUM(amount) AS revenue FROM orders WHERE city = 'Delhi'"})
    assert sq.status_code == 201, sq.text
    sq_id = sq.json()["id"]
    assert any(s["id"] == sq_id for s in client.get("/api/saved-queries").json())
    assert client.post(f"/api/saved-queries/{sq_id}/run").json()["rows"] == [[150]]
    assert client.post("/api/saved-queries", json={"name": "bad", "question": "x",
                                                   "sql": "DELETE FROM orders"}).status_code == 400
    assert client.delete(f"/api/saved-queries/{sq_id}").status_code == 204


def test_hypotheses_preview(client):
    spec = {"metric": "revenue", "filters": {"city": "Delhi"}, "period_current": "2026-02",
            "period_base": "2026-01", "intent": "root_cause"}
    ids = [h["id"] for h in client.post("/api/hypotheses/generate", json=spec).json()]
    assert "revenue.aov" in ids


def test_experiment_crud_and_metrics(client):
    exp = client.post("/api/experiments", json={"question": "Feb me Delhi revenue kyun gira?"}).json()
    assert client.get(f"/api/experiments/{exp['id']}").json()["status"] == "created"
    names = {m["name"] for m in client.get("/api/metrics").json()}
    assert {"revenue", "aov", "cancel_rate"} <= names


def _analyst_headers(client):
    from app.core.security import create_access_token

    return {"Authorization": f"Bearer {create_access_token('dev', 'dev@local', 'analyst')}"}


def test_trace_and_profile_in_response(client, fake_llm):
    fake_llm(["```sql\nSELECT city, SUM(amount) AS revenue FROM orders GROUP BY city\n```", "Delhi 150, Pune 70."])
    body = client.post("/api/query", json={"question": "city-wise revenue", "mode": "ANALYZE"}).json()
    keys = [s["key"] for s in body["trace"]]
    assert keys == ["context", "llm_sql", "firewall", "execute", "answer", "profile"]
    fw = next(s for s in body["trace"] if s["key"] == "firewall")
    assert len(fw["layers"]) == 4 and fw["tables"] == ["orders"] and "LIMIT 5000 injected" in fw["layers"][3]["detail"]
    p = body["profile"]
    assert p["shape"] == "breakdown" and p["stats"]["total"] == 220
    top = next(i for i in p["insights"] if i["kind"] == "top")
    assert top["values"]["label"] == "Delhi" and abs(top["values"]["share"] - 150 / 220) < 1e-9


def test_manual_sql_trace_skips_llm(client):
    body = client.post("/api/query", json={"question": "x", "sql": "SELECT COUNT(*) AS n FROM orders"}).json()
    assert [s["key"] for s in body["trace"]] == ["firewall", "execute", "answer", "profile"]
    assert body["profile"]["shape"] == "scalar"
