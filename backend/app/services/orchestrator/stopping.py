"""F28: stop if sum(max(0, Share_f)) >= 0.80 or budget = 0 or depth = 2.

Implementation note: explained >= target hone par bhi pending drill-down (refinement) poora hota hai —
drill-down naya hissa explain nahi karta, sirf bada factor (share > 30%) ko localize karta hai
(e.g. AOV -> mix vs rate). Depth limit 2 isse bounded rakhta hai.
"""
from app.services.orchestrator.budget import Budget

MAX_DEPTH = 2
DRILLDOWN_SHARE = 0.30


def explained_share(shares: list[float]) -> float:
    return sum(max(0.0, s) for s in shares)


def stop_reason(explained: float, budget: Budget, queue_empty: bool, target: float = 0.80,
                pending_refinements: bool = False) -> str | None:
    """None => continue. Reason experiment_runs.stop_reason me save hota hai."""
    if explained >= target and not pending_refinements:
        return f"explained>={target:.2f}"
    if not budget.left():
        return "budget_exhausted"
    if queue_empty:
        return f"explained>={target:.2f}" if explained >= target else "queue_empty"
    return None


def should_drilldown(share: float, depth: int, threshold: float = DRILLDOWN_SHARE, max_depth: int = MAX_DEPTH) -> bool:
    return share > threshold and depth < max_depth
