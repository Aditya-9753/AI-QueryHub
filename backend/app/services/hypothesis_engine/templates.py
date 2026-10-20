"""Fixed template hypotheses (Ch 8.4): seasonality, calendar, data issue, price change, concurrent event."""
from app.schemas.qtrace import Hypothesis, QuestionSpec

PRIOR = 0.4

TEMPLATES = [
    {"key": "seasonality", "statement": "Seasonal pattern: pichhle saal bhi same period me aisa hua tha",
     "test_type": "yoy", "covers": None},
    {"key": "calendar", "statement": "Calendar effect: periods ke din alag hain",
     "test_type": "log_decomp", "covers": "days"},
    {"key": "data_issue", "statement": "Data issue: missing days / duplicates / late data",
     "test_type": "data_health", "covers": None},
    {"key": "price_change", "statement": "Price change: same items ki price badli",
     "test_type": "mix_rate", "covers": "segment_aov"},
    {"key": "concurrent_event", "statement": "Concurrent event: controls me bhi same change (market-wide)",
     "test_type": "did", "covers": None},
]


def template_hypotheses(spec: QuestionSpec, skip_covered: set[str] = frozenset(),
                        skip: set[str] = frozenset()) -> list[Hypothesis]:
    """skip_covered: metric tree ke keys — duplicates (calendar vs 'days', price vs rate) skip hote hain."""
    out = []
    for t in TEMPLATES:
        if t["key"] in skip or (t["covers"] and t["covers"] in skip_covered):
            continue
        out.append(Hypothesis(id=f"tpl.{t['key']}", statement=t["statement"], metric=spec.metric,
                              source="template", prior=PRIOR, test_type=t["test_type"]))
    return out
