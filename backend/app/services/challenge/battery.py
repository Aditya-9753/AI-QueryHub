"""Automatic challenge battery (Ch 8.6) — top 1-2 findings par chalti hai."""
from dataclasses import asdict, dataclass, field

from app.services.analytics.baseline import yoy_excess
from app.services.evidence.scorer import sample_adequacy
from app.services.verify.data_health import HealthReport

BATTERY_TYPES = ("seasonality", "calendar", "data_quality", "small_sample", "alternative_segment", "simpson",
                 "market_wide")


@dataclass
class ChallengeResult:
    type: str
    passed: bool              # True => finding survives this challenge
    detail: str
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def seasonality_check(this_year_delta: float, last_year_delta: float, min_excess: float = 0.02) -> ChallengeResult:
    """Survive karta hai agar excess (this year - last year) significant ho (|excess| >= min_excess)."""
    excess = yoy_excess(this_year_delta, last_year_delta)
    passed = abs(excess) >= min_excess
    return ChallengeResult("seasonality", passed,
                           f"this year {this_year_delta:+.4f}, last year {last_year_delta:+.4f}, "
                           f"excess {excess:+.4f} (threshold {min_excess:.4f})",
                           {"excess": excess, "threshold": min_excess})


def calendar_check(per_day_share: float) -> ChallengeResult:
    return ChallengeResult("calendar", per_day_share > 0,
                           f"per-day normalization ke baad share {per_day_share:.3f}", {"per_day_share": per_day_share})


def data_quality_check(health: HealthReport) -> ChallengeResult:
    failed = [c.check_name for c in health.failed if c.severity == "error"]
    return ChallengeResult("data_quality", health.ok, "all checks pass" if not failed else f"failed: {failed}",
                           health.to_dict())


def small_sample_check(n: int, n_required: int) -> ChallengeResult:
    sa = sample_adequacy(n, n_required)
    return ChallengeResult("small_sample", sa >= 0.5, f"n={n}, n_required={n_required}, SA={sa:.2f}", {"SA": sa})


def alternative_segment_check(ep_by_dimension: dict[str, float], claimed_dimension: str) -> ChallengeResult:
    best = max(ep_by_dimension, key=ep_by_dimension.get)
    return ChallengeResult("alternative_segment", best == claimed_dimension,
                           f"highest EP: {best} ({ep_by_dimension[best]:.2f})", {"ep": ep_by_dimension})


def simpson_check(mix: float, rate: float, claimed_type: str) -> ChallengeResult:
    dominant = "mix" if abs(mix) >= abs(rate) else "rate"
    return ChallengeResult("simpson", dominant == claimed_type,
                           f"mix {mix:+.1f}, rate {rate:+.1f} -> {dominant} dominates", {"dominant": dominant})


def market_wide_check(did_ci: tuple[float, float]) -> ChallengeResult:
    lo, hi = did_ci
    return ChallengeResult("market_wide", not (lo <= 0 <= hi), f"DiD CI [{lo:+.4f}, {hi:+.4f}]", {"ci": [lo, hi]})


def run_challenge_battery(ctx: dict) -> list[ChallengeResult]:
    """ctx me jo inputs available hain sirf wahi checks chalte hain."""
    out = []
    if {"this_year_delta", "last_year_delta"} <= ctx.keys():
        out.append(seasonality_check(ctx["this_year_delta"], ctx["last_year_delta"],
                                     ctx.get("seasonality_min_excess", 0.02)))
    if "per_day_share" in ctx:
        out.append(calendar_check(ctx["per_day_share"]))
    if "health" in ctx:
        out.append(data_quality_check(ctx["health"]))
    if {"n", "n_required"} <= ctx.keys():
        out.append(small_sample_check(ctx["n"], ctx["n_required"]))
    if {"ep_by_dimension", "claimed_dimension"} <= ctx.keys():
        out.append(alternative_segment_check(ctx["ep_by_dimension"], ctx["claimed_dimension"]))
    if {"mix", "rate", "claimed_type"} <= ctx.keys():
        out.append(simpson_check(ctx["mix"], ctx["rate"], ctx["claimed_type"]))
    if "did_ci" in ctx:
        out.append(market_wide_check(ctx["did_ci"]))
    return out
