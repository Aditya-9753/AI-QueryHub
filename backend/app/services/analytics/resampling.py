"""F17-F18: block bootstrap CI + permutation test (Ch 9.4, code Ch 13.3)."""
import numpy as np


def block_bootstrap(daily_a, daily_b, stat=lambda a, b: b.mean() / a.mean() - 1, block=7, n_boot=2000, seed=42):
    """Bootstrap draws of a two-period statistic. Whole 7-day blocks resample hote hain (weekly pattern bachta hai).
    daily_a / daily_b 1-D ya 2-D (rows = days) ho sakte hain."""
    rng = np.random.default_rng(seed)
    a, b = np.asarray(daily_a, float), np.asarray(daily_b, float)

    def resample(x):
        blk = min(block, len(x))
        starts = rng.integers(0, len(x) - blk + 1, size=len(x) // blk + 1)
        return np.concatenate([x[s:s + blk] for s in starts])[:len(x)]

    return np.array([stat(resample(a), resample(b)) for _ in range(n_boot)], dtype=float)


def block_bootstrap_ci(daily_a, daily_b, stat=lambda a, b: b.mean() / a.mean() - 1,
                       block=7, n_boot=2000, seed=42):
    """95% CI for a two-period statistic. Resamples whole 7-day blocks
    so weekly autocorrelation is kept."""
    draws = block_bootstrap(daily_a, daily_b, stat, block, n_boot, seed)
    draws = draws[np.isfinite(draws)]
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def bootstrap_pvalue(draws) -> float:
    """Two-sided percentile-bootstrap p-value: kitni draws zero ke doosri taraf hain."""
    d = np.asarray(draws, float)
    d = d[np.isfinite(d)]
    if len(d) == 0:
        return 1.0
    tail = min((d <= 0).sum(), (d >= 0).sum())
    return float(min(1.0, 2 * (tail + 1) / (len(d) + 1)))


def permutation_test(daily_a, daily_b, n_perm=5000, seed=42):
    """Two-sided p-value for difference in means, no normality assumption."""
    rng = np.random.default_rng(seed)
    a, b = np.asarray(daily_a, float), np.asarray(daily_b, float)
    observed = b.mean() - a.mean()
    pooled = np.concatenate([a, b])
    count = 0
    for _ in range(n_perm):
        rng.shuffle(pooled)
        diff = pooled[len(a):].mean() - pooled[:len(a)].mean()
        count += abs(diff) >= abs(observed)
    return (count + 1) / (n_perm + 1)
