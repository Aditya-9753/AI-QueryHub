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
