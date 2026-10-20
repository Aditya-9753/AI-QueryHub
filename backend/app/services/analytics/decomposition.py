"""F1-F5: metric decomposition — "kaunsa factor kitna responsible?" (Ch 9.1, code Ch 13.1)."""
import math
from itertools import permutations


def log_decomposition(factors0: dict, factors1: dict) -> dict:
    """Metric = product of factors. Returns each factor's share of the change.
    Shares always add up to exactly 1.0 (100%)."""
    total0 = math.prod(factors0.values())
    total1 = math.prod(factors1.values())
    d_total = math.log(total1 / total0)
    out = {}
    for k in factors0:
        d_k = math.log(factors1[k] / factors0[k])
        out[k] = {"dlog": d_k, "share": d_k / d_total,
                  "amount": d_k / d_total * (total1 - total0)}
    return out


def mix_rate(share0: dict, share1: dict, value0: dict, value1: dict) -> dict:
    """Average = sum(share_i * value_i). Splits its change into
    mix effect (composition) and rate effect (within-segment)."""
    mix = sum((share1[i] - share0[i]) * value0[i] for i in share0)
    rate = sum(share1[i] * (value1[i] - value0[i]) for i in share0)
    return {"mix": mix, "rate": rate, "total": mix + rate}


def segment_contribution(rev0: dict, rev1: dict) -> dict:
    """Additive metric: each segment's share of the total change."""
    d_total = sum(rev1.values()) - sum(rev0.values())
    return {k: (rev1[k] - rev0[k]) / d_total for k in rev0}


def shapley(f, x0: dict, x1: dict) -> dict:
    """Fair, order-independent attribution for any function f(dict).
    Use for 3-4 factors with interaction (n! orderings)."""
    keys = list(x0)
    phi = {k: 0.0 for k in keys}
    orders = list(permutations(keys))
    for order in orders:
        cur = dict(x0)
        for k in order:
            before = f(cur)
            cur[k] = x1[k]
            phi[k] += f(cur) - before
    return {k: v / len(orders) for k, v in phi.items()}
