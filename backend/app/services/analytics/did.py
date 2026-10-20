"""F11: difference-in-differences + control selection (Ch 9.3, 8.3)."""
import math

import numpy as np


def diff_in_diff(t0: float, t1: float, c0: float, c1: float) -> float:
    """Log difference-in-differences. t = treated (Delhi), c = control."""
    return (math.log(t1) - math.log(t0)) - (math.log(c1) - math.log(c0))


def pre_trend_gap(treated: list[float], control: list[float]) -> float:
    """Pre-period me log-growth ka average absolute farq.
    Chhota gap => parallel-trends assumption plausible; bada => DiD finding ko 'Weak' mark karo."""
    t = np.diff(np.log(np.asarray(treated, float)))
    c = np.diff(np.log(np.asarray(control, float)))
    return float(np.mean(np.abs(t - c)))


def parallel_trends_test(treated: list[float], control: list[float], max_slope: float = 0.005,
                         alpha: float = 0.05) -> dict:
    """DiD assumption check: pre-period me ln(T) - ln(C) ka time trend. Slope significant (p < alpha)
    aur |slope| > max_slope (0.5%/month) => trends parallel nahi, DiD finding 'Weak'."""
    from scipy import stats

    gap = np.log(np.asarray(treated, float)) - np.log(np.asarray(control, float))
    if len(gap) < 3:
        return {"slope": None, "p_value": None, "ok": True, "months": len(gap)}
    res = stats.linregress(np.arange(len(gap)), gap)
    ok = not (res.pvalue < alpha and abs(res.slope) > max_slope)
    return {"slope": float(res.slope), "p_value": float(res.pvalue), "ok": bool(ok), "months": len(gap)}


def select_controls(target: list[float], candidates: dict[str, list[float]],
                    min_corr: float = 0.8, size_range: tuple[float, float] = (0.5, 2.0)) -> list[str]:
    """Control rule (8.3): pichhle 12 mahine me corr >= 0.8 aur size ratio 0.5-2.0.
    Khaali list => DiD skip, finding me limitation likho."""
    tgt = np.asarray(target, float)
    picked = []
    for name, series in candidates.items():
        s = np.asarray(series, float)
        if len(s) != len(tgt) or len(s) < 3:
            continue
        corr = float(np.corrcoef(tgt, s)[0, 1])
        ratio = float(s.mean() / tgt.mean())
        if corr >= min_corr and size_range[0] <= ratio <= size_range[1]:
            picked.append(name)
    return picked
