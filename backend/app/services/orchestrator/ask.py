"""ASK / ANALYZE pipeline (Ch 5, left branch):

question -> schema snapshot (role-filtered) -> retrieve tables -> LLM SQL -> 4-layer firewall
-> read-only execute (error par 1 repair) -> 1-line answer (numeric grounding check, warna template).
"""
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.services.evidence.grounding_validator import numbers_in, numeric_grounding_ok
from app.services.llm.llm_client import LLMError, LLMResponse
from app.services.llm.prompt_builder import answer_prompt, guess_mode, repair_prompt, sql_prompt
from app.services.llm.sql_generator import extract_sql
from app.services.query_executor.executor import ExecutionResult, run_sql, sql_dialect
from app.services.rag.retriever import retrieve
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


# ------------------------------------------------------------------ pipeline
def run_ask(question: str, role: str, llm, engine: Engine, mode: str, sql: str | None = None,
            layer: SemanticLayer | None = None) -> AskResult:
    settings = get_settings()
    layer = layer or SemanticLayer()
    dialect = sql_dialect(engine)
    calls: list[LLMCallLog] = []
    tables = schema_snapshot(engine, role)
    sensitive = sensitive_tables(tables)

    def guard(candidate: str) -> str:
        return firewall_check(candidate, role=role, dialect=dialect, engine=engine, sensitive_tables=sensitive)

    if sql is not None:                                  # manual SQL (Monaco) — LLM skip
        try:
            safe = guard(sql)
        except UnsafeSQL as e:
            raise AskError("blocked", str(e), sql, calls) from e
        try:
            result = run_sql(safe, engine)
        except SQLAlchemyError as e:
            raise AskError("error", _db_error(e), safe, calls) from e
        answer, source = template_answer(result), "template"
        return AskResult(mode, safe, result, answer, source, generated=False, attempts=0, llm_calls=calls)

    docs = {t.name: table_doc(t) for t in tables}
    if not docs:
        raise AskError("error", "Is datasource me aapke role ke liye koi table available nahi hai.", None, calls)
    base = sql_prompt(question, [docs[n] for n in retrieve(question, docs)], metric_docs(layer), dialect, mode,
                      date.today().isoformat())
    prompt, attempts = base, 0
    while True:
        attempts += 1
        resp = llm.complete(prompt)                      # LLMError caller handle karta hai
        calls.append(("ask_sql" if attempts == 1 else "ask_sql_repair", prompt, resp))
        candidate = extract_sql(resp.text)
        try:
            safe = guard(candidate)
            result = run_sql(safe, engine)
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

    answer, source = summarize(question, safe, result, llm if settings.llm_answer else None, calls)
    return AskResult(mode, safe, result, answer, source, generated=True, attempts=attempts, llm_calls=calls)
