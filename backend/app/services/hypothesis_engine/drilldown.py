"""F29: explanatory power (EP) + Jensen-Shannon surprise — drill-down dimension choice (Adtributor idea)."""
import math

from app.schemas.qtrace import Hypothesis

PRIOR = 0.4


def explanatory_power(segment_deltas: dict[str, float], total_delta: float, top_k: int = 3) -> tuple[float, list[str]]:
    """Top-k segments (total ki direction me sabse zyada contribute karne wale) ka EP = sum(dR_i)/dR."""
    if total_delta == 0:
        return 0.0, []
    ranked = sorted(segment_deltas, key=lambda s: segment_deltas[s] / total_delta, reverse=True)[:top_k]
    return sum(segment_deltas[s] for s in ranked) / total_delta, ranked


def _normalize(d: dict[str, float], keys: list[str]) -> list[float]:
    total = sum(max(d.get(k, 0.0), 0.0) for k in keys)
    return [max(d.get(k, 0.0), 0.0) / total if total else 0.0 for k in keys]


def _kl(p: list[float], q: list[float]) -> float:
    return sum(pi * math.log(pi / qi) for pi, qi in zip(p, q) if pi > 0 and qi > 0)


def js_divergence(p: list[float], q: list[float]) -> float:
    """JS(P||Q) = 1/2 KL(P||M) + 1/2 KL(Q||M), M = (P+Q)/2. Natural log, range [0, ln 2]."""
    m = [(a + b) / 2 for a, b in zip(p, q)]
    return 0.5 * _kl(p, m) + 0.5 * _kl(q, m)


def surprise(base: dict[str, float], current: dict[str, float]) -> float:
    keys = sorted(set(base) | set(current))
    return js_divergence(_normalize(current, keys), _normalize(base, keys))


def rank_dimensions(dims: dict[str, tuple[dict[str, float], dict[str, float]]],
                    top_k: int = 3, target_ep: float = 0.8) -> list[dict]:
    """dims: {dimension: (base_values_by_segment, current_values_by_segment)}.
    Woh dimension pehle jahan *kam segments zyada* explain karein: (k asc, EP desc, JS desc)."""
    out = []
    for dim, (base, cur) in dims.items():
        deltas = {s: cur.get(s, 0.0) - base.get(s, 0.0) for s in set(base) | set(cur)}
        total = sum(deltas.values())
        k_needed, ep, top = top_k, 0.0, []
        for k in range(1, top_k + 1):
            ep, top = explanatory_power(deltas, total, k)
            if ep >= target_ep:
                k_needed = k
                break
        out.append({"dimension": dim, "k": k_needed, "ep": ep, "segments": top, "js": surprise(base, cur)})
    return sorted(out, key=lambda r: (r["k"], -r["ep"], -r["js"]))


def drilldown_hypotheses(parent: Hypothesis, dimension: str, segments: list[str]) -> list[Hypothesis]:
    return [
        Hypothesis(
            id=f"{parent.id}>{dimension}={seg}",
            statement=f"{parent.statement} — {dimension} '{seg}' me concentrated",
            metric=parent.metric, dimensions=[dimension], source="drilldown", prior=PRIOR,
            parent_id=parent.id, depth=parent.depth + 1, test_type="mix_rate",
        )
        for seg in segments
    ]
