"""Deploy-friendly env parsing (Render / Supabase)."""
from app.core.config import Settings


def test_postgres_urls_use_psycopg_driver():
    s = Settings(database_url="postgresql://u:p@host:5432/db", readonly_database_url="postgres://ro:p@host/db")
    assert s.database_url == "postgresql+psycopg://u:p@host:5432/db"
    assert s.readonly_database_url == "postgresql+psycopg://ro:p@host/db"
    assert Settings(database_url="sqlite:///./x.db").database_url == "sqlite:///./x.db"


def test_cors_origins_comma_or_json(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://web.onrender.com/, http://localhost:5173")
    assert Settings().cors_origins == ["https://web.onrender.com", "http://localhost:5173"]
    monkeypatch.setenv("CORS_ORIGINS", '["https://a.example"]')
    assert Settings().cors_origins == ["https://a.example"]


def test_admin_emails_and_default_signup_role(monkeypatch):
    from app.core.config import get_settings
    from app.core.security import initial_role

    monkeypatch.setenv("ADMIN_EMAILS", "Boss@Example.com, ops@example.com")
    monkeypatch.setenv("DEFAULT_SIGNUP_ROLE", "viewer")
    get_settings.cache_clear()
    try:
        assert get_settings().admin_emails == ["boss@example.com", "ops@example.com"]
        assert initial_role("boss@example.com", has_other_users=True) == "admin"
        # list set ho to "pehla signup admin" band — public deploy par koi bhi admin nahi ban sakta
        assert initial_role("stranger@example.com", has_other_users=False) == "viewer"
    finally:
        get_settings.cache_clear()
    monkeypatch.delenv("ADMIN_EMAILS")
    monkeypatch.delenv("DEFAULT_SIGNUP_ROLE")
    get_settings.cache_clear()
    assert initial_role("first@example.com", has_other_users=False) == "admin"     # purana rule (local dev)
    assert initial_role("second@example.com", has_other_users=True) == "analyst"
