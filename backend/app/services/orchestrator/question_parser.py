"""Step Q (part 1): question -> QuestionSpec.

Pehle deterministic rule parser (sasta, reproducible, LLM ke bina chalta hai); metric ya month na mile to
LLM fallback (JSON) + semantic layer validation. LLM kabhi formula nahi likhta — sirf metric NAAM chunta hai.
"""
import json
import re
from datetime import date

from app.schemas.qtrace import QuestionSpec
from app.services.llm.prompt_builder import decompose_prompt
from app.services.rag.semantic_layer import SemanticLayer, shift_period


class QuestionParseError(ValueError):
    pass


MONTHS = {
    "jan": 1, "january": 1, "janvari": 1, "january's": 1,
    "feb": 2, "february": 2, "febuary": 2, "farvari": 2, "farvary": 2,
    "mar": 3, "march": 3, "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10, "october": 10,
    "nov": 11, "november": 11, "dec": 12, "december": 12,
}
METRIC_PATTERNS = [
    ("aov", (r"\baov\b", r"average order value", r"avg\.? order value", r"basket size")),
    ("cancel_rate", (r"cancel",)),
    ("revenue", (r"revenue", r"\bsales?\b", r"\bgmv\b", r"kamai", r"bikri", r"income")),
    ("orders", (r"\borders?\b", r"order count")),
]
_ROOT = re.compile(r"\b(kyun|kyon|kyu|kiu|why|reason|wajah|cause)\b", re.I)
_COMPARE = re.compile(r"\b(vs|versus|compare)\b", re.I)
_TREND = re.compile(r"\btrend\b", re.I)
_TOKEN = re.compile(r"[a-z']+|\d{4}")


def find_metric(question: str, available: list[str]) -> str | None:
    q = question.lower()
    for name, patterns in METRIC_PATTERNS:
        if name in available and any(re.search(p, q) for p in patterns):
            return name
    return None


def find_periods(question: str, latest: date | None = None) -> list[str]:
    tokens = _TOKEN.findall(question.lower())
    found: list[list] = []
    for i, t in enumerate(tokens):
        if t in MONTHS:
            year = next((int(x) for x in tokens[i + 1:i + 3] if x.isdigit()), None)
            found.append([MONTHS[t], year])
    years = sorted({int(t) for t in tokens if t.isdigit()})
    ref = latest or date.today()
    for f in found:
        if f[1] is None and len(years) == 1:
            f[1] = years[0]
        if f[1] is None:   # saal nahi diya: data me sabse recent aisa mahina
            f[1] = ref.year if f[0] <= ref.month else ref.year - 1
    return sorted({f"{y:04d}-{m:02d}" for m, y in found})


def find_filters(question: str, values: dict[str, list[str]]) -> dict[str, str]:
    q = question.lower()
    out: dict[str, str] = {}
    for dim, vals in values.items():
        for v in sorted(vals, key=len, reverse=True):
            if v and re.search(rf"(?<![a-z0-9]){re.escape(v.lower())}(?![a-z0-9])", q):
                out[dim] = v
                break
    return out


def intent_of(question: str) -> str:
    if _ROOT.search(question):
        return "root_cause"
    if _COMPARE.search(question):
        return "compare"
    if _TREND.search(question):
        return "trend"
    return "lookup"


def parse_rules(question: str, layer: SemanticLayer, values: dict[str, list[str]],
                latest: date | None = None) -> QuestionSpec:
    metric = find_metric(question, layer.names())
    periods = find_periods(question, latest)
    if metric is None or not periods:
        missing = [n for n, ok in (("metric", metric), ("month", periods)) if not ok]
        raise QuestionParseError(f"question se {' aur '.join(missing)} samajh nahi aaya")
    dims = layer.get(metric).dimensions
    filters = {k: v for k, v in find_filters(question, values).items() if k in dims}
    current = periods[-1]
    base = periods[-2] if len(periods) >= 2 else shift_period(current, -1)
    return QuestionSpec(metric=metric, filters=filters, period_current=current, period_base=base,
                        period_yoy=shift_period(current, -12), intent=intent_of(question))


def parse_llm(question: str, layer: SemanticLayer, llm) -> QuestionSpec:
    dims = sorted({d for m in layer.metrics() for d in m.dimensions})
    resp = llm.complete(decompose_prompt(question, layer.names(), dims))
    match = re.search(r"\{.*\}", resp.text, re.S)
    if not match:
        raise QuestionParseError("LLM ne JSON nahi diya")
    data = json.loads(match.group(0))
    metric = data.get("metric")
    if metric not in layer.names():
        raise QuestionParseError(f"unknown metric from LLM: {metric!r}")
    allowed = layer.get(metric).dimensions
    filters = {k: str(v) for k, v in (data.get("filters") or {}).items() if k in allowed}
    for key in ("period_current", "period_base"):
        if not re.fullmatch(r"\d{4}-\d{2}", str(data.get(key, ""))):
            raise QuestionParseError(f"invalid {key} from LLM")
    return QuestionSpec(metric=metric, filters=filters, period_current=data["period_current"],
                        period_base=data["period_base"], period_yoy=shift_period(data["period_current"], -12),
                        intent=data.get("intent") if data.get("intent") in ("lookup", "compare", "trend",
                                                                             "root_cause") else "root_cause")


def parse_question(question: str, layer: SemanticLayer, values: dict[str, list[str]], latest: date | None = None,
                   llm=None) -> tuple[QuestionSpec, str, object | None]:
    """Returns (spec, source, llm_response)."""
    try:
        return parse_rules(question, layer, values, latest), "rules", None
    except QuestionParseError:
        if llm is None:
            raise
    spec = parse_llm(question, layer, llm)
    return spec, "llm", None
