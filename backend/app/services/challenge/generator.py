"""User ka custom challenge ("Challenge This Finding") -> LLM counter-hypotheses (JSON).
Fixed battery (battery.py) self-confirmation bias kam karti hai; LLM sirf custom challenges ke liye, aur uske
ideas semantic layer se ground hokar deterministic test se hi judge hote hain."""
import json
import re

from app.schemas.qtrace import Hypothesis


def custom_challenge_prompt(finding_statement: str, user_text: str, metric: str, dimensions: list[str]) -> str:
    return ("Propose up to 3 counter-hypotheses (alternative explanations) for the finding, each testable as a "
            "segment breakdown on ONE allowed dimension. Return JSON list of {\"id\", \"statement\", \"dimensions\"}.\n"
            f"Metric: <data>{metric}</data>\nAllowed dimensions: <data>{json.dumps(dimensions)}</data>\n"
            f"Finding: <data>{json.dumps(finding_statement)}</data>\nUser challenge: <data>{json.dumps(user_text)}</data>")


def counter_hypotheses(finding_statement: str, user_text: str, metric: str, dimensions: list[str],
                       llm) -> list[Hypothesis]:
    resp = llm.complete(custom_challenge_prompt(finding_statement, user_text, metric, dimensions))
    m = re.search(r"\[.*\]", resp.text, re.S)
    try:
        raw = json.loads(m.group(0)) if m else []
    except json.JSONDecodeError:
        return []
    out = []
    for r in raw[:3] if isinstance(raw, list) else []:
        try:
            slug = re.sub(r"[^a-z0-9_]", "_", str(r.get("id", "counter")).lower())[:40]
            out.append(Hypothesis(id=f"llm.challenge.{slug}", statement=str(r["statement"])[:300], metric=metric,
                                  dimensions=[d for d in r.get("dimensions", []) if d in dimensions][:1],
                                  source="llm", prior=0.3, test_type="corr"))
        except (KeyError, TypeError):
            continue
    return out
