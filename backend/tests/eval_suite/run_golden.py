"""SQL Execution Accuracy on golden questions (Ch 18 / Ch 19 Phase 1 "ASK mode 20 sawaalon par").

Zaroorat: seeded demo DB (`python ../database/seed_data/seed_demo.py`) + LLM key (.env).
    cd backend && python -m tests.eval_suite.run_golden [--role analyst] [--only G01,G02]

Match rule ("subset"): har expected row ke saare values predicted row me hone chahiye (extra columns OK),
row count same; numbers 2 decimal tak round.
"""
import argparse
import json
import time
from pathlib import Path

from app.db.session import readonly_engine
from app.services.llm.fallback import get_llm
from app.services.llm.llm_client import LLMError
from app.services.orchestrator.ask import AskError, run_ask
from app.services.query_executor.executor import run_sql

HERE = Path(__file__).parent


def _canon(v) -> str:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return f"{round(float(v), 2):.2f}"
    return str(v)


def rows_match(expected: list[list], predicted: list[list]) -> bool:
    if len(expected) != len(predicted):
        return False
    pred = [sorted(_canon(v) for v in r) for r in predicted]
    for er in sorted(expected, key=lambda r: [_canon(v) for v in r]):
        need = [_canon(v) for v in er]
        hit = next((i for i, pr in enumerate(pred) if all(need.count(x) <= pr.count(x) for x in need)), None)
        if hit is None:
            return False
        pred.pop(hit)
    return True


def tables_of(sql: str) -> set[str]:
    import sqlglot
    from sqlglot import exp

    try:
        return {t.name.lower() for t in sqlglot.parse_one(sql, read="sqlite").find_all(exp.Table)}
    except Exception:  # noqa: BLE001
        return set()


def _rate(xs: list) -> float | None:
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", default="analyst")
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    questions = json.loads((HERE / "golden_questions" / "questions.json").read_text(encoding="utf-8"))
    if args.only:
        keep = set(args.only.split(","))
        questions = [q for q in questions if q["id"] in keep]

    llm, results = get_llm(), []
    for q in questions:
        t0 = time.perf_counter()
        rec = {"id": q["id"], "question": q["question"]}
        try:
            res = run_ask(q["question"], args.role, llm, engine=readonly_engine, mode=q["mode"])
            rec["sql"] = res.sql
            if q.get("expected_blocked"):
                rec["status"] = "FAIL (not blocked)"
            else:
                expected = run_sql(q["expected_sql"]).all_rows
                rec["status"] = "PASS" if rows_match(expected, res.result.all_rows) else "FAIL"
                # Ch 18 Schema Grounding: sahi tables chuni? (expected SQL ki tables == generated SQL ki tables)
                rec["schema_grounded"] = tables_of(q["expected_sql"]) == tables_of(res.sql)
                rec["mode_ok"] = res.mode == q["mode"]   # Intent alignment proxy: ASK vs ANALYZE sahi pehchana
        except AskError as e:
            rec["sql"], rec["error"] = e.sql, e.message
            # unsafe sawaal: firewall ne block kiya ya LLM ne valid SELECT hi nahi diya — dono me kuch execute nahi hua
            rec["status"] = "PASS" if q.get("expected_blocked") else f"FAIL ({e.status})"
        except LLMError as e:
            rec["status"], rec["error"] = "LLM_ERROR", str(e)[:200]
        rec["seconds"] = round(time.perf_counter() - t0, 2)
        results.append(rec)
        print(f"{rec['id']}  {rec['status']:<20} {rec['seconds']:>5}s  {q['question']}")
        if not rec["status"].startswith("PASS") and rec.get("sql"):
            print(f"      sql: {rec['sql']}")

    passed = sum(r["status"] == "PASS" for r in results)
    print(f"\nSQL Execution Accuracy: {passed}/{len(results)} = {passed / max(len(results), 1):.0%}")
    by_mode = {}
    for q, r in zip(questions, results):
        key = "BLOCKED" if q.get("expected_blocked") else q["mode"]
        by_mode.setdefault(key, [0, 0])
        by_mode[key][0] += r["status"] == "PASS"
        by_mode[key][1] += 1
    summary = {"total": len(results), "passed": passed, "accuracy": passed / max(len(results), 1),
               "by_mode": {k: {"passed": v[0], "total": v[1]} for k, v in by_mode.items()},
               "llm_errors": sum(r["status"] == "LLM_ERROR" for r in results),
               "schema_grounding": _rate([r.get("schema_grounded") for r in results]),
               "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    payload = json.dumps({"summary": summary, "questions": results}, indent=2)
    (out / f"golden_{time.strftime('%Y%m%d_%H%M%S')}.json").write_text(payload, encoding="utf-8")
    if not args.only:
        (out / "golden_latest.json").write_text(payload, encoding="utf-8")


if __name__ == "__main__":
    main()
