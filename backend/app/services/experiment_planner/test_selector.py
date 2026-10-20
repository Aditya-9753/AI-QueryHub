"""Kaunsa test kab (Ch 9.4 table)."""

METHOD_BY_PATTERN = {
    "period_change": "bootstrap",          # F6 + F17
    "two_groups": "welch_t",               # F12 (ya mann_whitney)
    "two_periods_daily": "permutation",    # F18
    "categorical": "chi2",                 # F13
    "numeric_relation": "corr",            # F14
    "trend": "ets",                        # F8
    "outlier": "iqr",                      # F15
    "enough_data": "required_n",           # F16
}


def select_test(pattern: str, daily: bool = False) -> str:
    if pattern == "two_groups" and daily:
        return "permutation"   # daily time-series autocorrelated hoti hai -> t-test ki jagah permutation
    return METHOD_BY_PATTERN[pattern]
