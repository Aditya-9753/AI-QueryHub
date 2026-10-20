"""F33: numeric grounding — narrative ka har number kisi evidence value se match hona chahiye (Ch 13.7)."""
import re

NUM = re.compile(r"-?\d+(?:,\d{2,3})*(?:\.\d+)?")


def numbers_in(text: str) -> list[float]:
    return [float(n.replace(",", "")) for n in NUM.findall(text)]


def candidate_values(evidence_values: list[float]) -> list[float]:
    candidates = []
    for v in evidence_values:
        candidates += [v, v * 100, abs(v), abs(v) * 100]
    return candidates


def is_grounded(n: float, candidates: list[float], rel_tol: float = 0.005, abs_tol: float = 0.05) -> bool:
    return any(abs(n - c) <= max(abs_tol, rel_tol * abs(c)) for c in candidates)


def numeric_grounding_ok(narrative: str, evidence_values: list[float],
                         rel_tol: float = 0.005, abs_tol: float = 0.05):
    """Every number in the LLM narrative must match some evidence value
    (also checks value x100 for percentages). Returns (ok, bad_numbers)."""
    candidates = candidate_values(evidence_values)
    bad = [n for n in numbers_in(narrative) if not is_grounded(n, candidates, rel_tol, abs_tol)]
    return len(bad) == 0, bad


def strip_ungrounded(sentence: str, evidence_values: list[float], placeholder: str = "[see evidence table]") -> str:
    candidates = candidate_values(evidence_values)

    def repl(m: re.Match) -> str:
        return m.group(0) if is_grounded(float(m.group(0).replace(",", "")), candidates) else placeholder

    return NUM.sub(repl, sentence)
