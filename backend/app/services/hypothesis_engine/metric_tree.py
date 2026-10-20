"""Metric tree se deterministic hypotheses (F1, Figure 8.2).

revenue: R = D x n x A,  n = placed/day x (1 - c),  A = sum(s_i a_i)
orders:  N = D x placed/day x (1 - c)
RAW_TREES = per-day normalization ke bina (ablation "-Normalization"): calendar factor alag nahi hota.
"""
from app.schemas.qtrace import Hypothesis

PRIOR = 0.5

_MIX = {"key": "category_mix", "statement": "{Dim} mix shift hua (mix effect)", "test_type": "mix_rate",
        "needs_dimension": True}
_RATE = {"key": "segment_aov", "statement": "{Dim} ke andar AOV badla (rate effect)", "test_type": "mix_rate",
         "needs_dimension": True}
_PLACED = {"key": "placed_orders", "statement": "Placed orders per day badle", "test_type": "bootstrap"}
_CANCEL = {"key": "cancel_rate", "statement": "Cancellation rate badla", "test_type": "chi2"}
_DAYS = {"key": "days", "statement": "Calendar: period me din kam/zyada the", "test_type": "log_decomp"}

METRIC_TREES: dict[str, dict] = {
    "revenue": {"formula": "R = D x n x A", "factors": [
        _DAYS,
        {"key": "orders_per_day", "statement": "Orders per day badle", "test_type": "bootstrap",
         "children": [_PLACED, _CANCEL]},
        {"key": "aov", "statement": "AOV (average order value) badla", "test_type": "bootstrap",
         "children": [_MIX, _RATE]},
    ]},
    "orders": {"formula": "N = D x placed/day x (1 - c)", "factors": [
        _DAYS,
        {**_PLACED, "statement": "Placed orders per day badle"},
        _CANCEL,
    ]},
}

RAW_TREES: dict[str, dict] = {
    "revenue": {"formula": "R = N x A", "factors": [
        {"key": "orders", "statement": "Total orders badle", "test_type": "bootstrap",
         "children": [{**_PLACED, "statement": "Total placed orders badle"}, _CANCEL]},
        {"key": "aov", "statement": "AOV (average order value) badla", "test_type": "bootstrap",
         "children": [_MIX, _RATE]},
    ]},
    "orders": {"formula": "N = placed x (1 - c)", "factors": [
        {**_PLACED, "statement": "Total placed orders badle"}, _CANCEL,
    ]},
}


def _tree(metric: str, per_day: bool) -> dict:
    return (METRIC_TREES if per_day else RAW_TREES).get(metric, {})


def _make(metric: str, node: dict, parent: Hypothesis | None, dimension: str | None = None) -> Hypothesis:
    dim = dimension or "segment"
    return Hypothesis(
        id=f"{metric}.{node['key']}",
        statement=node["statement"].format(Dim=dim.title()),
        metric=metric,
        dimensions=[dimension] if (dimension and node.get("needs_dimension")) else [],
        source="metric_tree",
        prior=PRIOR,
        parent_id=parent.id if parent else None,
        depth=(parent.depth + 1) if parent else 0,
        test_type=node["test_type"],
    )


def factor_keys(metric: str, per_day: bool = True) -> set[str]:
    """Tree ki saari keys (children samet) — templates ke duplicates skip karne ke liye."""
    keys: set[str] = set()

    def walk(nodes):
        for n in nodes:
            keys.add(n["key"])
            walk(n.get("children", []))

    walk(_tree(metric, per_day).get("factors", []))
    return keys


def metric_tree_hypotheses(metric: str, per_day: bool = True) -> list[Hypothesis]:
    """Top-level factors (depth 0). Children drill-down par (`children_of`) aate hain."""
    return [_make(metric, f, None) for f in _tree(metric, per_day).get("factors", [])]


def needs_dimension(h: Hypothesis, per_day: bool = True) -> bool:
    return any(c.get("needs_dimension") for c in _children_nodes(h, per_day))


def _children_nodes(h: Hypothesis, per_day: bool) -> list[dict]:
    key = h.id.split(".", 1)[-1]
    for f in _tree(h.metric, per_day).get("factors", []):
        if f["key"] == key:
            return f.get("children", [])
    return []


def children_of(h: Hypothesis, per_day: bool = True, dimension: str | None = None) -> list[Hypothesis]:
    return [_make(h.metric, c, h, dimension) for c in _children_nodes(h, per_day)]
