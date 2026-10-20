"""Synthetic planted-cause benchmark runner (Ch 18.2) — investigation quality.

    cd backend && python -m tests.eval_suite.benchmark --scenarios 50 [--fast]

Har scenario: generator data -> SQLite (daily_sales) -> Q-TRACE+ (spec ground truth se, LLM ke bina) -> metrics:
Recall@k, attribution error (F32), gate false-alarm (noise), data-issue detection, grounding violations,
latency/cost. Calibration ke liye har scored finding ka (components, correct) label bhi save hota hai.
"""
import argparse
import json
import math
import os
import tempfile
import time
from pathlib import Path

import numpy as np
from sqlalchemy import create_engine

from app.schemas.qtrace import SUPPORTED_LIKE, QuestionSpec
from app.services.orchestrator.qtrace import QTraceConfig, QTracePlus
from app.services.rag.semantic_layer import SemanticLayer, daily_sales_metrics, month_bounds
from tests.eval_suite.generator import base_daily, make_scenarios, plant
from tests.eval_suite.metrics import attribution_error, brier, ece

HERE = Path(__file__).parent
RESULTS = HERE / "results"
EXPECTED_KEYS = {
    "mix_shift": {"revenue.category_mix", "revenue.orders_per_day", "revenue.placed_orders"},
    "cancel_spike": {"revenue.cancel_rate", "revenue.orders_per_day"},
}


def scenario_data(s: dict, seed: int):
    rng = np.random.default_rng(seed)
    base = base_daily("2024-01-01", "2026-02-28", rng)
    planted = plant(base, s, rng)
    return base, planted


def true_share(base, planted, s: dict) -> float | None:
    """ln(R1 / R1_counterfactual) / ln(R1 / R0): planted cause ne total log-change ka kitna hissa banaya."""
    if s["kind"] not in EXPECTED_KEYS:
        return None
    def tot(df, period):
        a, b = month_bounds(period)
        m = (df["city"] == s["city"]) & (df["date"] >= a) & (df["date"] < b)
        return float(df.loc[m, "revenue"].sum())
    r0, r1, r1cf = tot(planted, s["period_base"]), tot(planted, s["period_current"]), tot(base, s["period_current"])
    return math.log(r1 / r1cf) / math.log(r1 / r0)


def engine_for(df, path: str):
    if os.path.exists(path):
        os.remove(path)
    eng = create_engine(f"sqlite:///{path}")
    out = df.copy()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    out.to_sql("daily_sales", eng, index=False)
    return eng


def localized(report, s: dict) -> bool:
    """Planted segment sahi pakda gaya? (dimension drill-down / mix segment ka top segment == planted category)."""
    if s["kind"] != "mix_shift":
        return False
    for f in report.findings:
        if f.status in SUPPORTED_LIKE and f.data.get("dimension") == "category" and \
                (f.data.get("top_segment") == s["category"] or f.data.get("segment") == s["category"]):
            return True
    return False


def evaluate(report, s: dict, truth: float | None, k: int = 3) -> dict:
    expected = EXPECTED_KEYS.get(s["kind"], set())
    ranked = [f.hypothesis_id for f in report.ranked_supported()]
    ranked += [f.hypothesis_id for f in sorted(report.findings, key=lambda f: -f.share_of_delta)
               if f.source == "drilldown" and f.status in SUPPORTED_LIKE and f.hypothesis_id not in ranked]
    non_cal = [x for x in ranked if not x.endswith(".days")]
    rec = {"id": s["id"], "kind": s["kind"], "city": s["city"], "status": report.status,
           "gate_z": report.verify["gate"].get("z"), "gate_method": report.verify["gate"].get("method"),
           "ranked": ranked, "queries": report.budget.get("queries"), "llm_calls": report.budget.get("llm_calls"),
           "ms": report.duration_ms, "grounding_violations": report.grounding.get("violations", 0)}
    # Ch 18 Evidence Coverage: claims jinke saare evidence_node_ids graph me maujood hain
    node_ids = {n["id"] for n in report.graph.get("nodes", [])}
    linked = [bool(c.evidence_node_ids) and all(i in node_ids for i in c.evidence_node_ids) for c in report.claims]
    rec["evidence_coverage"] = sum(linked) / len(linked) if linked else 0.0
    # Ch 18 Investigation Completion: expected exit/steps tak pahuncha (verify -> ... -> report + claims)
    phases = {st["phase"] for st in report.steps}
    needed = {"Q", "V", "Rec"} | ({"T", "R", "A"} if report.status == "completed" else set())
    rec["completed_ok"] = needed <= phases and bool(report.claims)
    if s["kind"] in EXPECTED_KEYS:
        rec["detected"] = report.status == "completed"
        loc = localized(report, s)
        hit = lambda x: x in expected or (loc and "category" in x)  # noqa: E731
        rec["recall@1"] = bool(non_cal[:1]) and hit(non_cal[0])
        rec[f"recall@{k}"] = any(hit(x) for x in ranked[:k])
        rec["segment_localized"] = loc if s["kind"] == "mix_shift" else None
        fr = {f.hypothesis_id: f for f in report.findings}
        pred = sum(max(0.0, fr[x].share_of_delta) for x in report.frontier
                   if x in expected and fr[x].status in SUPPORTED_LIKE)
        dim_f = fr.get("revenue.dim:category")
        if loc and dim_f is not None and dim_f.data.get("top_segment") == s.get("category"):
            pred = max(0.0, dim_f.share_of_delta)   # planted segment ka contribution = cause ka seedha estimate
        rec["true_share"], rec["pred_share"] = truth, pred if report.status == "completed" else 0.0
        rec["attr_error"] = attribution_error({"cause": rec["pred_share"]}, {"cause": truth})
        rec["false_findings"] = [x for x in non_cal if not hit(x)]
    elif s["kind"] == "noise_only":
        rec["false_alarm"] = report.status == "completed" and bool(non_cal)
        rec["gate_fired"] = report.status not in ("within_normal",)
    elif s["kind"] == "missing_days":
        rec["data_issue_detected"] = report.status == "data_issue"
    # calibration labels
    rec["labels"] = []
    if report.status == "completed":
        for f in report.findings:
            if f.score is None or not f.components:
                continue
            seg = f.data.get("top_segment") or f.data.get("segment")
            correct = f.hypothesis_id.endswith(".days") or f.hypothesis_id in expected or \
                (f.hypothesis_id.split(">")[0] in expected and f.source != "drilldown") or \
                (f.source == "drilldown" and s["kind"] == "mix_shift" and seg == s.get("category"))
            rec["labels"].append({"key": f.hypothesis_id, "components": f.components, "score": f.score,
                                  "correct": int(correct)})
    return rec


def aggregate(recs: list[dict], k: int = 3) -> dict:
    def mean(xs):
        xs = [x for x in xs if x is not None]
        return float(np.mean(xs)) if xs else None
    planted = [r for r in recs if r["kind"] in EXPECTED_KEYS]
    noise = [r for r in recs if r["kind"] == "noise_only"]
    missing = [r for r in recs if r["kind"] == "missing_days"]
    labels = [lab for r in recs for lab in r["labels"]]
    supported_non_cal = sum(len(r.get("false_findings", [])) for r in planted)
    return {
        "scenarios": len(recs),
        "detection_rate": mean([r["detected"] for r in planted]),
        "segment_localized_given_detected": mean([r["segment_localized"] for r in planted
                                                  if r["kind"] == "mix_shift" and r["detected"]]),
        "recall@1": mean([r["recall@1"] for r in planted]),
        f"recall@{k}": mean([r[f"recall@{k}"] for r in planted]),
        f"recall@{k}_given_detected": mean([r[f"recall@{k}"] for r in planted if r["detected"]]),
        "attribution_error": mean([r["attr_error"] for r in planted if r["detected"]]),
        "false_alarm_rate": mean([r["false_alarm"] for r in noise]),
        "gate_fire_rate_noise": mean([r["gate_fired"] for r in noise]),
        "data_issue_detection": mean([r["data_issue_detected"] for r in missing]),
        "false_findings_per_planted": supported_non_cal / len(planted) if planted else None,
        "grounding_violations": sum(r.get("grounding_violations", 0) for r in recs),
        "investigation_completion": mean([r["completed_ok"] for r in recs]),
        "evidence_coverage": mean([r.get("evidence_coverage") for r in recs]),
        "reproducibility": mean([r.get("repro") for r in recs]),
        "errors": sum(r["status"] == "error" for r in recs),
        "avg_queries": mean([r.get("queries") for r in recs]),
        "avg_llm_calls": mean([r.get("llm_calls") for r in recs]),
        "avg_ms": mean([r.get("ms") for r in recs]),
        "brier": brier([x["score"] for x in labels], [x["correct"] for x in labels]) if labels else None,
        "ece": ece([x["score"] for x in labels], [x["correct"] for x in labels]) if labels else None,
        "labelled_findings": len(labels),
        "by_kind": {kind: sum(r["kind"] == kind for r in recs) for kind in
                    ("mix_shift", "cancel_spike", "missing_days", "noise_only")},
    }


def run_benchmark(n: int, seed: int = 0, config: QTraceConfig | None = None, workdir: str | None = None,
                  verbose: bool = False, repro: int = 10) -> tuple[dict, list[dict]]:
    workdir = workdir or tempfile.mkdtemp(prefix="qh_bench_")
    scenarios = make_scenarios(n, np.random.default_rng(seed))
    layer = SemanticLayer(daily_sales_metrics())
    recs = []
    for i, s in enumerate(scenarios):
        base, planted = scenario_data(s, seed * 10_000 + i)
        eng = engine_for(planted, os.path.join(workdir, f"{s['id']}.db"))
        spec = QuestionSpec(metric="revenue", filters={"city": s["city"]}, period_current=s["period_current"],
                            period_base=s["period_base"], period_yoy="2025-02", intent="root_cause")
        t0 = time.perf_counter()
        try:
            report = QTracePlus(eng, layer, role="analyst", config=config).run(spec=spec)
        except Exception as e:  # noqa: BLE001 — Investigation Completion metric ke liye record karo
            recs.append({"id": s["id"], "kind": s["kind"], "city": s["city"], "status": "error",
                         "error": f"{e.__class__.__name__}: {e}", "labels": [], "completed_ok": False})
            eng.dispose()
            continue
        rec = evaluate(report, s, true_share(base, planted, s))
        rec["wall_s"] = round(time.perf_counter() - t0, 2)
        # Ch 18 Reproducibility: pehle `repro` completed scenarios dobara chalao — findings same?
        if report.status == "completed" and sum(r.get("repro") is not None for r in recs) < repro:
            again = QTracePlus(eng, layer, role="analyst", config=config).run(spec=spec)
            sig = lambda r: sorted((f.hypothesis_id, f.status.value, round(f.share_of_delta, 9)) for f in r.findings)  # noqa: E731
            rec["repro"] = sig(report) == sig(again)
        recs.append(rec)
        eng.dispose()
        if verbose:
            print(f"{s['id']} {s['kind']:13s} {s['city']:7s} -> {report.status:13s} z={rec['gate_z']}"
                  f" top={rec['ranked'][:3]}")
    return aggregate(recs), recs


def fast_config(**kw) -> QTraceConfig:
    return QTraceConfig(n_boot=600, n_perm=600, **kw)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", type=int, default=50)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--fast", action="store_true", help="kam bootstrap draws (CI smoke run)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    cfg = fast_config() if args.fast else QTraceConfig()
    t0 = time.time()
    summary, recs = run_benchmark(args.scenarios, args.seed, cfg, verbose=args.verbose)
    summary.update(seed=args.seed, fast=args.fast, seconds=round(time.time() - t0, 1),
                   generated_at=time.strftime("%Y-%m-%d %H:%M:%S"))
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "benchmark_latest.json").write_text(json.dumps({"summary": summary, "scenarios": recs}, indent=2,
                                                              default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
