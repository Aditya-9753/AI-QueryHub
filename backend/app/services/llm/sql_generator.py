"""LLM response -> SQL text. Validation firewall ka kaam hai, yahan sirf extraction."""
import re

_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.S | re.I)
_START = re.compile(r"\b(WITH|SELECT)\b", re.I)


def extract_sql(text: str) -> str:
    m = _FENCE.search(text)
    sql = m.group(1) if m else text
    if not m:
        start = _START.search(sql)
        if start:
            sql = sql[start.start():]
    return sql.strip().rstrip(";").strip()
