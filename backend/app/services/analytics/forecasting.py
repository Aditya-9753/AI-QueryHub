"""F8: Holt-Winters (ETS) forecast — trend / forecast questions ke liye."""
import numpy as np


def ets_forecast(history: list[float], horizon: int = 1, season: int | None = 12) -> list[float]:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    y = np.asarray(history, float)
    seasonal = "add" if season and len(y) >= 2 * season else None
    model = ExponentialSmoothing(y, trend="add", seasonal=seasonal,
                                 seasonal_periods=season if seasonal else None).fit()
    return [float(v) for v in model.forecast(horizon)]
