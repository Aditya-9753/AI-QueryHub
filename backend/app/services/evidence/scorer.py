"""F21-F26: gated + multiplicative Evidence Score (Ch 9.6, code Ch 13.6)."""

WEIGHTS = {"DC": 1, "SA": 1, "SS": 1, "CQA": 1, "SC": 1, "ES": 1}  # tune later (tests/eval_suite/calibrate.py)


def data_coverage(days_with_data, expected_days, null_rate):
    return min(1.0, days_with_data / expected_days) * (1 - null_rate)


def sample_adequacy(n, n_required):
    return min(1.0, n / n_required)


def statistical_strength(q_value, effect, mde, ci_low, ci_high):
    if ci_low <= 0 <= ci_high:                 # CI includes zero -> no strength
        return 0.0
    return (1 - q_value) * min(1.0, abs(effect) / mde)


def cross_query_agreement(path_values, tol=0.10):
    """path_values: same metric measured by independent queries."""
    if len(path_values) < 2:
        return 0.5
    ref = path_values[0]
    agree = sum(1 for v in path_values
                if (v > 0) == (ref > 0) and abs(v - ref) <= tol * abs(ref))
    return agree / len(path_values)


def schema_confidence(source, similarity=0.0, user_approved=False):
    if source == "semantic_layer":
        return 1.0
    if similarity >= 0.8 and user_approved:
        return 0.8
    return 0.5


def explained_share(share):
    """ES = min(1, |Share_f|)."""
    return min(1.0, abs(share))


def evidence_score(c: dict, contradiction_penalty: float, w=WEIGHTS):
    """Gated + multiplicative. Returns (score or None, label)."""
    if c["DC"] < 0.7 or c["SA"] < 0.5:
        return None, "Insufficient"
    base = sum(w[k] * c[k] for k in w) / sum(w.values())
    score = base * (1 - contradiction_penalty)
    label = "Strong" if score >= 0.75 else "Moderate" if score >= 0.5 else "Weak"
    return round(score, 3), label


def old_score(c: dict, cp: float) -> float:
    """F20 (v2.0) — sirf comparison / viva ke liye."""
    return 0.2 * (c["DC"] + c["SA"] + c["SS"] + c["CQA"] + c["SC"]) - 0.3 * cp
