from app.services.llm.prompt_builder import guess_mode
from app.services.llm.sql_generator import extract_sql
from app.services.orchestrator.ask import resolve_mode


def test_extract_sql():
    assert extract_sql("```sql\nSELECT 1;\n```") == "SELECT 1"
    assert extract_sql("Here you go:\n```\nWITH t AS (SELECT 1) SELECT * FROM t\n```") == "WITH t AS (SELECT 1) SELECT * FROM t"
    assert extract_sql("Sure! SELECT city FROM orders;") == "SELECT city FROM orders"
    assert extract_sql("DELETE FROM orders") == "DELETE FROM orders"         # firewall pakdega


def test_mode_router():
    assert guess_mode("February mein Delhi ka revenue kitna tha?") == "ASK"
    assert guess_mode("Delhi revenue category-wise, Jan vs Feb") == "ANALYZE"
    assert guess_mode("Feb me Delhi revenue kyun gira?") == "INVESTIGATE"
    assert resolve_mode("kyun gira?", None)[0] == "ANALYZE"
    assert resolve_mode("anything", "ASK") == ("ASK", [])
