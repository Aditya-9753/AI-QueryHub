"""F30: weight tuning by logistic regression + 5-fold CV (sklearn ke bina, scipy.optimize se).

    cd backend && python -m tests.eval_suite.calibrate      (pehle benchmark chalao)
"""
import json
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from tests.eval_suite.metrics import brier, ece

COMPONENTS = ["DC", "SA", "SS", "CQA", "SC", "ES"]
RESULTS = Path(__file__).parent / "results"


def _sigmoid(z):
    return 1 / (1 + np.exp(-z))


def fit_logistic(X: np.ndarray, y: np.ndarray, l2: float = 1e-2) -> np.ndarray:
    """Returns [beta0, beta_1..beta_k]."""
    Xb = np.hstack([np.ones((len(X), 1)), X])

    def loss(beta):
        p = np.clip(_sigmoid(Xb @ beta), 1e-9, 1 - 1e-9)
        return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)) + l2 * np.sum(beta[1:] ** 2)

    return minimize(loss, np.zeros(Xb.shape[1]), method="L-BFGS-B").x


def weights_from_betas(betas: np.ndarray) -> dict[str, float]:
    """w_k = max(beta_k, 0) / sum_j max(beta_j, 0)."""
    pos = np.maximum(betas[1:], 0)
    total = pos.sum() or 1.0
    return {c: float(w / total) for c, w in zip(COMPONENTS, pos)}


def weighted_score(X: np.ndarray, w: dict[str, float]) -> np.ndarray:
    wv = np.array([w[c] for c in COMPONENTS])
    return X @ wv / (wv.sum() or 1.0)


def cross_validate(X: np.ndarray, y: np.ndarray, folds: int = 5, seed: int = 0) -> dict:
    idx = np.random.default_rng(seed).permutation(len(X))
    out = {"logistic_brier": [], "weighted_brier": []}
    for f in np.array_split(idx, folds):
        train = np.setdiff1d(idx, f)
        beta = fit_logistic(X[train], y[train])
        p = _sigmoid(np.hstack([np.ones((len(f), 1)), X[f]]) @ beta)
        out["logistic_brier"].append(brier(p, y[f]))
        out["weighted_brier"].append(brier(weighted_score(X[f], weights_from_betas(beta)), y[f]))
    return {k: float(np.mean(v)) for k, v in out.items()}


def main() -> None:
    bench = json.loads((RESULTS / "benchmark_latest.json").read_text(encoding="utf-8"))
    labels = [lab for r in bench["scenarios"] for lab in r["labels"]]
    if len(labels) < 10:
        raise SystemExit("labels kam hain — pehle `python -m tests.eval_suite.benchmark --scenarios 50` chalao")
    X = np.array([[lab["components"][c] for c in COMPONENTS] for lab in labels], float)
    y = np.array([lab["correct"] for lab in labels], float)
    s_equal = np.array([lab["score"] for lab in labels], float)
    beta = fit_logistic(X, y)
    result = {
        "n": len(labels), "positive_rate": float(y.mean()),
        "equal_weights": {"brier": brier(s_equal, y), "ece": ece(s_equal, y)},
        "fitted_betas": dict(zip(["intercept", *COMPONENTS], map(float, beta))),
        "fitted_weights": weights_from_betas(beta),
        "cv_5fold": cross_validate(X, y) if len(labels) >= 25 else None,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "note": "Weights tabhi WEIGHTS (evidence/scorer.py) me daalo jab CV Brier equal-weights se behtar ho.",
    }
    (RESULTS / "calibration_latest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
