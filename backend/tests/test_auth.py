
from app.core.config import get_settings
from app.core.security import hash_password, verify_password


def test_password_hashing():
    h = hash_password("s3cret-pass")
    assert h.startswith("pbkdf2_sha256$") and verify_password("s3cret-pass", h)
    assert not verify_password("wrong", h) and not verify_password("x", None)


def test_signup_login_roles(client):
    first = client.post("/api/auth/signup", json={"email": "Admin@Example.com", "password": "password123", "name": "A"})
    assert first.status_code == 201, first.text
    assert first.json()["user"]["role"] == "admin" and first.json()["user"]["email"] == "admin@example.com"

    second = client.post("/api/auth/signup", json={"email": "ana@example.com", "password": "password123"})
    assert second.json()["user"]["role"] == "analyst"
    assert client.post("/api/auth/signup", json={"email": "ana@example.com", "password": "password123"}).status_code == 409
    assert client.post("/api/auth/signup", json={"email": "bad", "password": "password123"}).status_code == 422
    assert client.post("/api/auth/signup", json={"email": "x@y.com", "password": "short"}).status_code == 422

    assert client.post("/api/auth/login", json={"email": "ana@example.com", "password": "nope"}).status_code == 401
    login = client.post("/api/auth/login", json={"email": "ANA@example.com", "password": "password123"})
    ana_token = login.json()["access_token"]
    ana = {"Authorization": f"Bearer {ana_token}"}
    assert client.get("/api/auth/me", headers=ana).json()["role"] == "analyst"

    admin = {"Authorization": f"Bearer {first.json()['access_token']}"}
    assert client.get("/api/admin/users", headers=ana).status_code == 403
    users = client.get("/api/admin/users", headers=admin).json()
    ana_id = next(u["id"] for u in users if u["email"] == "ana@example.com")
    assert client.patch(f"/api/admin/users/{ana_id}", json={"role": "viewer"}, headers=admin).json()["role"] == "viewer"
    assert client.get("/api/auth/me", headers=ana).json()["role"] == "viewer"      # role DB se, turant lagu

    admin_id = first.json()["user"]["id"]
    assert client.patch(f"/api/admin/users/{admin_id}", json={"role": "viewer"}, headers=admin).status_code == 409

    client.patch(f"/api/admin/users/{ana_id}", json={"is_active": False}, headers=admin)
    assert client.get("/api/auth/me", headers=ana).status_code == 401
    assert client.post("/api/auth/login", json={"email": "ana@example.com", "password": "password123"}).status_code == 403


def test_login_required_when_auth_enabled(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_disabled", False)
    assert client.get("/api/query/history").status_code == 401
    assert client.get("/api/query/history", headers={"Authorization": "Bearer garbage"}).status_code == 401
    assert client.post("/api/auth/dev-token").status_code == 404
