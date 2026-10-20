"""Ch 10 worked example ka exact dataset + pipeline run (Ch 13.8 jaisa output).

    cd backend && python -m tests.eval_suite.worked_example

Delhi Jan 2026: 10,000 orders / 31 din (E 30% @10,000, F 30% @4,000, G 40% @2,000) = Rs 5.00 Cr
Delhi Feb 2026:  9,000 orders / 28 din (E 24% @9,800, F 32% @4,000, G 44% @2,000) = Rs 4.06 Cr
Controls Mumbai/Pune: per-day -2.0%;  payments path = revenue x 0.992 (0.8% diff);  history 2023-01 se.
Pipeline ko ye numbers pata nahi — sab SQL + maths se nikalta hai.
"""
import math
import os
import tempfile

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

from app.schemas.qtrace import QuestionSpec
from app.services.orchestrator.qtrace import QTraceConfig, QTracePlus
from app.services.rag.semantic_layer import MetricDef, SemanticLayer, daily_sales_metrics

AOV0 = {"Electronics": 10_000, "Fashion": 4_000, "Grocery": 2_000}
SHARE0 = {"Electronics": 0.30, "Fashion": 0.30, "Grocery": 0.40}
JAN_SEASON = 1 + 0.08 * math.sin(2 * math.pi * (1 - 4) / 12)      # = 0.92
# Delhi ka Jan per-day level (10,000/31) apni seasonal history se consistent: expected Feb ~ Rs 15.9 L/din
CITY_LEVEL = {"Delhi": 10_000 / 31 / JAN_SEASON, "Mumbai": 1.1 * 10_000 / 31 / JAN_SEASON,
              "Pune": 0.9 * 10_000 / 31 / JAN_SEASON}


def _allocate(total: int, weights: np.ndarray, rng) -> np.ndarray:
    """total ko days me weights ke hisaab se integer allocate (sum exact)."""
    return rng.multinomial(total, weights / weights.sum())


def build_frames(seed: int = 7) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    rows = []
    months = pd.period_range("2023-01", "2026-02", freq="M")
    for city, level in CITY_LEVEL.items():
        for p in months:
            days = pd.date_range(p.start_time, p.end_time.normalize(), freq="D")
            season = 1 + 0.08 * math.sin(2 * math.pi * (p.month - 4) / 12)
            per_day = level * season
            if p.month == 2:                       # har saal Jan -> Feb per-day -1.5% (seasonal)
                per_day = level * (1 + 0.08 * math.sin(2 * math.pi * (1 - 4) / 12)) * 0.985
            share, aov = dict(SHARE0), dict(AOV0)
            if city == "Delhi" and str(p) == "2026-01":
                totals = {"Electronics": 3000, "Fashion": 3000, "Grocery": 4000}
            elif city == "Delhi" and str(p) == "2026-02":
                totals = {"Electronics": 2160, "Fashion": 2880, "Grocery": 3960}
                aov["Electronics"] = 9_800
            else:
                if str(p) == "2026-02":            # controls: per-day -2% vs Jan 2026
                    jan = level * (1 + 0.08 * math.sin(2 * math.pi * (1 - 4) / 12))
                    per_day = jan * 0.98
                n = int(round(per_day * len(days)))
                totals = {c: int(round(n * s)) for c, s in share.items()}
            weekly = np.where(days.dayofweek >= 5, 1.15, 0.95) * rng.lognormal(0, 0.10, len(days))
            for cat, tot in totals.items():
                alloc = _allocate(tot, weekly * rng.lognormal(0, 0.05, len(days)), rng)
                for d, o in zip(days, alloc):
                    rows.append({"date": d.date().isoformat(), "city": city, "category": cat, "orders": int(o),
                                 "cancelled": 0, "revenue": float(o * aov[cat])})
    df = pd.DataFrame(rows)
    pay = df.groupby(["date", "city"], as_index=False)["revenue"].sum()
    pay["amount"] = (pay["revenue"] * 0.992).round(2)
    return df, pay[["date", "city", "amount"]]


def layer() -> SemanticLayer:
    pay = MetricDef("payments_revenue", "Payments path", "daily_payments", "SUM(amount)", time_column="date",
                    dimensions=("city",), key_columns=("date", "city"), required_columns=("amount", "city"),
                    updated_column=None, unit="inr")
    return SemanticLayer(daily_sales_metrics() + [pay])


_ENGINES: dict[int, object] = {}


def build_engine(path: str | None = None, seed: int = 7):
    if path is None and seed in _ENGINES:       # same data => reuse (Windows open-file lock se bachne ke liye)
        return _ENGINES[seed]
    path = path or os.path.join(tempfile.gettempdir(), f"qh_worked_example_{seed}_{os.getpid()}.db")
    if os.path.exists(path):
        os.remove(path)
    engine = create_engine(f"sqlite:///{path}")
    df, pay = build_frames(seed)
    df.to_sql("daily_sales", engine, index=False)
    pay.to_sql("daily_payments", engine, index=False)
    _ENGINES[seed] = engine
    return engine


SPEC = QuestionSpec(metric="revenue", filters={"city": "Delhi"}, period_current="2026-02", period_base="2026-01",
                    period_yoy="2025-02", intent="root_cause")


def run(config: QTraceConfig | None = None, engine=None):
    return QTracePlus(engine or build_engine(), layer(), role="analyst", config=config).run(spec=SPEC)


def main() -> None:
    r = run()
    c = r.core
    L = 1e5
    print(f"status {r.status}  gate {r.verify['gate']['method']} z={r.verify['gate']['z']:.2f}  "
          f"Jan {c['T0'] / 1e7:.2f} Cr -> Feb {c['T1'] / 1e7:.2f} Cr ({c['rel_change']:+.1%}), per-day {c['per_day_change']:+.1%}")
    for d in r.decomposition:
        print(f"{d['factor']:15s} share {d['share']:6.1%}   amount {d['amount'] / L:8.2f} lakh   ({d['method']})")
    mix = r.finding("revenue.category_mix")
    if mix:
        print(f"mix/rate        mix {mix.data['mix']:.1f}  rate {mix.data['rate']:.1f}  total {mix.data['mix'] + mix.data['rate']:.1f}")
    conc = r.finding("tpl.concurrent_event")
    if conc and conc.data.get("did") is not None:
        print(f"DiD             {conc.data['did']:.4f}  CI [{conc.data['did_ci'][0]:.4f}, {conc.data['did_ci'][1]:.4f}]  "
              f"controls {conc.data['controls']} {conc.data['control_change']:+.1%}")
    for f in r.findings:
        print(f"  {f.hypothesis_id:42s} {f.status.value:11s} share {f.share_of_delta:+.3f}  q={f.q_value if f.q_value is None else round(f.q_value, 4)}"
              f"  score={f.score} {f.label or ''}")
    print(f"stop: {r.stop_reason}  explained {r.explained:.1%}  residual {r.residual_share:.1%}  CQA {r.reconciliation.get('cqa')}")
    print(f"grounding violations: {r.grounding['violations']}  queries: {len(r.queries)}  {r.duration_ms:.0f} ms")
    for cl in r.claims:
        print(f"  [{cl.claim_type}] {cl.sentence}")


if __name__ == "__main__":
    main()
