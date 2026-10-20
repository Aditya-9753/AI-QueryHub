"""Tests ek temp SQLite DB use karte hain (app import se PEHLE env set hona zaroori hai)."""
import os
import tempfile

import pytest

_DB = os.path.join(tempfile.gettempdir(), "queryhub_pytest.db")
if os.path.exists(_DB):
    os.remove(_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ["READONLY_DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ["AUTH_DISABLED"] = "true"
os.environ["AUTO_MIGRATE"] = "true"
# Tests hermetic rahein: backend/.env ki asli LLM keys / Sentry use nahi hongi (env vars .env ko override karte hain)
os.environ["GROQ_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""
os.environ["OLLAMA_URL"] = "http://127.0.0.1:9"     # band port -> turant connection refused
os.environ["SENTRY_DSN"] = ""
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_JWT_SECRET"] = ""
TEST_DB_URL = f"sqlite:///{_DB}"

DEMO_DDL = [
    "DROP TABLE IF EXISTS orders",
    "DROP TABLE IF EXISTS customers",
    "CREATE TABLE orders (order_id INTEGER PRIMARY KEY, city TEXT, category TEXT, channel TEXT, "
    "amount NUMERIC, status TEXT, created_at TIMESTAMP)",
    "INSERT INTO orders (city, category, channel, amount, status, created_at) VALUES "
    "('Delhi','Electronics','app',100,'placed','2026-02-01 10:00:00'),"
    "('Delhi','Grocery','web',50,'placed','2026-02-02 11:00:00'),"
    "('Pune','Fashion','app',70,'cancelled','2026-02-03 12:00:00')",
    "CREATE TABLE customers (id INTEGER PRIMARY KEY, city TEXT, email TEXT, phone TEXT)",
    "INSERT INTO customers (city, email, phone) VALUES ('Delhi','a@x.com','999')",
]


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from sqlalchemy import text

    from app.db.session import engine
    from app.main import app
    from app.services.rag.schema_context import clear_cache

    with engine.begin() as conn:
        for stmt in DEMO_DDL:
            conn.execute(text(stmt))
    clear_cache()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def fake_llm():
    """`fake_llm(["```sql ...```", "answer"])` -> FakeLLM installed as get_llm override."""
    from app.main import app
    from app.services.llm.fallback import get_llm
    from tests.fakes import FakeLLM

    installed = []

    def install(replies):
        llm = FakeLLM(replies)
        app.dependency_overrides[get_llm] = lambda: llm
        installed.append(llm)
        return llm

    yield install
    app.dependency_overrides.pop(get_llm, None)
