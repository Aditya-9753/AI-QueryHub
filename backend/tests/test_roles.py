"""Analyst vs viewer: viewer = report consumer (NL ask + team investigations padhna),
analyst = investigator (manual SQL, run, challenge, replay). Sab backend par enforced."""
from app import models
from app.db.session import SessionLocal


def _signup(client, email: str) -> tuple[str, dict]:
    r = client.post("/api/auth/signup", json={"email": email, "password": "password123", "name": email.split("@")[0]})
    assert r.status_code == 201, r.text
    return r.json()["user"]["id"], {"Authorization": f"Bearer {r.json()['access_token']}"}


def _set_role(client, user_id: str, role: str) -> None:
    admin = {"Authorization": f"Bearer {client.post('/api/auth/dev-token', params={'role': 'admin'}).json()['access_token']}"}
    assert client.patch(f"/api/admin/users/{user_id}", json={"role": role}, headers=admin).status_code == 200


def test_viewer_vs_analyst_permissions(client):
    ana_id, ana = _signup(client, "rita.analyst@example.com")
    ana2_id, ana2 = _signup(client, "om.analyst@example.com")
    vie_id, vie = _signup(client, "vik.viewer@example.com")
    for uid in (ana_id, ana2_id):
        _set_role(client, uid, "analyst")
    _set_role(client, vie_id, "viewer")

    # manual SQL: analyst haan, viewer nahi
    sql = {"question": "x", "sql": "SELECT COUNT(*) AS n FROM orders"}
    assert client.post("/api/query", json=sql, headers=ana).status_code == 200
    r = client.post("/api/query", json=sql, headers=vie)
    assert r.status_code == 403 and r.json()["detail"]["status"] == "blocked"

    # investigations: sirf analyst bana / chala sakta hai
    assert client.post("/api/experiments", json={"question": "Feb me Delhi revenue kyun gira?"}, headers=vie).status_code == 403
    draft = client.post("/api/experiments", json={"question": "Feb me Delhi revenue kyun gira?"}, headers=ana).json()
    done = client.post("/api/experiments", json={"question": "Jan me Pune revenue kyun badha?"}, headers=ana).json()
    with SessionLocal() as db:                       # permission test: run ka result yahan matter nahi karta
        db.get(models.Experiment, done["id"]).status = "completed"
        db.commit()

    # team library: viewer ko sirf completed runs dikhte hain, owner ke naam ke saath
    team = client.get("/api/experiments", headers=vie).json()
    ids = {e["id"] for e in team}
    assert done["id"] in ids and draft["id"] not in ids
    assert next(e for e in team if e["id"] == done["id"])["owner"] == "rita.analyst"
    assert client.get(f"/api/experiments/{done['id']}", headers=vie).status_code == 200
    assert client.get(f"/api/experiments/{draft['id']}", headers=vie).status_code == 404
    assert client.get(f"/api/experiments/{done['id']}/findings", headers=vie).status_code == 200
    assert {e["id"] for e in client.get("/api/experiments", headers=ana2).json()}.isdisjoint({done["id"], draft["id"]})
    assert done["id"] in {e["id"] for e in client.get("/api/experiments", params={"scope": "team"}, headers=ana2).json()}

    # write actions: viewer kabhi nahi; doosra analyst sirf exact replay (verification), re-run / re-derive nahi
    assert client.post(f"/api/experiments/{done['id']}/replay", json={"mode": "exact"}, headers=vie).status_code == 403
    assert client.post(f"/api/experiments/{done['id']}/run", headers=ana2).status_code == 403
    assert client.post(f"/api/experiments/{done['id']}/replay", json={"mode": "rederive"}, headers=ana2).status_code == 403
    assert client.post("/api/challenges", json={"finding_id": "nope", "type": "battery"}, headers=vie).status_code == 403


def _token(client, role: str) -> dict:
    return {"Authorization": f"Bearer {client.post('/api/auth/dev-token', params={'role': role}).json()['access_token']}"}


def test_data_level_tiers_on_customers(client, fake_llm):
    """Same sawaal, teen roles: admin ko email milta hai, analyst ko email block, viewer ko customers table hi nahi."""
    admin, analyst = _token(client, "admin"), _token(client, "analyst")
    q = {"question": "customer emails", "sql": "SELECT city, email FROM customers"}
    assert client.post("/api/query", json=q, headers=admin).status_code == 200
    r = client.post("/api/query", json=q, headers=analyst)
    assert r.status_code == 400 and r.json()["detail"]["status"] == "blocked"
    assert client.post("/api/query", json={**q, "sql": "SELECT city FROM customers"}, headers=analyst).status_code == 200

    _, vie = _signup(client, "neha.viewer@example.com")
    _set_role(client, client.get("/api/auth/me", headers=vie).json()["id"], "viewer")
    fake_llm(["```sql\nSELECT city FROM customers\n```"])
    r = client.post("/api/query", json={"question": "customers kis city me hain?"}, headers=vie)
    assert r.status_code == 400 and r.json()["detail"]["status"] == "blocked"


def test_admin_control_center(client):
    admin = _token(client, "admin")
    for path in ("/api/admin/overview", "/api/admin/queries", "/api/admin/system"):
        assert client.get(path, headers=_token(client, "analyst")).status_code == 403
        assert client.get(path, headers=_token(client, "viewer")).status_code == 403
        assert client.get(path, headers=admin).status_code == 200

    ov = client.get("/api/admin/overview", params={"days": 7}, headers=admin).json()
    assert len(ov["queries"]["daily"]) == 7 and ov["queries"]["total"] >= ov["queries"]["ok"]
    assert set(ov["users"]["by_role"]) <= {"admin", "analyst", "viewer"}
    log = client.get("/api/admin/queries", headers=admin).json()
    assert log and {"question", "status", "sql", "user"} <= set(log[0])

    system = client.get("/api/admin/system", headers=admin).json()
    assert system["llm"]["groq"]["configured"] is False and "api_key" not in str(system).lower()

    r = client.post("/api/admin/users", headers=admin,
                    json={"email": "New.Viewer@example.com", "password": "password123", "name": "Nv"})
    assert r.status_code == 201 and r.json()["role"] == "viewer" and r.json()["email"] == "new.viewer@example.com"
    assert client.post("/api/admin/users", headers=admin,
                       json={"email": "new.viewer@example.com", "password": "password123"}).status_code == 409
    login = client.post("/api/auth/login", json={"email": "new.viewer@example.com", "password": "password123"})
    assert login.status_code == 200 and login.json()["user"]["role"] == "viewer"


def test_admin_sees_whole_org(client):
    _, ana = _signup(client, "zoya.analyst@example.com")
    _set_role(client, client.get("/api/auth/me", headers=ana).json()["id"], "analyst")
    exp = client.post("/api/experiments", json={"question": "Mar me Pune revenue kyun gira?"}, headers=ana).json()
    admin = _token(client, "admin")
    assert exp["id"] in {e["id"] for e in client.get("/api/experiments", params={"scope": "all"}, headers=admin).json()}
    # analyst "all" maange to bhi sirf apne runs
    other = _token(client, "analyst")
    assert exp["id"] not in {e["id"] for e in client.get("/api/experiments", params={"scope": "all"}, headers=other).json()}


def test_access_warnings_explain_hidden_data(client, fake_llm):
    _, vie = _signup(client, "ira.viewer@example.com")
    _set_role(client, client.get("/api/auth/me", headers=vie).json()["id"], "viewer")
    fake_llm(["```sql\nSELECT city, SUM(amount) AS spend FROM orders GROUP BY city\n```", "x"])
    body = client.post("/api/query", json={"question": "top customers with email"}, headers=vie).json()
    assert any("'customers' table" in w and "viewer" in w for w in body.get("warnings", [])), body

    fake_llm(["```sql\nSELECT city FROM customers\n```", "x"])
    analyst = _token(client, "analyst")
    body = client.post("/api/query", json={"question": "customers ka email aur city"}, headers=analyst).json()
    assert any(w.startswith("email") and "analyst" in w for w in body["warnings"])
