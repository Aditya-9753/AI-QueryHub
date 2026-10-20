"""F31-F32: Brier, ECE, attribution error, Recall@k."""
import numpy as np


def brier(scores, labels) -> float:
    s, y = np.asarray(scores, float), np.asarray(labels, float)
    return float(np.mean((s - y) ** 2))


def ece(scores, labels, bins: int = 10) -> float:
    s, y = np.asarray(scores, float), np.asarray(labels, float)
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(s, edges[1:-1]), 0, bins - 1)
    total = 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            total += m.sum() / len(s) * abs(y[m].mean() - s[m].mean())
    return float(total)


def attribution_error(predicted: dict[str, float], true: dict[str, float]) -> float:
    keys = set(predicted) | set(true)
    return float(np.mean([abs(predicted.get(k, 0.0) - true.get(k, 0.0)) for k in keys]))


def recall_at_k(ranked: list[list[str]], planted: list[str | None], k: int = 3) -> float:
    pairs = [(r, p) for r, p in zip(ranked, planted) if p is not None]
    if not pairs:
        return float("nan")
    return sum(p in r[:k] for r, p in pairs) / len(pairs)
