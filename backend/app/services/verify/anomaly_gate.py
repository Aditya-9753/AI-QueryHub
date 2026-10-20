"""Step V (part 2): "kya change normal band ke bahar hai?" (F9, F10)."""
from app.services.analytics.baseline import expected_band, yoy_z, z_score

Z_THRESHOLD = 1.96


def gate_from_band(actual: float, forecast: float, sigma: float, z_threshold: float = Z_THRESHOLD) -> dict:
    z = z_score(actual, forecast, sigma)
    return {"method": "ets", "z": z, "actual": actual,
            "band": {"forecast": forecast, "sigma": sigma,
                     "low": forecast - z_threshold * sigma, "high": forecast + z_threshold * sigma},
            "status": "anomaly" if abs(z) > z_threshold else "within_normal"}


def anomaly_gate(actual_per_day: float, history: list[float] | None = None, season: int = 12,
                 current_se: float = 0.0, yoy_arrays: tuple | None = None,
                 z_threshold: float = Z_THRESHOLD, min_ets_points: int = 24) -> dict:
    """>= 24 monthly points => ETS band (sigma incl. current month sampling SE).
    Warna YoY rule: z = (ln this-year change - ln last-year change) / SE (blueprint 8.2)."""
    if history is not None and len(history) >= max(min_ets_points, 2 * season):
        try:
            band = expected_band(history, season, current_se=current_se)
            out = gate_from_band(actual_per_day, band["forecast"], band["sigma"], z_threshold)
            out["band"].update(sigma_resid=band["sigma_resid"], current_se=current_se)
            out["months_used"] = len(history)
            return out
        except Exception:  # ETS fit fail -> YoY fallback
            pass
    if yoy_arrays is not None:
        y = yoy_z(*yoy_arrays)
        return {"method": "yoy", "z": y["z"], "actual": actual_per_day, "yoy": y,
                "status": "anomaly" if abs(y["z"]) > z_threshold else "within_normal"}
    return {"method": "none", "z": None, "actual": actual_per_day, "status": "insufficient_history"}
