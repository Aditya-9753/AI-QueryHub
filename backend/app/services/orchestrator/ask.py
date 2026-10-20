"""ASK / ANALYZE pipeline (Ch 5, left branch):

question -> schema snapshot (role-filtered) -> retrieve tables -> LLM SQL -> 4-layer firewall
-> read-only execute (error par 1 repair) -> 1-line answer (numeric grounding check, warna template).
"""
import re
import time
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlglot import exp, parse_one

from app.core.config import get_settings
from app.services.evidence.grounding_validator import numbers_in, numeric_grounding_ok
from app.services.llm.llm_client import LLMError, LLMResponse
from app.services.llm.prompt_builder import answer_prompt, guess_mode, repair_prompt, sql_prompt
from app.services.llm.sql_generator import extract_sql
from app.services.query_executor.executor import ExecutionResult, run_sql, sql_dialect
from app.services.rag.retriever import SMALL_SCHEMA, retrieve
from app.services.rag.schema_context import schema_snapshot, sensitive_tables, table_doc
from app.services.rag.semantic_layer import SemanticLayer
from app.services.sql_validator.firewall import firewall_check
from app.services.sql_validator.safety_rules import UnsafeSQL

LLMCallLog = tuple[str, str, LLMResponse]          # (step, prompt, response)


class AskError(Exception):
    def __init__(self, status: str, message: str, sql: str | None, llm_calls: list[LLMCallLog]) -> None:
        super().__init__(message)
        self.status, self.message, self.sql, self.llm_calls = status, message, sql, llm_calls


@dataclass
class AskResult:
    mode: str
    sql: str
    result: ExecutionResult
    answer: str
    answer_source: str
    generated: bool
    attempts: int
    llm_calls: list[LLMCallLog] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)            # pipeline stages + timings (UI execution trace)
    dimension_values: dict[str, list[str]] = field(default_factory=dict)   # follow-up suggestions ke liye


def resolve_mode(question: str, mode: str | None) -> tuple[str, list[str]]:
    if mode:
        return mode, []
    guessed = guess_mode(question)
    if guessed == "INVESTIGATE":
        return "ANALYZE", ["Ye 'kyun?' wala sawaal lagta hai — root cause ke liye Investigation workspace use karo. "
                           "Abhi ANALYZE mode me breakdown diya hai."]
    return guessed, []


def metric_docs(layer: SemanticLayer) -> list[str]:
    return [f"{m.name}: {m.definition}. SQL: {m.expression} FROM {m.table}"
            + (f" WHERE {m.base_filter}" if m.base_filter else "") + f" (time column: {m.time_column})"
            for m in layer.metrics()]


def _db_error(e: SQLAlchemyError) -> str:
    return f"{e.__class__.__name__}: {str(getattr(e, 'orig', e)).splitlines()[0][:300]}"


def _is_parse_error(e: UnsafeSQL) -> bool:
    return str(e).startswith("could not parse")


# ------------------------------------------------------------------ answer
def _fmt(v) -> str:
    if isinstance(v, bool) or v is None:
        return str(v)
    if isinstance(v, float):
        return f"{v:,.2f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


def template_answer(result: ExecutionResult) -> str:
    if result.row_count == 0:
        return "Koi result nahi mila."
    first = ", ".join(f"{c}: {_fmt(v)}" for c, v in zip(result.columns, result.rows[0]))
    if result.row_count == 1:
        return first
    return f"{result.row_count} rows mili. Pehli row — {first}"


def evidence_values(question: str, sql: str, result: ExecutionResult) -> list[float]:
    """Answer ke numbers in values (ya inke lakh/crore/thousand scale) se match hone chahiye."""
    vals: list[float] = [float(result.row_count)]
    for row in result.rows[:50]:
        for v in row:
            if isinstance(v, bool) or v is None:
                continue
            if isinstance(v, (int, float)):
                vals += [v, v / 1e3, v / 1e5, v / 1e6, v / 1e7, v / 1e9]
            else:
                vals += numbers_in(str(v))
    return vals + numbers_in(question) + numbers_in(sql)


def summarize(question: str, sql: str, result: ExecutionResult, llm, calls: list[LLMCallLog]) -> tuple[str, str]:
    if llm is not None and result.row_count > 0:
        prompt = answer_prompt(question, result.columns, result.rows[:20])
        try:
            resp = llm.complete(prompt)
            calls.append(("ask_answer", prompt, resp))
            text = resp.text.strip().strip('"').strip()
            ok, _ = numeric_grounding_ok(text, evidence_values(question, sql, result))
            if text and ok and len(text) <= 500:
                return text, "llm"
        except LLMError:
            pass
    return template_answer(result), "template"


# ------------------------------------------------------------------ trace
def _ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000, 1)


def tables_in(sql: str, dialect: str) -> list[str]:
    try:
        return sorted({t.name for t in parse_one(sql, read=dialect).find_all(exp.Table)})
    except Exception:
        return []


def firewall_stage(candidate: str, safe: str, role: str, dialect: str, ms: float) -> dict:
    used = tables_in(safe, dialect)
    limit_added = re.search(r"\blimit\b", candidate, re.I) is None
    return {"key": "firewall", "label": "SQL firewall", "ms": ms, "tables": used, "layers": [
        {"name": "Read-only connection", "detail": "PRAGMA query_only" if dialect == "sqlite"
         else "queryhub_ro role · read-only transaction"},
        {"name": "AST rules", "detail": "single SELECT · no DML/DDL · function blacklist"},
        {"name": "RBAC policy", "detail": f"role {role} · tables {', '.join(used) or '-'}"},
        {"name": "Cost guard", "detail": (f"LIMIT {get_settings().max_rows} injected" if limit_added else "LIMIT present")
         + " · EXPLAIN cost ok"},
    ]}


def access_warnings(question: str, engine: Engine, role: str, tables) -> list[str]:
    """Sawaal me role ke liye chhupi table ya sensitive column ka naam ho to user ko saaf batao (chup-chaap
    NULL / doosra column dikhane ke bajay)."""
    words = set(re.findall(r"[a-z_]+", question.lower()))
    visible = {t.name for t in tables}
    hidden = [t.name for t in schema_snapshot(engine, "admin")
              if t.name not in visible and (t.name in words or t.name.rstrip("s") in words)]
    sensitive = sorted({c.name for t in tables for c in t.columns if c.sensitive and c.name.lower() in words})
    out = []
    if hidden:
        out.append(f"'{', '.join(hidden)}' table aapke role ({role}) ke liye available nahi — "
                   "jawab sirf allowed tables se bana hai.")
    if sensitive:
        out.append(f"{', '.join(sensitive)} sensitive column hai — aapke role ({role}) ke liye hidden rehta hai "
                   "(admin dekh sakta hai).")
    return out


def dimension_values_for(tables, used: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for t in tables:
        if t.name in used:
            for c in t.columns:
                if c.values and not c.sensitive and len(c.values) <= 30:
                    out.setdefault(c.name, c.values)
    return out


# ------------------------------------------------------------------ pipeline
def run_ask(question: str, role: str, llm, engine: Engine, mode: str, sql: str | None = None,
            layer: SemanticLayer | None = None) -> AskResult:
    settings = get_settings()
    layer = layer or SemanticLayer()
    dialect = sql_dialect(engine)
    calls: list[LLMCallLog] = []
    trace: list[dict] = []
    t = time.perf_counter()
    tables = schema_snapshot(engine, role)
    sensitive = sensitive_tables(tables)

    def guard(candidate: str) -> str:
        return firewall_check(candidate, role=role, dialect=dialect, engine=engine, sensitive_tables=sensitive)

    if sql is not None:                                  # manual SQL (Monaco) — LLM skip
        t = time.perf_counter()
        try:
            safe = guard(sql)
        except UnsafeSQL as e:
            raise AskError("blocked", str(e), sql, calls) from e
        trace.append(firewall_stage(sql, safe, role, dialect, _ms(t)))
        t = time.perf_counter()
        try:
            result = run_sql(safe, engine)
        except SQLAlchemyError as e:
            raise AskError("error", _db_error(e), safe, calls) from e
        trace.append({"key": "execute", "label": "Read-only execution", "ms": _ms(t), "rows": result.row_count,
                      "checksum": result.checksum[:16], "dialect": dialect})
        answer, source = template_answer(result), "template"
        trace.append({"key": "answer", "label": "Answer", "ms": 0.0, "source": source,
                      "numbers": len(numbers_in(answer))})
        return AskResult(mode, safe, result, answer, source, generated=False, attempts=0, llm_calls=calls,
                         trace=trace, dimension_values=dimension_values_for(tables, tables_in(safe, dialect)))

    docs = {t.name: table_doc(t) for t in tables}
    if not docs:
        raise AskError("error", "Is datasource me aapke role ke liye koi table available nahi hai.", None, calls)
    chosen = retrieve(question, docs)
    metrics = metric_docs(layer)
    base = sql_prompt(question, [docs[n] for n in chosen], metrics, dialect, mode, date.today().isoformat())
    trace.append({"key": "context", "label": "Schema + semantic context", "ms": _ms(t), "tables_visible": len(docs),
                  "retrieved": chosen, "metrics": len(metrics),
                  "rag": "all tables (small schema)" if len(docs) <= SMALL_SCHEMA else settings.schema_rag})
    prompt, attempts = base, 0
    llm_ms = 0.0
    while True:
        attempts += 1
        t = time.perf_counter()
        resp = llm.complete(prompt)                      # LLMError caller handle karta hai
        llm_ms += _ms(t)
        calls.append(("ask_sql" if attempts == 1 else "ask_sql_repair", prompt, resp))
        candidate = extract_sql(resp.text)
        try:
            t = time.perf_counter()
            safe = guard(candidate)
            fw_ms = _ms(t)
            t = time.perf_counter()
            result = run_sql(safe, engine)
            exec_ms = _ms(t)
            break
        except UnsafeSQL as e:
            # safety block par retry nahi (LLM ko firewall "bypass" karna sikhana nahi) — sirf syntax galti par
            if not _is_parse_error(e) or attempts > settings.ask_max_retries:
                raise AskError("blocked" if not _is_parse_error(e) else "error", str(e), candidate, calls) from e
            prompt = repair_prompt(base, candidate, str(e))
        except SQLAlchemyError as e:
            if attempts > settings.ask_max_retries:
                raise AskError("error", _db_error(e), safe, calls) from e
            prompt = repair_prompt(base, safe, _db_error(e))

    sql_calls = [c[2] for c in calls]
    trace.append({"key": "llm_sql", "label": "LLM → SQL", "ms": llm_ms, "model": sql_calls[-1].model,
                  "attempts": attempts, "tokens_in": sum(r.tokens_in or 0 for r in sql_calls),
                  "tokens_out": sum(r.tokens_out or 0 for r in sql_calls)})
    trace.append(firewall_stage(candidate, safe, role, dialect, fw_ms))
    trace.append({"key": "execute", "label": "Read-only execution", "ms": exec_ms, "rows": result.row_count,
                  "checksum": result.checksum[:16], "dialect": dialect})
    t = time.perf_counter()
    answer, source = summarize(question, safe, result, llm if settings.llm_answer else None, calls)
    trace.append({"key": "answer", "label": "Grounded answer", "ms": _ms(t), "source": source,
                  "numbers": len(numbers_in(answer))})
    return AskResult(mode, safe, result, answer, source, generated=True, attempts=attempts, llm_calls=calls,
                     trace=trace, dimension_values=dimension_values_for(tables, tables_in(safe, dialect)),
                     warnings=access_warnings(question, engine, role, tables))
