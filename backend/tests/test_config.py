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
