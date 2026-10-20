"""F6, F12-F14, F16: basic statistical tests (Ch 9.4)."""
import math

import numpy as np
from scipy import stats


def period_delta(y0: float, y1: float) -> dict:
    """F6: absolute aur relative change."""
    return {"abs": y1 - y0, "rel": (y1 / y0 - 1) if y0 else math.nan}


def welch_t(a, b) -> dict:
    """F12: Welch t-test (unequal variance). effect = mean(b) - mean(a)."""
    res = stats.ttest_ind(b, a, equal_var=False)
    return {"t": float(res.statistic), "p_value": float(res.pvalue),
            "effect": float(np.mean(b) - np.mean(a))}


def mann_whitney(a, b) -> dict:
    res = stats.mannwhitneyu(b, a, alternative="two-sided")
    return {"u": float(res.statistic), "p_value": float(res.pvalue)}


def chi_square(table) -> dict:
    """F13: chi-square on a contingency table. Expected count >= 5 hona chahiye."""
    chi2, p, dof, expected = stats.chi2_contingency(np.asarray(table))
    return {"chi2": float(chi2), "p_value": float(p), "dof": int(dof),
            "min_expected": float(expected.min()), "valid": bool(expected.min() >= 5)}


def correlation(x, y, method: str = "pearson") -> dict:
    """F14: correlation — UI me 'association' likho, causation nahi."""
    fn = stats.pearsonr if method == "pearson" else stats.spearmanr
    r, p = fn(x, y)
    return {"r": float(r), "p_value": float(p), "method": method}


def required_n(sigma: float, mde: float, alpha: float = 0.05, power: float = 0.8) -> int:
    """F16: n_req = 2 (z_{1-a/2} + z_{1-b})^2 sigma^2 / MDE^2."""
    z_a = stats.norm.ppf(1 - alpha / 2)
    z_b = stats.norm.ppf(power)
    return math.ceil(2 * (z_a + z_b) ** 2 * sigma ** 2 / mde ** 2)
