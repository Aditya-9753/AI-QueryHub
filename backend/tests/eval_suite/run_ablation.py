"""Ablation (Ch 18.3): same planted scenarios par components hata kar metrics compare.

    cd backend && python -m tests.eval_suite.run_ablation --scenarios 40 [--fast]

LLM-dependent variants (Baseline Text-to-SQL, LLM-only scoring) ke liye LLM key chahiye — yahan 'n/a'.
"""
import argparse
import json
import time

from tests.eval_suite.benchmark import RESULTS, fast_config, run_benchmark

VARIANTS = [
    ("Full", "Nothing", {}),
    ("-Verify", "Step V (anomaly gate / data health exit)", {"use_verify": False}),
    ("-Normalization", "Per-day (calendar factor)", {"per_day": False}),
    ("-Decomposition", "Log/mix split (naive ratio shares)", {"use_decomposition": False}),
    ("-FDR", "Benjamini-Hochberg (q = p)", {"use_fdr": False}),
    ("-Challenge", "Challenge battery", {"use_challenge": False}),
]
METRICS = ["detection_rate", "recall@3", "attribution_error", "false_alarm_rate", "data_issue_detection",
           "false_findings_per_planted", "brier", "grounding_violations", "avg_queries"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", type=int, default=40)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--fast", action="store_true")
    args = ap.parse_args()
    rows = []
    for name, removed, flags in VARIANTS:
        cfg = fast_config(**flags) if args.fast else __import__("app.services.orchestrator.qtrace",
                                                                fromlist=["QTraceConfig"]).QTraceConfig(**flags)
        summary, _ = run_benchmark(args.scenarios, args.seed, cfg)
        rows.append({"variant": name, "removed": removed, **{m: summary.get(m) for m in METRICS}})
        print(f"{name:16s}", "  ".join(f"{m}={summary.get(m) if not isinstance(summary.get(m), float) else round(summary[m], 3)}"
                                       for m in METRICS))
    rows += [{"variant": "Baseline (LLM Text-to-SQL)", "removed": "Q-TRACE+ layer", "note": "n/a — LLM key chahiye"},
             {"variant": "LLM-only scoring", "removed": "Evidence Score", "note": "n/a — LLM key chahiye"}]
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "ablation_latest.json").write_text(json.dumps(
        {"scenarios": args.scenarios, "seed": args.seed, "fast": args.fast,
         "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "rows": rows}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
