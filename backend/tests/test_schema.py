import os

from sqlalchemy import create_engine

from app.services.rag.schema_context import schema_snapshot, sensitive_tables, table_doc
from tests.conftest import TEST_DB_URL


def test_schema_endpoint_hides_app_tables(client):
    body = client.get("/api/schema").json()
    names = {t["name"] for t in body["tables"]}
    assert {"orders", "customers"} <= names
    assert not names & {"users", "experiments", "audit_log", "alembic_version", "query_history"}
    orders = next(t for t in body["tables"] if t["name"] == "orders")
    city = next(c for c in orders["columns"] if c["name"] == "city")
    created = next(c for c in orders["columns"] if c["name"] == "created_at")
    assert city["values"] == ["Delhi", "Pune"]
    assert created["min"].startswith("2026-02-01") and created["max"].startswith("2026-02-03")


def test_snapshot_role_filtering(client):
    engine = create_engine(TEST_DB_URL)
    analyst = {t.name: t for t in schema_snapshot(engine, "analyst", refresh=True)}
    email = next(c for c in analyst["customers"].columns if c.name == "email")
    assert email.sensitive and email.values == []
    assert "email" not in table_doc(analyst["customers"])
    assert sensitive_tables(list(analyst.values())) == {"customers": {"email", "phone"}}
    assert set(t.name for t in schema_snapshot(engine, "viewer")) == {"orders"}


def test_datasources(client):
    listed = client.get("/api/datasources").json()
    assert listed[0]["id"] == "default" and listed[0]["is_default"]
    assert client.post("/api/datasources/default/test").json()["ok"] is True

    bad = client.post("/api/datasources", json={"name": "x", "kind": "postgres", "conn_secret_ref": "JWT_SECRET"})
    assert bad.status_code == 400
    lower = client.post("/api/datasources", json={"name": "x", "kind": "sqlite", "conn_secret_ref": "postgres://u:p@h"})
    assert lower.status_code == 422                              # URL/password field me allowed hi nahi

    ds = client.post("/api/datasources", json={"name": "Copy", "kind": "sqlite", "conn_secret_ref": "DS_TEST_COPY"}).json()
    missing = client.post(f"/api/datasources/{ds['id']}/test").json()
    assert missing["ok"] is False and "DS_TEST_COPY" in missing["error"]

    os.environ["DS_TEST_COPY"] = TEST_DB_URL
    try:
        assert client.post(f"/api/datasources/{ds['id']}/test").json()["ok"] is True
        assert {t["name"] for t in client.get("/api/schema", params={"datasource_id": ds["id"]}).json()["tables"]} >= {"orders"}
    finally:
        del os.environ["DS_TEST_COPY"]
    assert client.delete(f"/api/datasources/{ds['id']}").status_code == 204
