"""Supabase Auth: legacy HS256 token verify + local user auto-provision (email se)."""
from datetime import datetime, timedelta, timezone

from jose import jwt

from app.core.config import get_settings

SECRET = "super-secret-jwt-token-with-at-least-32-characters"


def _token(email: str, aud: str = "authenticated", secret: str = SECRET) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"iss": "https://abcd.supabase.co/auth/v1", "sub": "8f1c-uuid", "aud": aud, "email": email,
                       "role": "authenticated", "user_metadata": {"full_name": "Supa User"},
                       "iat": now, "exp": now + timedelta(hours=1)}, secret, algorithm="HS256")


def test_supabase_token_maps_to_local_user(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "supabase_jwt_secret", SECRET)
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {_token('Supa@Example.com')}"})
    assert me.status_code == 200, me.text
    assert me.json()["email"] == "supa@example.com" and me.json()["name"] == "Supa User"
    again = client.get("/api/auth/me", headers={"Authorization": f"Bearer {_token('supa@example.com')}"})
    assert again.json()["id"] == me.json()["id"]                       # same user, dobara create nahi


def test_supabase_token_rejected_when_invalid(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "supabase_jwt_secret", SECRET)
    bad_sig = _token("x@example.com", secret="another-secret-another-secret-another-secret")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {bad_sig}"}).status_code == 401
    wrong_aud = _token("x@example.com", aud="anon")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {wrong_aud}"}).status_code == 401
    monkeypatch.setattr(get_settings(), "supabase_jwt_secret", "")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {_token('y@example.com')}"}).status_code == 401
