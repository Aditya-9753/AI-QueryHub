"""Step V (part 1): data health checks (Ch 8.2).

Functions pure hain — stats SQL se aate hain (`health_queries`), checks yahan evaluate hote hain.
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta

import numpy as np

from app.services.rag.semantic_layer import MetricDef, _lit


@dataclass
class CheckResult:
    check_name: str
    expected: str
    observed: str
    passed: bool
    severity: str = "error"          # error => data issue (early exit), warning => sirf warning


@dataclass
class HealthReport:
    checks: list[CheckResult] = field(default_factory=list)
    days_with_data: int | None = None
    expected_days: int | None = None

    @property
    def ok(self) -> bool:
        return all(c.passed for c in self.checks if c.severity == "error")

    @property
    def failed(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed]

    @property
    def null_rate(self) -> float:
        for c in self.checks:
            if c.check_name == "null_rate":
                return float(c.observed)
        return 0.0

    def to_dict(self) -> dict:
        return {"ok": self.ok, "days_with_data": self.days_with_data, "expected_days": self.expected_days,
                "checks": [asdict(c) for c in self.checks]}


def completeness_check(days_with_data: int, expected_days: int, min_ratio: float = 0.95) -> CheckResult:
    ratio = days_with_data / expected_days if expected_days else 0.0
    return CheckResult("completeness", f">= {min_ratio:.2f}", f"{ratio:.3f}", ratio >= min_ratio)


def freshness_check(max_updated_at: datetime, period_end: datetime,
                    allowed_lag: timedelta = timedelta(days=-1)) -> CheckResult:
    """Default: data period ke aakhri din (period_end - 1 day) tak pahunch gaya ho."""
    threshold = period_end + allowed_lag
    return CheckResult("freshness", f">= {threshold.date().isoformat()}", max_updated_at.isoformat(sep=" "),
                       max_updated_at >= threshold, severity="warning")


def null_rate_check(null_rate: float, max_rate: float = 0.02) -> CheckResult:
    return CheckResult("null_rate", f"<= {max_rate}", f"{null_rate:.4f}", null_rate <= max_rate)


def duplicates_check(duplicate_count: int) -> CheckResult:
    return CheckResult("duplicates", "0", str(duplicate_count), duplicate_count == 0)


def volume_check(row_count: float, history_counts: list[float], k: float = 3.0) -> CheckResult:
    h = np.asarray(history_counts, float)
    lo, hi = h.mean() - k * h.std(ddof=1), h.mean() + k * h.std(ddof=1)
    return CheckResult("volume", f"[{lo:.1f}, {hi:.1f}] rows/day", f"{row_count:.1f}", bool(lo <= row_count <= hi),
                       severity="warning")


def run_data_health(stats: dict) -> HealthReport:
    """stats keys (jo available ho): days_with_data, expected_days, null_rate, duplicate_count,
    max_updated_at, period_end, row_count, history_counts."""
    r = HealthReport(days_with_data=stats.get("days_with_data"), expected_days=stats.get("expected_days"))
    if "days_with_data" in stats and "expected_days" in stats:
        r.checks.append(completeness_check(stats["days_with_data"], stats["expected_days"]))
    if stats.get("max_updated_at") is not None and "period_end" in stats:
        r.checks.append(freshness_check(stats["max_updated_at"], stats["period_end"]))
    if "null_rate" in stats:
        r.checks.append(null_rate_check(stats["null_rate"]))
    if "duplicate_count" in stats:
        r.checks.append(duplicates_check(stats["duplicate_count"]))
    if "row_count" in stats and len(stats.get("history_counts", [])) >= 3:
        r.checks.append(volume_check(stats["row_count"], stats["history_counts"]))
    return r


def _where(m: MetricDef, start: str, end: str, filters: dict[str, str] | None, as_of: str | None = None) -> str:
    parts = [f"{m.time_column} >= {_lit(start)}", f"{m.time_column} < {_lit(end)}"]
    parts += [f"{c} = {_lit(v)}" for c, v in (filters or {}).items()]
    if as_of and m.updated_column:
        parts.append(f"{m.updated_column} <= {_lit(as_of)}")
    return " AND ".join(parts)


def health_queries(m: MetricDef, start: str, end: str, filters: dict[str, str] | None = None,
                   as_of: str | None = None) -> dict[str, str]:
    """Metric ki table par health stats SQL (firewall se guzarti hai). end exclusive."""
    w = _where(m, start, end, filters, as_of)
    req = list(m.required_columns)
    nulls = " + ".join(f"SUM(CASE WHEN {c} IS NULL THEN 1 ELSE 0 END)" for c in req) or "0"
    key = " || '|' || ".join(f"CAST({k} AS TEXT)" for k in m.key_columns)
    q = {
        "days_with_data": f"SELECT COUNT(DISTINCT DATE({m.time_column})) FROM {m.table} WHERE {w}",
        "null_rate": f"SELECT ({nulls}) * 1.0 / NULLIF(COUNT(*) * {max(len(req), 1)}, 0) FROM {m.table} WHERE {w}",
        "duplicate_count": f"SELECT COUNT(*) - COUNT(DISTINCT {key}) FROM {m.table} WHERE {w}",
    }
    if m.updated_column:
        q["max_updated_at"] = f"SELECT MAX({m.updated_column}) FROM {m.table} WHERE {w}"
    return q


def volume_query(m: MetricDef, start: str, end: str, filters: dict[str, str] | None = None,
                 as_of: str | None = None) -> str:
    return (f"SELECT DATE({m.time_column}) AS day, COUNT(*) AS n FROM {m.table} "
            f"WHERE {_where(m, start, end, filters, as_of)} GROUP BY DATE({m.time_column})")


def outlier_check(values, reference) -> CheckResult:
    """F15 (IQR rule): current period ke kitne din reference distribution ke hisaab se extreme hain (warning)."""
    from app.services.analytics.anomaly import iqr_outliers

    ref = list(reference)
    flags = iqr_outliers(ref + list(values), k=3.0)[len(ref):]
    n = int(sum(flags))
    return CheckResult("outlier_days", "0 extreme days (IQR k=3)", str(n), n == 0, severity="warning")
