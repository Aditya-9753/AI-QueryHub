"""F15: outlier rules."""
import numpy as np


def iqr_outliers(values, k: float = 1.5) -> list[bool]:
    """Robust (median-based): x < Q1 - k*IQR ya x > Q3 + k*IQR."""
    x = np.asarray(values, float)
    q1, q3 = np.percentile(x, [25, 75])
    iqr = q3 - q1
    return list(((x < q1 - k * iqr) | (x > q3 + k * iqr)).tolist())


def zscore_outliers(values, threshold: float = 3.0) -> list[bool]:
    """Normal-ish data ke liye: |x - mu| / sigma > 3."""
    x = np.asarray(values, float)
    sd = x.std(ddof=1)
    if sd == 0:
        return [False] * len(x)
    return list((np.abs(x - x.mean()) / sd > threshold).tolist())
