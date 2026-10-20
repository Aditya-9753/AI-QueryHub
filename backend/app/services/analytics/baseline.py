"""F6-F10: per-day normalization, ETS expected band, z-score, YoY (Ch 9.2, code Ch 13.2).

Note (v3 implementation): forecast error ka sigma = sqrt(resid_sd^2 + current_se^2).
Sirf in-sample residuals (25-36 monthly points) sigma ko underestimate karte hain — noise-only
synthetic scenarios par isse false-alarm 11-22% tha; current month ka sampling SE jodne se ~5% (nominal).
"""
import math
import warnings

import numpy as np


def per_day(value: float, days: int) -> float:
    return value / days


def per_day_delta(r0: float, d0: int, r1: float, d1: int) -> float:
    """F7: Delta^day = (R1/d1) / (R0/d0) - 1."""
    return (r1 / d1) / (r0 / d0) - 1


def expected_band(history: list[float], season: int = 12, current_se: float = 0.0) -> dict:
    """Seasonal ETS (Holt-Winters additive) forecast for the next period + 95% band.
    history: >= 2 seasons of per-day values (e.g. 24+ months)."""
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    y = np.asarray(history, float)
    if len(y) < 2 * season:
        raise ValueError(f"ETS needs >= {2 * season} points, got {len(y)}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = ExponentialSmoothing(y, trend="add", seasonal="add", seasonal_periods=season).fit()
    forecast = float(model.forecast(1)[0])
    sigma_resid = float(np.std(model.resid, ddof=1))
    sigma = math.sqrt(sigma_resid ** 2 + current_se ** 2)
    return {"forecast": forecast, "sigma": sigma, "sigma_resid": sigma_resid, "current_se": current_se,
            "low": forecast - 1.96 * sigma, "high": forecast + 1.96 * sigma}


def z_score(actual: float, forecast: float, sigma: float) -> float:
    return (actual - forecast) / sigma


def yoy_excess(this_year_delta: float, last_year_delta: float) -> float:
    """F10: Excess = Delta^day(this year) - Delta^day(last year)."""
    return this_year_delta - last_year_delta


def rel_se(values) -> float:
    """Per-day mean ka relative standard error (log scale ke liye)."""
    v = np.asarray(values, float)
    if len(v) < 2 or v.mean() == 0:
        return float("nan")
    return float(v.std(ddof=1) / (v.mean() * math.sqrt(len(v))))


def yoy_z(cur, base, ly_cur, ly_base) -> dict:
    """YoY gate (history < 24 months): log excess / sampling SE. Arrays = daily values per period."""
    m = [float(np.mean(x)) for x in (cur, base, ly_cur, ly_base)]
    ty, ly = math.log(m[0] / m[1]), math.log(m[2] / m[3])
    se_ty = math.hypot(rel_se(cur), rel_se(base))
    se_ly = math.hypot(rel_se(ly_cur), rel_se(ly_base))
    se = math.hypot(se_ty, se_ly)
    return {"ty": ty, "ly": ly, "excess": ty - ly, "se_ty": se_ty, "se_ly": se_ly, "se_excess": se,
            "z": (ty - ly) / se if se > 0 else float("inf")}
