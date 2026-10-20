"""ANALYZE result profiling — query result se deterministic insights (LLM nahi, sirf arithmetic).

Columns ko roles milte hain (time / dimension / measure), result ka shape tay hota hai
(scalar / breakdown / timeseries / matrix) aur us shape ke hisaab se insights banti hain:
top contributor + share, concentration (top-3, Pareto 80%), spread, robust outliers (MAD z),
trend (first->last, peak/trough, biggest period-over-period move, slope R²). Har number seedha
result rows se aata hai, isliye ye grounded hain by construction.
"""
import math
import re
from statistics import median

ID_COL = re.compile(r"(^id$|_id$)", re.I)
TIME_NAME = re.compile(r"(date|day|week|month|year|period|quarter|_at$|^dt$|time)", re.I)
ISO_DATE = re.compile(r"^\d{4}-\d{2}(-\d{2})?([ T].*)?$")
MONEY = re.compile(r"(revenue|amount|sales|gmv|value|payment|spend|price|aov|cost|income|profit)", re.I)
RATIO = re.compile(r"(rate|pct|percent|ratio|share|avg|average|mean|aov|per_)", re.I)

MAX_INSIGHTS = 6


# ------------------------------------------------------------------ formatting
def fmt_value(v: float, measure: str, ratio_01: bool = False) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    if ratio_01:
        return f"{v * 100:.1f}%"
    if MONEY.search(measure):
        a = abs(v)
        if a >= 1e7:
            return f"₹{v / 1e7:,.2f} Cr"
        if a >= 1e5:
            return f"₹{v / 1e5:,.2f} L"
        return f"₹{v:,.0f}" if a >= 100 else f"₹{v:,.2f}"
    if float(v).is_integer() and abs(v) < 1e15:
        return f"{int(v):,}"
    return f"{v:,.2f}" if abs(v) >= 1 else f"{v:.4f}"


def pct(x: float) -> str:
    return f"{x * 100:+.1f}%" if x is not None else "—"


def share(x: float) -> str:
    return f"{x * 100:.1f}%"


# ------------------------------------------------------------------ roles
def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and not (isinstance(v, float) and math.isnan(v))


def column_roles(columns: list[str], rows: list[list]) -> dict[str, str]:
    roles: dict[str, str] = {}
    for i, c in enumerate(columns):
        vals = [r[i] for r in rows if r[i] is not None]
        if ID_COL.search(c):
            roles[c] = "id"
        elif vals and all(isinstance(v, str) and ISO_DATE.match(v) for v in vals):
            roles[c] = "time"
        elif vals and all(_is_num(v) for v in vals):
            # month/year jaise integer columns = time axis, measure nahi
            small_ints = all(float(v).is_integer() and 0 <= v <= 3000 for v in vals)
            roles[c] = "time" if TIME_NAME.search(c) and small_ints else "measure"
        elif TIME_NAME.search(c):
            roles[c] = "time"
        else:
            roles[c] = "dimension"
    return roles


def _shape(dims: list[str], times: list[str], measures: list[str], n: int) -> str:
    if not measures:
        return "table"
    if n == 1 and not dims and not times:
        return "scalar"
    if times and not dims:
        return "timeseries"
    if len(dims) + len(times) >= 2:
        return "matrix"
    if dims:
        return "breakdown"
    return "table"


# ------------------------------------------------------------------ helpers
def _robust_outliers(labels: list[str], vals: list[float], z_cut: float = 3.5) -> list[tuple[str, float, float]]:
    if len(vals) < 5:
        return []
    med = median(vals)
    mad = median(abs(v - med) for v in vals)
    if mad == 0:
        return []
    out = [(lab, v, 0.6745 * (v - med) / mad) for lab, v in zip(labels, vals)]
    return sorted([o for o in out if abs(o[2]) >= z_cut], key=lambda o: -abs(o[2]))


def _slope_r2(vals: list[float]) -> tuple[float, float]:
    n = len(vals)
    xs = list(range(n))
    mx, my = sum(xs) / n, sum(vals) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, vals))
    syy = sum((y - my) ** 2 for y in vals)
    if sxx == 0 or syy == 0:
        return 0.0, 0.0
    slope = sxy / sxx
    return slope, (sxy * sxy) / (sxx * syy)


def _ins(kind: str, title: str, text: str, tone: str = "neutral", **values) -> dict:
    return {"kind": kind, "title": title, "text": text, "tone": tone, "values": values}


# ------------------------------------------------------------------ shapes
def _breakdown(labels: list[str], vals: list[float], measure: str, dim: str, additive: bool, r01: bool) -> list[dict]:
    f = lambda v: fmt_value(v, measure, r01)  # noqa: E731
    out: list[dict] = []
    order = sorted(range(len(vals)), key=lambda i: -vals[i])
    top, bottom = order[0], order[-1]
    total = sum(vals)
    nonneg = all(v >= 0 for v in vals)
    if additive and nonneg and total > 0 and len(vals) >= 2:
        s = vals[top] / total
        out.append(_ins("top", f"{labels[top]} leads", f"{labels[top]} contributes {share(s)} of total {measure} "
                        f"({f(vals[top])} of {f(total)}).", "accent", label=labels[top], share=s))
        if len(vals) >= 4:
            top3 = sum(vals[i] for i in order[:3]) / total
            cum, k = 0.0, 0
            for i in order:
                cum += vals[i]
                k += 1
                if cum / total >= 0.8:
                    break
            out.append(_ins("concentration", "Concentration",
                            f"Top 3 {dim} values hold {share(top3)} of {measure}; {k} of {len(vals)} "
                            f"make up 80% (Pareto).", "warn" if top3 >= 0.8 else "neutral", top3=top3, pareto_k=k))
    else:
        mean = total / len(vals)
        out.append(_ins("top", f"{labels[top]} is highest", f"{labels[top]} has the highest {measure} at {f(vals[top])}"
                        + (f", {pct(vals[top] / mean - 1)} vs the average {f(mean)}." if mean else "."),
                        "accent", label=labels[top]))
    if len(vals) >= 2 and vals[bottom] != vals[top]:
        second = order[1]
        gap = (vals[top] / vals[second] - 1) if vals[second] > 0 else None
        out.append(_ins("spread", "Spread", f"Lowest is {labels[bottom]} at {f(vals[bottom])}"
                        + (f"; the leader is {pct(gap).lstrip('+')} ahead of #2 {labels[second]}." if gap is not None
                           else "."), "neutral", low=labels[bottom]))
    for lab, v, z in _robust_outliers(labels, vals)[:2]:
        out.append(_ins("outlier", f"Outlier: {lab}", f"{lab} at {f(v)} is unusually {'high' if z > 0 else 'low'} "
                        f"(robust z = {z:+.1f}).", "bad" if z < 0 else "warn", label=lab, z=z))
    return out


def _timeseries(labels: list[str], vals: list[float], measure: str, r01: bool) -> list[dict]:
    f = lambda v: fmt_value(v, measure, r01)  # noqa: E731
    out: list[dict] = []
    if len(vals) < 2:
        return out
    first, last = vals[0], vals[-1]
    ch = (last / first - 1) if first else None
    out.append(_ins("trend", "Overall change", f"{measure} moved from {f(first)} ({labels[0]}) to {f(last)} "
                    f"({labels[-1]})" + (f", {pct(ch)}." if ch is not None else "."),
                    "ok" if (ch or 0) >= 0 else "bad", change=ch))
    hi = max(range(len(vals)), key=lambda i: vals[i])
    lo = min(range(len(vals)), key=lambda i: vals[i])
    out.append(_ins("peak", "Peak & trough", f"Peak {f(vals[hi])} in {labels[hi]}; trough {f(vals[lo])} in "
                    f"{labels[lo]}.", "neutral", peak=labels[hi], trough=labels[lo]))
    moves = [(i, vals[i] / vals[i - 1] - 1) for i in range(1, len(vals)) if vals[i - 1]]
    if moves:
        i, m = max(moves, key=lambda t: abs(t[1]))
        out.append(_ins("move", "Biggest move", f"Largest period-over-period change: {pct(m)} from {labels[i - 1]} "
                        f"to {labels[i]}.", "ok" if m >= 0 else "bad", period=labels[i], change=m))
    if len(vals) >= 4:
        slope, r2 = _slope_r2(vals)
        mean = sum(vals) / len(vals)
        if r2 >= 0.5 and mean:
            out.append(_ins("slope", "Steady trend", f"A {'rising' if slope > 0 else 'falling'} linear trend explains "
                            f"{share(r2)} of the variation (≈{f(abs(slope))} per period).",
                            "ok" if slope > 0 else "bad", r2=r2))
        else:
            out.append(_ins("slope", "No clear trend", f"Values fluctuate around {f(mean)}; a straight-line trend "
                            f"explains only {share(r2)} of the variation.", "neutral", r2=r2))
    return out


def _matrix(rows: list[list], i_a: int, i_b: int, i_m: int, a: str, b: str, measure: str, r01: bool) -> list[dict]:
    f = lambda v: fmt_value(v, measure, r01)  # noqa: E731
    cells = [(str(r[i_a]), str(r[i_b]), float(r[i_m])) for r in rows if _is_num(r[i_m])]
    if not cells:
        return []
    best = max(cells, key=lambda c: c[2])
    out = [_ins("top", "Largest cell", f"{best[0]} × {best[1]} is the largest at {f(best[2])}.", "accent")]
    by_a: dict[str, dict[str, float]] = {}
    for x, y, v in cells:
        by_a.setdefault(x, {})[y] = v
    leaders = {x: max(d, key=d.get) for x, d in by_a.items() if d}
    common = max(set(leaders.values()), key=list(leaders.values()).count)
    n_same = sum(1 for v in leaders.values() if v == common)
    out.append(_ins("pattern", "Pattern", f"{common} is the top {b} in {n_same} of {len(leaders)} {a} values.",
                    "neutral", leader=common))
    return out


# ------------------------------------------------------------------ main
def profile_result(columns: list[str], rows: list[list], question: str = "",
                   dimension_values: dict[str, list[str]] | None = None) -> dict | None:
    """Result ka profile: roles, shape, primary measure ke stats, insights, follow-up suggestions."""
    if not rows or not columns:
        return None
    roles = column_roles(columns, rows)
    dims = [c for c in columns if roles[c] == "dimension"]
    times = [c for c in columns if roles[c] == "time"]
    measures = [c for c in columns if roles[c] == "measure"]
    shape = _shape(dims, times, measures, len(rows))
    out: dict = {"roles": roles, "shape": shape, "measure": None, "dimension": None, "stats": None,
                 "insights": [], "followups": []}
    if not measures:
        return out
    m = measures[0]
    im = columns.index(m)
    vals_all = [float(r[im]) for r in rows if _is_num(r[im])]
    if not vals_all:
        return out
    r01 = bool(RATIO.search(m)) and all(0 <= v <= 1 for v in vals_all) and not MONEY.search(m)
    additive = not RATIO.search(m)
    out["measure"] = m
    out["format"] = "pct" if r01 else "money" if MONEY.search(m) else "number"
    out["stats"] = {"n": len(vals_all), "total": sum(vals_all) if additive else None, "mean": sum(vals_all) / len(vals_all),
                    "min": min(vals_all), "max": max(vals_all), "additive": additive}

    axis = (times or dims or [None])[0]
    if shape in ("breakdown", "timeseries") and axis:
        ia = columns.index(axis)
        pairs = [(str(r[ia]), float(r[im])) for r in rows if _is_num(r[im]) and r[ia] is not None]
        if shape == "timeseries":
            pairs.sort(key=lambda p: (len(p[0]), p[0]) if p[0].isdigit() else p[0])
        labels, vals = [p[0] for p in pairs], [p[1] for p in pairs]
        out["dimension"] = axis
        out["insights"] = (_timeseries(labels, vals, m, r01) if shape == "timeseries"
                           else _breakdown(labels, vals, m, axis, additive, r01))
        if shape == "breakdown" and labels:
            top = labels[max(range(len(vals)), key=lambda i: vals[i])]
            out["top_label"] = top
    elif shape == "matrix":
        a, b = (times + dims)[:2]
        out["dimension"] = a
        out["insights"] = _matrix(rows, columns.index(a), columns.index(b), im, a, b, m, r01)
    elif shape == "scalar":
        out["insights"] = [_ins("value", m, f"{m} = {fmt_value(vals_all[0], m, r01)}.", "accent")]
    out["insights"] = out["insights"][:MAX_INSIGHTS]
    out["followups"] = _followups(question, shape, out.get("dimension"), out.get("top_label"), m, columns,
                                  dimension_values or {})
    return out


def _followups(question: str, shape: str, dim: str | None, top: str | None, measure: str, columns: list[str],
               dimension_values: dict[str, list[str]]) -> list[dict]:
    q = question.strip().rstrip("?").strip()
    other = [d for d in dimension_values if d not in columns and d.lower() not in q.lower()]
    out: list[dict] = []
    if shape == "breakdown" and top and other:
        out.append({"label": f"Drill into {top} by {other[0]}", "mode": "ANALYZE",
                    "question": f"{q} — only {dim} = {top}, broken down by {other[0]}"})
    if shape in ("breakdown", "scalar") and not re.search(r"(month|monthly|trend|mahine|week|daily)", q, re.I):
        out.append({"label": "Monthly trend", "mode": "ANALYZE",
                    "question": f"{q} — month-wise trend for the last 6 months"})
    if shape == "timeseries" and other:
        out.append({"label": f"Split trend by {other[0]}", "mode": "ANALYZE",
                    "question": f"{q} — split by {other[0]}"})
    if shape in ("breakdown", "timeseries") and len(other) > 1:
        out.append({"label": f"Compare by {other[1]}", "mode": "ANALYZE", "question": f"{q} — by {other[1]} instead"})
    return out[:3]
