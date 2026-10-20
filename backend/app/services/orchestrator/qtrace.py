"""Q-TRACE+ pipeline:  V -> Q -> T -> (R -> A)* -> C -> Ch -> E -> X   (Ch 8; record: experiments/recorder.py)

Har number semantic-layer SQL + numpy/scipy/statsmodels se aata hai. LLM optional hai (question parse fallback,
extra hypotheses, narrative) aur uske output ke numbers grounding validator (F33) se check hote hain.

Formulas: F2 log decomposition, F4 mix/rate, F7 per-day, F8/F9 ETS band + z, F10 YoY, F11 DiD, F16 n_req,
F17 block bootstrap, F18 permutation, F19 BH-FDR, F21-F26 evidence score, F27 priority, F28 stop, F29 EP+JS.
"""
from __future__ import annotations

import json
import math
import re
import time
import zlib
from dataclasses import dataclass, field
from datetime import date, datetime

import numpy as np
import pandas as pd
from scipy import stats as sps

from app.schemas.qtrace import SUPPORTED_LIKE, Claim, Finding, Hypothesis, HypStatus, QuestionSpec
from app.services.analytics.baseline import rel_se
from app.services.analytics.decomposition import log_decomposition, mix_rate, shapley
from app.services.analytics.did import diff_in_diff, parallel_trends_test, pre_trend_gap, select_controls
from app.services.analytics.fdr import benjamini_hochberg
from app.services.analytics.resampling import block_bootstrap, bootstrap_pvalue, permutation_test
from app.services.analytics.statistics import required_n
from app.services.challenge.battery import run_challenge_battery
from app.services.challenge.resolver import contradiction_penalty, resolve
from app.services.evidence.claims import regenerate_or_strip
from app.services.evidence.graph import EvidenceGraph
from app.services.evidence.grounding_validator import numbers_in, numeric_grounding_ok, strip_ungrounded
from app.services.evidence.narrative import build_claims, evidence_values
from app.services.evidence.provenance import build_provenance
from app.services.evidence.scorer import (
    cross_query_agreement,
    data_coverage,
    evidence_score,
    explained_share,
    sample_adequacy,
    statistical_strength,
)
from app.services.experiments.versioning import schema_snapshot_hash
from app.services.hypothesis_engine.drilldown import drilldown_hypotheses, rank_dimensions
from app.services.hypothesis_engine.generator import generate_hypotheses
from app.services.hypothesis_engine.metric_tree import children_of, needs_dimension
from app.services.llm.llm_client import LLMError
from app.services.llm.prompt_builder import explain_prompt
from app.services.orchestrator.budget import Budget
from app.services.orchestrator.data_access import DataAccess
from app.services.orchestrator.priority import HypothesisQueue
from app.services.orchestrator.question_parser import parse_question
from app.services.orchestrator.stopping import should_drilldown, stop_reason
from app.services.rag.semantic_layer import SemanticLayer, month_bounds, period_days, shift_period
from app.services.verify.anomaly_gate import anomaly_gate
from app.services.verify.data_health import (
    HealthReport,
    health_queries,
    outlier_check,
    run_data_health,
    volume_query,
)

METRIC_INPUTS = {"revenue": ("revenue", "orders", "placed_orders"), "orders": ("orders", "placed_orders")}
FACTOR_LABELS = {
    "days": "Calendar (din)", "orders_per_day": "Orders per day", "orders": "Total orders", "aov": "AOV",
    "placed_orders": "Placed orders", "cancel_rate": "Cancellation rate", "category_mix": "Mix shift",
    "segment_aov": "Within-segment AOV (rate)", "seasonality": "Seasonality", "data_issue": "Data issue",
    "concurrent_event": "Market-wide (controls)", "price_change": "Price change", "calendar": "Calendar",
}


class UnsupportedQuestion(ValueError):
    pass


@dataclass
class QTraceConfig:
    use_verify: bool = True           # ablation "-Verify": gate compute hota hai, early exit nahi
    per_day: bool = True              # ablation "-Normalization"
    use_decomposition: bool = True    # ablation "-Decomposition": naive ratio shares, no mix/rate split
    use_fdr: bool = True              # ablation "-FDR": q = p
    use_challenge: bool = True
    llm_extras: bool = True
    llm_narrative: bool = True
    fdr_q: float = 0.10
    explained_target: float = 0.80
    z_threshold: float = 1.96
    mde_rel: float = 0.10             # relative effects (per-day, AOV): 10% change "matter" karta hai
    mde_share: float = 0.05           # share / proportion: 5 percentage points
    mde_rate: float = 0.02            # cancellation rate: 2 points
    n_boot: int = 2000
    n_perm: int = 2000
    history_months: int = 36
    control_months: int = 12
    min_ets_months: int = 24
    max_segments: int = 2
    pre_trend_tolerance: float = 0.03


@dataclass(frozen=True)
class Period:
    label: str
    period: str

    @property
    def start(self) -> str:
        return month_bounds(self.period)[0]

    @property
    def end(self) -> str:
        return month_bounds(self.period)[1]

    @property
    def days(self) -> int:
        return period_days(self.period)

    @property
    def index(self) -> pd.DatetimeIndex:
        return pd.date_range(self.start, periods=self.days, freq="D")


@dataclass
class InvestigationReport:
    status: str                                   # completed | data_issue | within_normal | no_change
    question: str | None
    spec: QuestionSpec
    parse_source: str = "spec"
    verify: dict = field(default_factory=dict)
    core: dict = field(default_factory=dict)
    decomposition: list[dict] = field(default_factory=list)
    hypotheses: list[Hypothesis] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    frontier: list[str] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    graph: dict = field(default_factory=dict)
    queries: list = field(default_factory=list)
    llm_calls: list = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)
    stop_reason: str | None = None
    residual_share: float | None = None
    explained: float | None = None
    controls: list[str] = field(default_factory=list)
    dimension_ranking: list[dict] = field(default_factory=list)
    reconciliation: dict = field(default_factory=dict)
    simpson: dict = field(default_factory=dict)
    grounding: dict = field(default_factory=dict)
    budget: dict = field(default_factory=dict)
    duration_ms: float = 0.0
    notes: list[str] = field(default_factory=list)
    dataset_version: str | None = None
    schema_snapshot: str | None = None

    def finding(self, key: str) -> Finding | None:
        return next((f for f in self.findings if f.hypothesis_id == key), None)

    def ranked_supported(self) -> list[Finding]:
        """Frontier supported findings, share ke hisaab se (Recall@k ke liye)."""
        fs = [self.finding(k) for k in self.frontier]
        return sorted([f for f in fs if f and f.status in SUPPORTED_LIKE], key=lambda f: -f.share_of_delta)

    def summary(self) -> dict:
        def _f(f: Finding) -> dict:
            d = f.model_dump(mode="json")
            d["key"] = f.hypothesis_id
            return d
        return _jsonable({
            "status": self.status, "question": self.question, "spec": self.spec.model_dump(),
            "parse_source": self.parse_source, "verify": self.verify, "core": self.core,
            "decomposition": self.decomposition,
            "hypotheses": [h.model_dump(mode="json") for h in self.hypotheses],
            "findings": [_f(f) for f in self.findings], "frontier": self.frontier,
            "claims": [c.model_dump() for c in self.claims], "graph": self.graph,
            "queries": [q.to_dict() for q in self.queries],
            "stop_reason": self.stop_reason, "residual_share": self.residual_share, "explained": self.explained,
            "controls": self.controls, "dimension_ranking": self.dimension_ranking,
            "reconciliation": self.reconciliation, "simpson": self.simpson, "grounding": self.grounding,
            "budget": self.budget, "duration_ms": self.duration_ms, "notes": self.notes,
            "dataset_version": self.dataset_version, "schema_snapshot": self.schema_snapshot,
            "steps": self.steps,
        })


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.floating, float)):
        v = float(o)
        return v if math.isfinite(v) else None
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (datetime, date, pd.Timestamp)):
        return o.isoformat()
    return o


def _calendar_series(df: pd.DataFrame, col: str, idx: pd.DatetimeIndex) -> pd.Series:
    s = df.groupby("day")[col].sum() if not df.empty else pd.Series(dtype=float)
    return s.reindex(idx, fill_value=0.0).astype(float)


def _calendar_pivot(df: pd.DataFrame, dim: str, col: str, idx: pd.DatetimeIndex) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(index=idx)
    p = df.pivot_table(index="day", columns=dim, values=col, aggfunc="sum", fill_value=0.0)
    return p.reindex(idx, fill_value=0.0).astype(float)


def _ci_excludes_zero(ci) -> bool:
    return ci is not None and not (ci[0] <= 0 <= ci[1])


def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


class QTracePlus:
    def __init__(self, engine, layer: SemanticLayer | None = None, role: str = "analyst", llm=None,
                 config: QTraceConfig | None = None, budget: Budget | None = None, as_of: str | None = None,
                 on_step=None) -> None:
        self.layer = layer or SemanticLayer()
        self.cfg = config or QTraceConfig()
        self.budget = budget or Budget.from_settings()
        self.engine, self.role, self.llm = engine, role, llm
        # Ch 17: as_of = run ka snapshot time; har semantic query me `updated_at <= as_of` (jahan column ho)
        self.as_of = as_of or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.on_step = on_step
        self.da = DataAccess(engine, self.layer, role, self.budget, as_of=self.as_of)
        self.data_through: str | None = None
        self.llm_calls: list[tuple[str, str, object]] = []
        self.steps: list[dict] = []
        self.notes: list[str] = []
        self.hypotheses: dict[str, Hypothesis] = {}
        self.findings: dict[str, Finding] = {}
        self.shares: dict[str, float] = {}
        self.segcache: dict[str, dict] = {}
        self.mixcache: dict[str, dict] = {}
        self.dim_ranking: list[dict] = []
        self.controls: list[str] = []
        self.control_info: dict = {}
        self.reconciliation: dict = {}
        self.simpson: dict = {}
        self.cqa = 0.5
        self.yoy: dict | None = None

    # ================================================================== public
    def run(self, question: str | None = None, spec: QuestionSpec | None = None) -> InvestigationReport:
        t0 = time.perf_counter()
        parse_source = "spec"
        if spec is None:
            spec, parse_source = self.decompose(question or "")
        if spec.metric not in METRIC_INPUTS:
            raise UnsupportedQuestion(f"INVESTIGATE abhi '{', '.join(METRIC_INPUTS)}' metrics ke liye hai "
                                      f"(mila: {spec.metric})")
        self.spec, self.question = spec, question
        self.metric = self.layer.get(spec.metric)
        self.P = {lbl: Period(lbl, p) for lbl, p in (
            ("current", spec.period_current), ("base", spec.period_base),
            ("yoy_current", spec.period_yoy or shift_period(spec.period_current, -12)),
            ("yoy_base", shift_period(spec.period_base, -12)))}
        self._step("Q", "question_spec", to="parsed", ref=parse_source)

        # ---------------------------------------------------------- V: verify
        self.health = self.verify_health()
        self.gate = self.verify_anomaly()
        self._step("V", "data_health", to="pass" if self.health.ok else "data_issue")
        self._step("V", "anomaly_gate", to=self.gate["status"])
        report = InvestigationReport(status="completed", question=question, spec=spec, parse_source=parse_source)
        report.verify = {"health": self.health.to_dict(), "gate": self.gate}
        if not self.health.ok and self.cfg.use_verify:
            return self._finish(report, "data_issue", t0)
        if self.gate["status"] == "within_normal" and self.cfg.use_verify:
            return self._finish(report, "within_normal", t0)

        # ---------------------------------------------------------- Q: normalize + controls
        self._load_core()
        if abs(self.dlnR) < 1e-12:
            return self._finish(report, "no_change", t0)
        self.controls = self.pick_controls()
        self.spec = spec = spec.model_copy(update={"controls": self.controls,
                                                   "normalize": "per_day" if self.cfg.per_day else "none"})
        report.spec = spec

        # ---------------------------------------------------------- T: hypotheses
        skip = set() if self.cfg.per_day else {"calendar"}
        extras = self._llm_extras if (self.llm is not None and self.cfg.llm_extras) else None
        hyps = generate_hypotheses(spec, llm_extras=extras, layer=self.layer, per_day=self.cfg.per_day,
                                   skip_templates=skip)
        hyps += [Hypothesis(id=f"{spec.metric}.dim:{d}", statement=f"{d.title()}-wise: change kisi segment me "
                            "concentrated hai", metric=spec.metric, dimensions=[d], source="drilldown", prior=0.4,
                            test_type="chi2", status=HypStatus.GROUNDED) for d in self._candidate_dims()]
        queue = HypothesisQueue()
        for h in hyps:
            self._describe(h)
            self.hypotheses[h.id] = h
            if h.status == HypStatus.UNGROUNDED:
                self._step("T", "hypothesis", ref=h.id, to="ungrounded")
                continue
            queue.push(h, exp_share=self.exp_share(h), cost=self.cost(h))
            self._step("T", "hypothesis", ref=h.id, frm="proposed", to=h.status.value)

        # ---------------------------------------------------------- (R -> A)* loop
        while True:
            # Top-level tree factors (F2 decomposition, 0 extra queries) aur pending drill-downs hamesha poore hote hain;
            # F28 stop rule baaki (templates / LLM extras) par lagta hai.
            pending = any(h.depth > 0 or (h.source == "metric_tree" and h.parent_id is None) for h in queue.items())
            reason = stop_reason(self.explained(), self.budget, not queue, self.cfg.explained_target,
                                 pending_refinements=pending)
            if reason:
                break
            h = queue.pop()
            self._step("R", "hypothesis", ref=h.id, frm=h.status.value, to="planned")
            f = self.test(h)
            self.findings[h.id] = f
            h.status = f.status
            self._step("A", "hypothesis", ref=h.id, frm="tested", to=f.status.value)
            # F28/8.5: drill-down sirf share se (> 30%, depth < 2) — parent ka CI significant hona zaroori nahi.
            # Daily-series test (orders/day) low-power hota hai; uske children (cancel rate: chi2 on counts) zyada
            # powerful hain, isliye unhe test hone do.
            if f.status != HypStatus.INCONCLUSIVE and should_drilldown(self._drill_share(f), h.depth):
                for c in self.refine(h, f):
                    self._describe(c)
                    self.hypotheses[c.id] = c
                    queue.push(c, exp_share=self.exp_share(c), cost=self.cost(c))
                    self._step("T", "drilldown", ref=c.id, frm="proposed", to="grounded")
        for h in queue.items():
            h.status = HypStatus.NOT_TESTED
        self.stop = reason

        # ---------------------------------------------------------- C / Ch / E / X
        self.cross_check()
        if self.cfg.use_challenge:
            self.challenge()
        self.score()
        return self._finish(report, "completed", t0)

    # ================================================================== Q: decompose
    def decompose(self, question: str) -> tuple[QuestionSpec, str]:
        from app.services.rag.schema_context import schema_snapshot

        tables = {t.name: t for t in schema_snapshot(self.engine, self.role)}
        values: dict[str, list[str]] = {}
        latest: date | None = None
        for m in self.layer.metrics():
            t = tables.get(m.table)
            if t is None:
                continue
            for c in t.columns:
                if c.name in m.dimensions and c.values:
                    values.setdefault(c.name, sorted(set(values.get(c.name, [])) | set(c.values)))
                if c.name == m.time_column and c.max and m.name == "revenue":
                    latest = datetime.fromisoformat(str(c.max)[:10]).date()
        llm = self.llm if self.llm is not None else None
        spec, source, _ = parse_question(question, self.layer, values, latest, llm=llm)
        if source == "llm":
            self.budget.spend_llm()
        return spec, source

    # ================================================================== V: verify
    def verify_health(self, extra_filters: dict | None = None, purpose: str = "V:health") -> HealthReport:
        cur = self.P["current"]
        filters = {**self.spec.filters, **(extra_filters or {})}
        q = health_queries(self.metric, cur.start, cur.end, filters, as_of=self.as_of)
        prov = {"table": self.metric.table, "metric": self.metric.name, "filters": filters,
                "time_window": [cur.start, cur.end], "metric_definition": self.da.definition(self.metric.name)}
        stats: dict = {"expected_days": cur.days, "period_end": datetime.fromisoformat(cur.end)}
        stats["days_with_data"] = int(self.da.scalar(q["days_with_data"], f"{purpose}:days", **prov) or 0)
        stats["null_rate"] = float(self.da.scalar(q["null_rate"], f"{purpose}:nulls", **prov) or 0.0)
        stats["duplicate_count"] = int(self.da.scalar(q["duplicate_count"], f"{purpose}:duplicates", **prov) or 0)
        if "max_updated_at" in q:
            mu = self.da.scalar(q["max_updated_at"], f"{purpose}:freshness", **prov)
            if mu is not None:
                ts = pd.Timestamp(mu)
                stats["max_updated_at"] = (ts.tz_localize(None) if ts.tzinfo else ts).to_pydatetime()
                if extra_filters is None:
                    self.data_through = stats["max_updated_at"].isoformat(sep=" ")
        if extra_filters is None:
            vstart = Period("v", shift_period(cur.period, -12)).start
            res, _ = self.da.run(volume_query(self.metric, vstart, cur.end, filters, as_of=self.as_of),
                                 f"{purpose}:volume", **{**prov, "time_window": [vstart, cur.end]})
            vol = pd.DataFrame(res.all_rows, columns=["day", "n"])
            if not vol.empty:
                vol["day"] = pd.to_datetime(vol["day"])
                monthly = vol.groupby(vol["day"].dt.to_period("M"))["n"].sum()
                cur_p = pd.Period(cur.period, "M")
                hist = [float(monthly[p]) / p.days_in_month for p in monthly.index if p < cur_p]
                stats["history_counts"] = hist[-12:]
                stats["row_count"] = float(monthly.get(cur_p, 0.0)) / cur.days
        return run_data_health(stats)

    def verify_anomaly(self) -> dict:
        """F8/F9 (ETS band, >= 24 months) ya F10 YoY z (kam history). Primary metric ki poori history ek query."""
        cur = self.P["current"]
        hstart = Period("h", shift_period(cur.period, -self.cfg.history_months)).start
        df, rec = self.da.daily(self.metric.name, self.spec.filters, hstart, cur.end, purpose="V:history")
        idx = pd.date_range(hstart, Period("x", cur.period).index[-1], freq="D")
        self.H = _calendar_series(df, self.metric.name, idx)
        self.H_present = set(df["day"]) if not df.empty else set()
        self.history_query = rec.id

        months = []
        p = pd.Period(cur.period, "M") - 1
        while True:     # trailing contiguous fully-covered months before current
            pidx = pd.date_range(p.start_time, p.end_time.normalize(), freq="D")
            if pidx[0] < idx[0]:
                break
            covered = sum(d in self.H_present for d in pidx) / len(pidx)
            if covered < 0.9:
                break
            months.append(float(self.H.loc[pidx].sum()) / len(pidx))
            p -= 1
        months.reverse()

        cur_vals = self.H.loc[cur.index].to_numpy()
        actual = float(cur_vals.mean())
        se = float(cur_vals.std(ddof=1) / math.sqrt(len(cur_vals))) if len(cur_vals) > 1 else 0.0
        self.yoy = self._yoy_stats()
        yoy_arrays = None
        if self.yoy is not None:
            yoy_arrays = tuple(self.H.loc[self.P[k].index].to_numpy()
                               for k in ("current", "base", "yoy_current", "yoy_base"))
        gate = anomaly_gate(actual, history=months, current_se=se, yoy_arrays=yoy_arrays,
                            z_threshold=self.cfg.z_threshold, min_ets_points=self.cfg.min_ets_months)
        gate["query_id"] = rec.id
        gate["months_available"] = len(months)
        gate["unit"] = self.metric.unit
        if self.data_through is None and self.H_present:
            self.data_through = max(self.H_present).date().isoformat()
        # F15: current period me extreme din (pichhle 90 din ke reference se) — warning
        ref = self.H.loc[self.H.index < pd.Timestamp(cur.start)].tail(90)
        ref = ref[[d in self.H_present for d in ref.index]]
        if len(ref) >= 28:
            self.health.checks.append(outlier_check(cur_vals.tolist(), ref.tolist()))
        return gate

    def _covered(self, label: str) -> bool:
        idx = self.P[label].index
        return sum(d in self.H_present for d in idx) / len(idx) >= 0.9

    def _yoy_stats(self) -> dict | None:
        if not all(self._covered(k) for k in ("current", "base", "yoy_current", "yoy_base")):
            return None
        arr = {k: self.H.loc[self.P[k].index].to_numpy() for k in ("current", "base", "yoy_current", "yoy_base")}
        if any(a.mean() <= 0 for a in arr.values()):
            return None
        ty = math.log(arr["current"].mean() / arr["base"].mean())
        ly = math.log(arr["yoy_current"].mean() / arr["yoy_base"].mean())
        se_ty = math.hypot(rel_se(arr["current"]), rel_se(arr["base"]))
        se_ly = math.hypot(rel_se(arr["yoy_current"]), rel_se(arr["yoy_base"]))
        return {"ty": ty, "ly": ly, "excess": ty - ly, "se_ty": se_ty, "se_ly": se_ly,
                "se_excess": math.hypot(se_ty, se_ly), "this_year_delta": math.exp(ty) - 1,
                "last_year_delta": math.exp(ly) - 1}

    # ================================================================== Q: core data + controls
    def _load_core(self) -> None:
        cur, base = self.P["current"], self.P["base"]
        start = min(self.P["yoy_base"].start, base.start)
        idx = pd.date_range(start, cur.index[-1], freq="D")
        D = pd.DataFrame(index=idx)
        self.core_queries: list[str] = [self.history_query]
        for m in METRIC_INPUTS[self.spec.metric]:
            if m not in self.layer.names():
                continue
            if m == self.metric.name:
                D[m] = self.H.reindex(idx, fill_value=0.0)
                continue
            df, rec = self.da.daily(m, self.spec.filters, start, cur.end, purpose=f"core:{m}")
            D[m] = _calendar_series(df, m, idx)
            self.core_queries.append(rec.id)
        self.D = D
        f0, f1 = self._factors("base"), self._factors("current")
        self.T0, self.T1 = math.prod(f0.values()), math.prod(f1.values())
        if self.T0 <= 0 or self.T1 <= 0:
            raise UnsupportedQuestion("base ya current period me data nahi hai")
        self.dlnR = math.log(self.T1 / self.T0)
        self.rel_total = self.T1 / self.T0 - 1
        self.factors0, self.factors1 = f0, f1
        if abs(self.dlnR) < 1e-12:
            return
        if self.cfg.use_decomposition:
            dec = log_decomposition(f0, f1)
            method = "log"
        else:
            dec = {k: {"share": (f1[k] / f0[k] - 1) / self.rel_total} for k in f0}
            method = "naive"
        self.decomp_rows: list[dict] = []
        for k, v in dec.items():
            hid = f"{self.spec.metric}.{k}"
            self.shares[hid] = v["share"]
            self.decomp_rows.append({"factor": k, "hypothesis": hid, "method": method, "share": v["share"],
                                     "amount": v["share"] * (self.T1 - self.T0), "depth": 0})
        # F5 cross-check: Shapley (order-independent) amounts — log decomposition ke saath compare
        self.shapley = shapley(lambda x: math.prod(x.values()), f0, f1)

    def _tot(self, m: str, label: str) -> float:
        return float(self.D.loc[self.P[label].index, m].sum())

    def _arr(self, m: str, label: str) -> np.ndarray:
        return self.D.loc[self.P[label].index, m].to_numpy(float)

    def _factors(self, label: str) -> dict[str, float]:
        d = self.P[label].days
        if self.spec.metric == "revenue":
            R, N = self._tot("revenue", label), self._tot("orders", label)
            if N <= 0:
                raise UnsupportedQuestion(f"{label} period me koi order nahi")
            return {"days": d, "orders_per_day": N / d, "aov": R / N} if self.cfg.per_day else \
                {"orders": N, "aov": R / N}
        N, pl = self._tot("orders", label), self._tot("placed_orders", label)
        if pl <= 0:
            raise UnsupportedQuestion(f"{label} period me koi order nahi")
        return {"days": d, "placed_orders": pl / d, "cancel_rate": N / pl} if self.cfg.per_day else \
            {"placed_orders": pl, "cancel_rate": N / pl}

    def pick_controls(self) -> list[str]:
        """8.3: same metric, pichhle 12 mahine me corr >= 0.8 aur size ratio 0.5-2.0. Na mile => DiD skip."""
        dims = [d for d in self.spec.filters if d in self.metric.dimensions]
        if not dims:
            self.notes.append("Koi filter dimension nahi — DiD ke liye controls nahi (market-wide check skip).")
            return []
        dim, target = dims[0], self.spec.filters[dims[0]]
        cur = self.P["current"]
        start = Period("c", shift_period(cur.period, -self.cfg.control_months)).start
        other = {k: v for k, v in self.spec.filters.items() if k != dim}
        df, rec = self.da.daily(self.metric.name, other, start, cur.end, group_by=(dim,), purpose="Q:controls")
        idx = pd.date_range(start, cur.index[-1], freq="D")
        piv = _calendar_pivot(df, dim, self.metric.name, idx)
        if target not in piv.columns:
            return []
        monthly = piv.groupby(piv.index.to_period("M")).mean()
        pre = monthly[monthly.index < pd.Period(cur.period, "M")]
        cands = {c: pre[c].tolist() for c in pre.columns if c != target}
        picked = select_controls(pre[target].tolist(), cands)
        self.control_daily = piv
        self.control_info = {"dimension": dim, "target": target, "query_id": rec.id, "candidates": list(cands)}
        if picked:
            t_series, c_series = pre[target].tolist(), pre[picked].mean(axis=1).tolist()
            pt = parallel_trends_test(t_series, c_series)
            self.control_info.update(pre_trend_gap=pre_trend_gap(t_series, c_series), parallel_trend=pt,
                                     parallel_ok=pt["ok"])
        else:
            self.notes.append("Controls nahi mile (corr >= 0.8, size 0.5-2x) — DiD skip.")
        return picked

    CONFOUNDERS = {"days": [], "seasonality": ["calendar"], "concurrent_event": ["seasonality"],
                   "data_issue": []}

    def _describe(self, h: Hypothesis) -> None:
        """Ch 6.1 Hypothesis object ke baaki fields: comparison_period, expected_direction, required_columns,
        confounders (jo is explanation ko 'fake' bana sakte hain — battery inhe check karti hai)."""
        key = h.id.split(".", 1)[-1].split(">")[0]
        m = self.layer.get(h.metric) if h.metric in self.layer.names() else self.metric
        h.comparison_period = f"{self.spec.period_base} -> {self.spec.period_current}"
        h.expected_direction = "down" if self.dlnR < 0 else "up"
        h.required_columns = sorted({m.time_column, *m.required_columns, *h.dimensions})
        h.confounders = self.CONFOUNDERS.get(key, ["calendar", "seasonality", "data_issue", "market_wide"])

    # ================================================================== priority helpers
    def exp_share(self, h: Hypothesis) -> float:
        if h.id in self.shares:
            return abs(self.shares[h.id])
        if h.source == "metric_tree" and h.parent_id:
            return abs(self.shares.get(h.parent_id, 0.3)) * 0.5
        key = h.id.split(".", 1)[-1]
        if key == "seasonality":
            return abs(self.yoy["ly"] / self.dlnR) if self.yoy else 0.05
        if key == "concurrent_event":
            return 0.3 if self.controls else 0.0
        if key == "data_issue":
            return 0.05
        return 0.3

    def cost(self, h: Hypothesis) -> float:
        key = h.id.split(".", 1)[-1]
        if key.startswith("dim:"):
            return 0.5 if h.dimensions and h.dimensions[0] in self.segcache else 2.0   # 2 segment queries
        if key in ("days", "data_issue", "seasonality", "concurrent_event") or h.source == "drilldown":
            return 0.5      # data pehle se fetched hai
        return 2.0 if h.source == "llm" else 1.0

    def _drill_share(self, f: Finding) -> float:
        """Drill-down threshold (30%) calendar hata kar wale change par: calendar pure arithmetic hai,
        'asli' (per-day) change me factor ka hissa dekho."""
        days = self.shares.get(f"{self.spec.metric}.days", 0.0) if self.cfg.per_day else 0.0
        if f.hypothesis_id.endswith(".days") or days >= 1 or days <= 0:
            return f.share_of_delta
        return f.share_of_delta / (1 - days)

    def explained_total(self) -> float:
        """Doc F28: sum(max(0, share_f)) supported frontier factors ka (calendar samet). Residual = 1 - ye."""
        return sum(max(0.0, f.share_of_delta) for f in self.frontier() if f.status in SUPPORTED_LIKE)

    def explained(self) -> float:
        """Stop rule ke liye: calendar (pure arithmetic) hata kar per-day change ka kitna hissa explain hua.
        Warna har Feb-vs-Jan sawaal calendar (~50-90%) par hi ruk jaata."""
        if not self.cfg.per_day:
            return self.explained_total()
        days = self.shares.get(f"{self.spec.metric}.days", 0.0)
        if 1 - days <= 0.05:          # per-day change ~0: calendar hi sab explain karta hai
            return 1.0
        rest = sum(max(0.0, f.share_of_delta) for f in self.frontier()
                   if f.status in SUPPORTED_LIKE and not f.hypothesis_id.endswith(".days"))
        return rest / (1 - days)

    def frontier(self) -> list[Finding]:
        out: list[Finding] = []

        def visit(key: str) -> None:
            f = self.findings.get(key)
            if f is None:
                return
            kids = [k for k, h in self.hypotheses.items() if h.parent_id == key and h.source == "metric_tree"]
            if kids and all(k in self.findings for k in kids):
                for k in kids:
                    visit(k)
            else:
                out.append(f)

        for key, h in self.hypotheses.items():
            if h.source == "metric_tree" and h.parent_id is None:
                visit(key)
        return out

    # ================================================================== R -> A: tests
    def _seed(self, key: str) -> int:
        return zlib.crc32(key.encode())

    def _boot(self, a, b, stat, key: str):
        draws = block_bootstrap(a, b, stat, block=7, n_boot=self.cfg.n_boot, seed=self._seed(key))
        fin = draws[np.isfinite(draws)]
        ci = (float(np.percentile(fin, 2.5)), float(np.percentile(fin, 97.5))) if len(fin) else (0.0, 0.0)
        return ci, bootstrap_pvalue(draws)

    def _finding(self, h: Hypothesis, *, share: float, effect: float, ci=None, p=None, method: str,
                 deterministic: bool = False, mde: float | None = None, statement: str | None = None,
                 claim_type: str = "association", data: dict | None = None, status: HypStatus | None = None,
                 notes: list[str] | None = None) -> Finding:
        notes = list(notes or [])
        if status is None:
            if deterministic:
                status = HypStatus.SUPPORTED if share > 0 else HypStatus.REJECTED
            elif _ci_excludes_zero(ci) and share > 0:
                status = HypStatus.SUPPORTED
            else:
                status = HypStatus.REJECTED
                notes.append("CI includes 0" if not _ci_excludes_zero(ci) else
                             "opposite direction (total change ke ulta)")
        data = _jsonable(data or {})
        return Finding(hypothesis_id=h.id, statement=statement or h.statement, share_of_delta=float(share),
                       effect=float(effect), ci=ci, p_value=p, method=method, deterministic=deterministic,
                       mde=mde, amount=float(share) * (self.T1 - self.T0), parent_id=h.parent_id, depth=h.depth,
                       source=h.source, claim_type=claim_type, data=data, status=status, notes=notes)

    def test(self, h: Hypothesis) -> Finding:
        key = h.id.split(".", 1)[-1]
        if h.source == "drilldown":
            return self._t_dimension(h) if key.startswith("dim:") else self._t_segment(h)
        if h.source == "llm":
            return self._t_llm(h)
        if h.source == "template":
            return {"seasonality": self._t_seasonality, "data_issue": self._t_data_issue,
                    "concurrent_event": self._t_concurrent, "calendar": self._t_days,
                    "price_change": self._t_rate}.get(key, self._t_unknown)(h)
        return {"days": self._t_days, "orders_per_day": lambda x: self._t_daily_rate(x, "orders"),
                "orders": lambda x: self._t_total(x, "orders"), "aov": self._t_aov,
                "placed_orders": (lambda x: self._t_daily_rate(x, "placed_orders")) if self.cfg.per_day
                else (lambda x: self._t_total(x, "placed_orders")),
                "cancel_rate": self._t_cancel, "category_mix": self._t_mix,
                "segment_aov": self._t_rate}.get(key, self._t_unknown)(h)

    def _t_unknown(self, h: Hypothesis) -> Finding:
        return self._finding(h, share=0.0, effect=0.0, method="none", status=HypStatus.INCONCLUSIVE,
                             notes=["is hypothesis ke liye test defined nahi"])

    def _t_days(self, h: Hypothesis) -> Finding:
        d0, d1 = self.P["base"].days, self.P["current"].days
        share = self.shares.get(h.id, self.shares.get(f"{self.spec.metric}.days", 0.0))
        return self._finding(h, share=share, effect=d1 / d0 - 1, ci=(d1 / d0 - 1, d1 / d0 - 1), method="log_decomp",
                             deterministic=True, statement=f"Calendar: {d0} vs {d1} din", claim_type="fact",
                             data={"d0": d0, "d1": d1, "n": d1, "n_req": 1, "query_ids": self.core_queries})

    def _t_daily_rate(self, h: Hypothesis, m: str) -> Finding:
        """orders/day ya placed/day: per-day mean change; block bootstrap CI + permutation p."""
        a, b = self._arr(m, "base"), self._arr(m, "current")
        effect = _safe_div(b.mean(), a.mean()) - 1
        ci, _ = self._boot(a, b, lambda x, y: y.mean() / x.mean() - 1, h.id)
        p = permutation_test(a, b, n_perm=self.cfg.n_perm, seed=self._seed(h.id))
        sigma = _safe_div(b.std(ddof=1), b.mean())
        label = FACTOR_LABELS.get(h.id.split(".", 1)[-1], m)
        return self._finding(h, share=self.shares.get(h.id, 0.0), effect=effect, ci=ci, p=p,
                             method="block_bootstrap+permutation", mde=self.cfg.mde_rel,
                             statement=f"{label}: {a.mean():.1f} -> {b.mean():.1f} per day ({effect:+.1%})",
                             data={"mean0": a.mean(), "mean1": b.mean(), "n": len(b), "sigma_rel": sigma,
                                   "n_req": required_n(sigma, self.cfg.mde_rel) if sigma > 0 else 1,
                                   "query_ids": self.core_queries})

    def _t_total(self, h: Hypothesis, m: str) -> Finding:
        """-Normalization ablation: period TOTAL (calendar effect isi me mil jaata hai — purane Q-TRACE ki galti)."""
        a, b = self._arr(m, "base"), self._arr(m, "current")
        N0, N1 = a.sum(), b.sum()
        ci, _ = self._boot(a, b, lambda x, y: y.sum() / x.sum() - 1, h.id)
        p = float(sps.binomtest(int(round(N1)), int(round(N0 + N1)), 0.5).pvalue)
        sigma = _safe_div(b.std(ddof=1), b.mean())
        return self._finding(h, share=self.shares.get(h.id, 0.0), effect=N1 / N0 - 1, ci=ci, p=p,
                             method="bootstrap(total)+binomial", mde=self.cfg.mde_rel,
                             statement=f"{FACTOR_LABELS.get(m, m)} (total): {N0:,.0f} -> {N1:,.0f} ({N1 / N0 - 1:+.1%})",
                             data={"N0": N0, "N1": N1, "n": len(b), "sigma_rel": sigma,
                                   "n_req": required_n(sigma, self.cfg.mde_rel) if sigma > 0 else 1,
                                   "query_ids": self.core_queries})

    def _t_aov(self, h: Hypothesis) -> Finding:
        X = np.column_stack([self._arr("revenue", "base"), self._arr("orders", "base")])
        Y = np.column_stack([self._arr("revenue", "current"), self._arr("orders", "current")])
        A0, A1 = X[:, 0].sum() / X[:, 1].sum(), Y[:, 0].sum() / Y[:, 1].sum()

        def stat(x, y):
            return (y[:, 0].sum() / y[:, 1].sum()) / (x[:, 0].sum() / x[:, 1].sum()) - 1

        ci, p = self._boot(X, Y, stat, h.id)
        daily = np.divide(Y[:, 0], Y[:, 1], out=np.zeros(len(Y)), where=Y[:, 1] > 0)
        daily = daily[Y[:, 1] > 0]
        sigma = _safe_div(daily.std(ddof=1), daily.mean()) if len(daily) > 1 else 0.0
        return self._finding(h, share=self.shares.get(h.id, 0.0), effect=A1 / A0 - 1, ci=ci, p=p,
                             method="block_bootstrap", mde=self.cfg.mde_rel,
                             statement=f"AOV: {A0:,.0f} -> {A1:,.0f} ({A1 / A0 - 1:+.1%})",
                             data={"A0": A0, "A1": A1, "n": len(Y), "sigma_rel": sigma,
                                   "n_req": required_n(sigma, self.cfg.mde_rel) if sigma > 0 else 1,
                                   "query_ids": self.core_queries})

    def _t_cancel(self, h: Hypothesis) -> Finding:
        X = np.column_stack([self._arr("placed_orders", "base"), self._arr("orders", "base")])
        Y = np.column_stack([self._arr("placed_orders", "current"), self._arr("orders", "current")])
        pl0, N0, pl1, N1 = X[:, 0].sum(), X[:, 1].sum(), Y[:, 0].sum(), Y[:, 1].sum()
        c0, c1 = 1 - N0 / pl0, 1 - N1 / pl1
        table = np.array([[pl0 - N0, N0], [pl1 - N1, N1]])
        p = float(sps.chi2_contingency(table)[1]) if (table > 0).all() else 1.0

        def stat(x, y):
            return (1 - y[:, 1].sum() / y[:, 0].sum()) - (1 - x[:, 1].sum() / x[:, 0].sum())

        ci, _ = self._boot(X, Y, stat, h.id)
        return self._finding(h, share=self.shares.get(h.id, 0.0), effect=c1 - c0, ci=ci, p=p,
                             method="chi2+block_bootstrap", mde=self.cfg.mde_rate,
                             statement=f"Cancellation rate: {c0:.1%} -> {c1:.1%}",
                             data={"c0": c0, "c1": c1, "n": int(pl1),
                                   "n_req": required_n(math.sqrt(max(c0 * (1 - c0), 1e-9)), self.cfg.mde_rate),
                                   "query_ids": self.core_queries})

    # ---------------------------------------------------------------- segments (mix / rate)
    def _seg_stats(self, dim: str) -> dict:
        if dim in self.segcache:
            return self.segcache[dim]
        idx = self.D.index
        start, end = idx[0].date().isoformat(), self.P["current"].end
        o_df, o_rec = self.da.daily("orders", self.spec.filters, start, end, group_by=(dim,), purpose=f"seg:{dim}:orders")
        O = _calendar_pivot(o_df, dim, "orders", idx)
        recs = [o_rec.id]
        if self.spec.metric == "revenue":
            r_df, r_rec = self.da.daily("revenue", self.spec.filters, start, end, group_by=(dim,),
                                        purpose=f"seg:{dim}:revenue")
            R = _calendar_pivot(r_df, dim, "revenue", idx)
            recs.append(r_rec.id)
        else:
            R = O.copy()
        segs = sorted(set(O.columns) | set(R.columns))
        O, R = O.reindex(columns=segs, fill_value=0.0), R.reindex(columns=segs, fill_value=0.0)
        st = {"O": O, "R": R, "segs": segs, "query_ids": recs}
        self.segcache[dim] = st
        return st

    def _candidate_dims(self) -> list[str]:
        orders_dims = self.layer.get("orders").dimensions if "orders" in self.layer.names() else ()
        return [d for d in self.metric.dimensions if d not in self.spec.filters and d in orders_dims]

    def _t_dimension(self, h: Hypothesis) -> Finding:
        """Doc 8.4 'Drill-down' source: kya per-day change ek segment me concentrated hai?
        Segment contribution (F3, per-day) + composition chi-square (segment vs rest, base vs current) +
        segment per-day block bootstrap. EP/JS ranking (F29) data me."""
        dim = h.dimensions[0]
        st = self._seg_stats(dim)
        v = st["R"] if self.spec.metric == "revenue" else st["O"]
        b, c = self.P["base"], self.P["current"]
        pd0, pd1 = v.loc[b.index].sum() / b.days, v.loc[c.index].sum() / c.days
        delta = pd1 - pd0
        tot = float(delta.sum())
        if abs(tot) < 1e-12 or len(delta) < 2:
            return self._finding(h, share=0.0, effect=0.0, method="segment", status=HypStatus.INCONCLUSIVE,
                                 notes=["per-day change ~0 ya ek hi segment"])
        contrib = {s: float(delta[s] / tot) for s in delta.index}
        size = {s: float(pd0[s] / pd0.sum()) if pd0.sum() else 0.0 for s in delta.index}
        # Bade segment ka contribution hamesha bada hota hai (uniform change me bhi). Concentration =
        # contribution - baseline size: segment apne size se kitna zyada (total ki direction me) hila.
        excess = {s: contrib[s] - size[s] for s in delta.index}
        top = max(excess, key=excess.get)
        days_share = self.shares.get(f"{self.spec.metric}.days", 0.0) if self.cfg.per_day else 0.0
        # Model: dR_seg = shock + size * dR_common,  dR = shock + dR_common
        #   => dR_seg - size * dR = (1 - size) * shock  => shock share = excess / (1 - size)
        share = excess[top] / max(1 - size[top], 0.05) * (1 - days_share)
        i = list(v.columns).index(top)
        sign = 1.0 if tot > 0 else -1.0

        def differential(x, y):     # segment per-day change - total per-day change (total ki direction me)
            seg = y[:, i].mean() / max(x[:, i].mean(), 1e-12)
            allv = y.sum(1).mean() / max(x.sum(1).mean(), 1e-12)
            return sign * (seg - allv)

        ci, _ = self._boot(v.loc[b.index].to_numpy(), v.loc[c.index].to_numpy(), differential, h.id)
        O0, O1 = st["O"].loc[b.index].sum(), st["O"].loc[c.index].sum()
        table = np.array([[O0[top], O0.sum() - O0[top]], [O1[top], O1.sum() - O1[top]]])
        p = float(sps.chi2_contingency(table)[1]) if (table > 0).all() else 1.0
        s0, s1 = _safe_div(O0[top], O0.sum()), _safe_div(O1[top], O1.sum())
        seg_change = _safe_div(pd1[top], pd0[top]) - 1
        total_change = _safe_div(pd1.sum(), pd0.sum()) - 1
        effect = sign * (seg_change - total_change)
        ranking = {r["dimension"]: r for r in self.rank_dims()}.get(dim, {})
        return self._finding(
            h, share=share, effect=effect, ci=ci, p=p, method="excess_contribution+chi2+block_bootstrap",
            mde=self.cfg.mde_rel,
            statement=(f"{dim.title()}: '{top}' me per-day {seg_change:+.1%} (total {total_change:+.1%}); "
                       f"order share {s0:.1%} -> {s1:.1%}; per-day change ka {contrib[top]:.0%} jabki size {size[top]:.0%}"),
            data={"dimension": dim, "top_segment": top, "contributions": contrib, "size": size, "excess": excess,
                  "segment_change": seg_change, "total_change": total_change, "s0": s0, "s1": s1,
                  "ep": ranking.get("ep"), "js": ranking.get("js"), "n": int(O1.sum()),
                  "n_req": required_n(math.sqrt(max(s0 * (1 - s0), 1e-9)), self.cfg.mde_share),
                  "query_ids": st["query_ids"]})

    def rank_dims(self) -> list[dict]:
        if self.dim_ranking:
            return self.dim_ranking
        data = {}
        for d in self.metric.dimensions:
            if d in self.spec.filters or d not in self.layer.get("orders").dimensions:
                continue
            st = self._seg_stats(d)
            v = st["R"] if self.spec.metric == "revenue" else st["O"]
            b, c = self.P["base"], self.P["current"]
            data[d] = ((v.loc[b.index].sum() / b.days).to_dict(), (v.loc[c.index].sum() / c.days).to_dict())
        self.dim_ranking = rank_dimensions(data) if data else []
        return self.dim_ranking

    def aov_dimension(self) -> str | None:
        """AOV drill-down: woh dimension jahan composition (mix) Delta-A ka sabse bada hissa explain kare.
        Kisi dimension me mix >= 50% na ho to rate dominant hai — tab EP+JS ranking (F29) se dimension."""
        if not hasattr(self, "mix_ranking"):
            cands = []
            for d in self.metric.dimensions:
                if d in self.spec.filters or d not in self.layer.get("orders").dimensions:
                    continue
                ms = self._mix_stats(d)
                frac = _safe_div(ms["mix"], ms["dA"]) if abs(ms["dA"]) > 1e-12 else 0.0
                cands.append({"dimension": d, "mix_fraction": frac, "mix": ms["mix"], "rate": ms["rate"]})
            self.mix_ranking = sorted(cands, key=lambda c: -c["mix_fraction"])
        if self.mix_ranking and self.mix_ranking[0]["mix_fraction"] >= 0.5:
            return self.mix_ranking[0]["dimension"]
        ranking = self.rank_dims()
        return ranking[0]["dimension"] if ranking else None

    def _mix_stats(self, dim: str) -> dict:
        if dim in self.mixcache:
            return self.mixcache[dim]
        st = self._seg_stats(dim)
        out = {"dim": dim, "segs": st["segs"]}
        for lbl, suf in (("base", "0"), ("current", "1"), ("yoy_base", "y0"), ("yoy_current", "y1")):
            idx = self.P[lbl].index
            O, R = st["O"].loc[idx].sum(), st["R"].loc[idx].sum()
            out["N" + suf] = float(O.sum())
            out["s" + suf] = (O / O.sum()).to_dict() if O.sum() > 0 else {s: 0.0 for s in st["segs"]}
            out["a" + suf] = {s: (R[s] / O[s] if O[s] > 0 else None) for s in st["segs"]}
            out["O" + suf] = O.to_dict()
        for s in st["segs"]:   # naye / gayab segments: identity A1 - A0 = mix + rate bani rahe
            if out["a0"][s] is None:
                out["a0"][s] = out["a1"][s] or 0.0
            if out["a1"][s] is None:
                out["a1"][s] = out["a0"][s]
        mr = mix_rate(out["s0"], out["s1"], out["a0"], out["a1"])
        A0 = sum(out["s0"][s] * out["a0"][s] for s in st["segs"])
        A1 = sum(out["s1"][s] * out["a1"][s] for s in st["segs"])
        segs = []
        for s in st["segs"]:
            segs.append({"segment": s, "s0": out["s0"][s], "s1": out["s1"][s], "a0": out["a0"][s],
                         "a1": out["a1"][s], "mix_i": (out["s1"][s] - out["s0"][s]) * out["a0"][s],
                         "rate_i": out["s1"][s] * (out["a1"][s] - out["a0"][s])})
        out.update(mix=mr["mix"], rate=mr["rate"], A0=A0, A1=A1, dA=A1 - A0, segments=segs,
                   query_ids=st["query_ids"])
        self.mixcache[dim] = out
        return out

    def _seg_matrices(self, dim: str, label: str) -> tuple[np.ndarray, int]:
        st = self._seg_stats(dim)
        idx = self.P[label].index
        return np.hstack([st["O"].loc[idx].to_numpy(), st["R"].loc[idx].to_numpy()]), len(st["segs"])

    @staticmethod
    def _mix_from_sums(o0, r0, o1, r1) -> tuple[float, float, float]:
        s0, s1 = o0 / o0.sum(), o1 / o1.sum()
        a0 = np.divide(r0, o0, out=np.zeros_like(r0), where=o0 > 0)
        a1 = np.divide(r1, o1, out=a0.copy(), where=o1 > 0)
        a0 = np.where(o0 > 0, a0, a1)
        A0 = r0.sum() / o0.sum()
        return float(((s1 - s0) * a0).sum()), float((s1 * (a1 - a0)).sum()), float(A0)

    def _parent_share(self, h: Hypothesis) -> float:
        return self.shares.get(h.parent_id or "", 0.0)

    def _t_mix(self, h: Hypothesis) -> Finding:
        dim = h.dimensions[0]
        ms = self._mix_stats(dim)
        X, k = self._seg_matrices(dim, "base")
        Y, _ = self._seg_matrices(dim, "current")

        def stat(x, y):
            mix, _, A0 = self._mix_from_sums(x[:, :k].sum(0), x[:, k:].sum(0), y[:, :k].sum(0), y[:, k:].sum(0))
            return mix / A0

        ci, _ = self._boot(X, Y, stat, h.id)
        counts = np.array([[ms["O0"][s], ms["O1"][s]] for s in ms["segs"]])
        counts = counts[counts.sum(1) > 0]
        p = float(sps.chi2_contingency(counts)[1]) if len(counts) >= 2 else 1.0
        segs = sorted(ms["segments"], key=lambda s: -_safe_div(s["mix_i"], ms["mix"]))
        top = segs[0]
        p_top = top["s0"]
        return self._finding(
            h, share=self.shares.get(h.id, 0.0), effect=ms["mix"] / ms["A0"], ci=ci, p=p,
            method="mix_rate+chi2+block_bootstrap", mde=self.cfg.mde_rel,
            statement=(f"{dim.title()} mix shift: '{top['segment']}' ka order share {top['s0']:.1%} -> "
                       f"{top['s1']:.1%} (mix effect {ms['mix']:+,.0f} on AOV)"),
            data={"dimension": dim, "mix": ms["mix"], "rate": ms["rate"], "A0": ms["A0"], "A1": ms["A1"],
                  "segments": segs, "top_segment": top["segment"], "n": int(ms["N1"]),
                  "n_req": required_n(math.sqrt(max(p_top * (1 - p_top), 1e-9)), self.cfg.mde_share),
                  "query_ids": ms["query_ids"]})

    def _t_rate(self, h: Hypothesis) -> Finding:
        dim = h.dimensions[0] if h.dimensions else (self.rank_dims()[0]["dimension"] if self.rank_dims() else None)
        if dim is None:
            return self._t_unknown(h)
        ms = self._mix_stats(dim)
        X, k = self._seg_matrices(dim, "base")
        Y, _ = self._seg_matrices(dim, "current")

        def stat(x, y):
            _, rate, A0 = self._mix_from_sums(x[:, :k].sum(0), x[:, k:].sum(0), y[:, :k].sum(0), y[:, k:].sum(0))
            return rate / A0

        ci, p = self._boot(X, Y, stat, h.id)
        segs = sorted(ms["segments"], key=lambda s: -_safe_div(s["rate_i"], ms["rate"]))
        top = segs[0]
        share = self.shares.get(h.id)
        if share is None:   # price_change template: rate share computed directly
            share = self._split_share("aov", ms)[1]
        return self._finding(
            h, share=share, effect=ms["rate"] / ms["A0"], ci=ci, p=p, method="mix_rate+block_bootstrap",
            mde=self.cfg.mde_rel,
            statement=(f"{dim.title()} ke andar AOV badla: '{top['segment']}' AOV {top['a0']:,.0f} -> "
                       f"{top['a1']:,.0f} (rate effect {ms['rate']:+,.0f})"),
            data={"dimension": dim, "mix": ms["mix"], "rate": ms["rate"], "A0": ms["A0"], "A1": ms["A1"],
                  "segments": segs, "top_segment": top["segment"], "n": len(Y), "n_req": 1,
                  "query_ids": ms["query_ids"]})

    def _split_share(self, parent_key: str, ms: dict) -> tuple[float, float]:
        parent = self.shares.get(f"{self.spec.metric}.{parent_key}", 0.0)
        if self.cfg.use_decomposition:
            if abs(ms["dA"]) < 1e-12:
                return 0.0, 0.0
            return parent * ms["mix"] / ms["dA"], parent * ms["rate"] / ms["dA"]
        return (ms["mix"] / ms["A0"]) / self.rel_total, (ms["rate"] / ms["A0"]) / self.rel_total

    def _t_segment(self, h: Hypothesis) -> Finding:
        parent = self.findings[h.parent_id]
        dim, seg = h.id.split(">", 1)[1].split("=", 1)
        ms = self._mix_stats(dim)
        row = next(s for s in ms["segments"] if s["segment"] == seg)
        X, k = self._seg_matrices(dim, "base")
        Y, _ = self._seg_matrices(dim, "current")
        i = ms["segs"].index(seg)
        if parent.hypothesis_id.endswith(".category_mix"):
            share = parent.share_of_delta * _safe_div(row["mix_i"], ms["mix"])
            O0, O1, N0, N1 = ms["O0"][seg], ms["O1"][seg], ms["N0"], ms["N1"]
            table = np.array([[O0, N0 - O0], [O1, N1 - O1]])
            p = float(sps.chi2_contingency(table)[1]) if (table > 0).all() else 1.0
            ci, _ = self._boot(X, Y, lambda x, y: y[:, i].sum() / y[:, :k].sum() - x[:, i].sum() / x[:, :k].sum(),
                               h.id)
            return self._finding(
                h, share=share, effect=row["s1"] - row["s0"], ci=ci, p=p, method="chi2+block_bootstrap",
                mde=self.cfg.mde_share,
                statement=f"'{seg}' ({dim}) ka order share {row['s0']:.1%} -> {row['s1']:.1%}",
                data={"dimension": dim, "segment": seg, **row, "n": int(N1),
                      "n_req": required_n(math.sqrt(max(row["s0"] * (1 - row["s0"]), 1e-9)), self.cfg.mde_share),
                      "query_ids": ms["query_ids"]})
        share = parent.share_of_delta * _safe_div(row["rate_i"], ms["rate"])
        ci, p = self._boot(X, Y, lambda x, y: _safe_div(y[:, k + i].sum(), y[:, i].sum()) /
                           max(_safe_div(x[:, k + i].sum(), x[:, i].sum()), 1e-12) - 1, h.id)
        return self._finding(
            h, share=share, effect=_safe_div(row["a1"], row["a0"]) - 1, ci=ci, p=p, method="block_bootstrap",
            mde=self.cfg.mde_rel, statement=f"'{seg}' ({dim}) ka AOV {row['a0']:,.0f} -> {row['a1']:,.0f}",
            data={"dimension": dim, "segment": seg, **row, "n": len(Y), "n_req": 1, "query_ids": ms["query_ids"]})

    def _t_seasonality(self, h: Hypothesis) -> Finding:
        if self.yoy is None:
            return self._finding(h, share=0.0, effect=0.0, method="yoy", status=HypStatus.INCONCLUSIVE,
                                 notes=["pichhle saal ka data (same months) available nahi"])
        y = self.yoy
        se = y["se_ly"]
        ci = (math.exp(y["ly"] - 1.96 * se) - 1, math.exp(y["ly"] + 1.96 * se) - 1)
        p = float(2 * (1 - sps.norm.cdf(abs(y["ly"]) / se))) if se > 0 else 0.0
        return self._finding(
            h, share=y["ly"] / self.dlnR, effect=math.exp(y["ly"]) - 1, ci=ci, p=p, method="yoy", mde=self.cfg.mde_rel,
            statement=(f"Seasonality: pichhle saal same months me per-day change {y['last_year_delta']:+.1%} "
                       f"(is saal {y['this_year_delta']:+.1%})"),
            data={**y, "n": len(self.P["current"].index), "n_req": 1, "query_ids": [self.history_query]})

    def _t_data_issue(self, h: Hypothesis) -> Finding:
        hd = self.health.to_dict()
        return self._finding(h, share=0.0, effect=0.0, method="data_health", deterministic=True,
                             status=HypStatus.REJECTED if self.health.ok else HypStatus.SUPPORTED,
                             statement=(f"Data issue: {hd['days_with_data']}/{hd['expected_days']} din ka data, "
                                        f"null rate {self.health.null_rate:.2%}"),
                             claim_type="fact", data={"health": hd, "n": 1, "n_req": 1},
                             notes=["Verify step me health checks pass"] if self.health.ok else [])

    def _t_concurrent(self, h: Hypothesis) -> Finding:
        if not self.controls:
            return self._finding(h, share=0.0, effect=0.0, method="did", status=HypStatus.INCONCLUSIVE,
                                 notes=["koi control segment nahi mila — DiD skip"])
        target = self.control_info["target"]
        piv = self.control_daily

        def arr(label):
            idx = self.P[label].index
            return np.column_stack([piv.loc[idx, target].to_numpy(), piv.loc[idx, self.controls].mean(axis=1)])

        X, Y = arr("base"), arr("current")
        T0, C0, T1, C1 = X[:, 0].mean(), X[:, 1].mean(), Y[:, 0].mean(), Y[:, 1].mean()
        market = math.log(C1 / C0)
        did = diff_in_diff(T0, T1, C0, C1)
        ci, p = self._boot(X, Y, lambda x, y: math.log(y[:, 1].mean() / x[:, 1].mean()), h.id)
        did_ci, did_p = self._boot(
            X, Y, lambda x, y: diff_in_diff(x[:, 0].mean(), y[:, 0].mean(), x[:, 1].mean(), y[:, 1].mean()),
            h.id + ":did")
        self.did = {"did": did, "did_ci": did_ci, "did_p": did_p, "market": market,
                    "control_change": math.exp(market) - 1, "controls": self.controls,
                    "parallel_ok": self.control_info.get("parallel_ok", True),
                    "pre_trend_gap": self.control_info.get("pre_trend_gap")}
        ci_eff = (math.exp(ci[0]) - 1, math.exp(ci[1]) - 1)
        notes = [] if self.did["parallel_ok"] else ["parallel-trends gap bada hai — DiD weak (CP 0.3)"]
        f = self._finding(
            h, share=market / self.dlnR, effect=math.exp(market) - 1, ci=ci_eff, p=p, method="log_did+block_bootstrap",
            mde=self.cfg.mde_rel,
            statement=(f"Controls ({', '.join(self.controls)}) me per-day change {math.exp(market) - 1:+.1%}; "
                       f"DiD {math.exp(did) - 1:+.1%}"),
            data={**self.did, "n": len(Y), "n_req": 1, "query_ids": [self.control_info["query_id"]]}, notes=notes)
        if not self.did["parallel_ok"]:
            f.contradiction_penalty = max(f.contradiction_penalty, 0.3)
        return f

    def _t_llm(self, h: Hypothesis) -> Finding:
        dims = [d for d in h.dimensions if d in self.metric.dimensions and d not in self.spec.filters]
        if not dims:
            return self._finding(h, share=0.0, effect=0.0, method="segment", status=HypStatus.INCONCLUSIVE,
                                 notes=["LLM hypothesis kisi testable dimension par map nahi hui"])
        dim = dims[0]
        st = self._seg_stats(dim)
        v = st["R"] if self.spec.metric == "revenue" else st["O"]
        b, c = self.P["base"], self.P["current"]
        pd0, pd1 = v.loc[b.index].sum() / b.days, v.loc[c.index].sum() / c.days
        delta = pd1 - pd0
        tot = delta.sum()
        seg = max(delta.index, key=lambda s: _safe_div(delta[s], tot))
        days_share = self.shares.get(f"{self.spec.metric}.days", 0.0)
        share = _safe_div(delta[seg], tot) * (1 - days_share)
        i = list(v.columns).index(seg)
        ci, p = self._boot(v.loc[b.index].to_numpy(), v.loc[c.index].to_numpy(),
                           lambda x, y: y[:, i].mean() / max(x[:, i].mean(), 1e-12) - 1, h.id)
        return self._finding(h, share=share, effect=_safe_div(pd1[seg], pd0[seg]) - 1, ci=ci, p=p,
                             method="segment_contribution+block_bootstrap", mde=self.cfg.mde_rel,
                             statement=f"{h.statement} — '{seg}' ({dim}) per-day {_safe_div(pd1[seg], pd0[seg]) - 1:+.1%}",
                             data={"dimension": dim, "segment": seg, "n": len(c.index), "n_req": 1,
                                   "query_ids": st["query_ids"]})

    # ================================================================== drill-down
    def refine(self, h: Hypothesis, f: Finding) -> list[Hypothesis]:
        """Bada factor (share > 30%, depth < 2) -> children (metric tree) ya segments (EP + JS)."""
        key = h.id.split(".", 1)[-1]
        if h.source == "metric_tree" and key in ("category_mix", "segment_aov"):
            ms = self._mix_stats(h.dimensions[0])
            field_ = "mix_i" if key == "category_mix" else "rate_i"
            total = ms["mix"] if key == "category_mix" else ms["rate"]
            ranked = sorted(ms["segments"], key=lambda s: -_safe_div(s[field_], total))
            segs = [s["segment"] for s in ranked if _safe_div(s[field_], total) > 0][: self.cfg.max_segments]
            kids = drilldown_hypotheses(h, h.dimensions[0], segs)
            for k, s in zip(kids, segs):
                row = next(r for r in ms["segments"] if r["segment"] == s)
                self.shares[k.id] = f.share_of_delta * _safe_div(row[field_], total)
            return kids
        if h.source != "metric_tree":
            return []
        dim = None
        if needs_dimension(h, self.cfg.per_day):
            dim = self.aov_dimension() if key == "aov" else (self.rank_dims() or [{}])[0].get("dimension")
            if dim is None:
                return []
        kids = children_of(h, per_day=self.cfg.per_day, dimension=dim)
        if key == "aov" and dim:
            ms = self._mix_stats(dim)
            s_mix, s_rate = self._split_share("aov", ms)
            for k in kids:
                self.shares[k.id] = s_mix if k.id.endswith("category_mix") else s_rate
            self.decomp_rows += [
                {"factor": "mix", "hypothesis": f"{self.spec.metric}.category_mix", "method": "mix",
                 "share": s_mix, "amount": s_mix * (self.T1 - self.T0), "depth": 1, "dimension": dim,
                 "value": ms["mix"], "parent": h.id},
                {"factor": "rate", "hypothesis": f"{self.spec.metric}.segment_aov", "method": "rate",
                 "share": s_rate, "amount": s_rate * (self.T1 - self.T0), "depth": 1, "dimension": dim,
                 "value": ms["rate"], "parent": h.id}]
        elif key in ("orders_per_day", "orders"):
            def ln_ratio(m, per_day):
                v0, v1 = self._tot(m, "base"), self._tot(m, "current")
                if per_day:
                    v0, v1 = v0 / self.P["base"].days, v1 / self.P["current"].days
                return v0, v1
            pl0, pl1 = ln_ratio("placed_orders", self.cfg.per_day)
            c0 = self._tot("orders", "base") / self._tot("placed_orders", "base")
            c1 = self._tot("orders", "current") / self._tot("placed_orders", "current")
            if self.cfg.use_decomposition:
                sp, sc = math.log(pl1 / pl0) / self.dlnR, math.log(c1 / c0) / self.dlnR
            else:
                sp, sc = (pl1 / pl0 - 1) / self.rel_total, (c1 / c0 - 1) / self.rel_total
            for k in kids:
                self.shares[k.id] = sp if k.id.endswith("placed_orders") else sc
            self.decomp_rows += [
                {"factor": "placed_orders", "hypothesis": f"{self.spec.metric}.placed_orders", "method": "log",
                 "share": sp, "amount": sp * (self.T1 - self.T0), "depth": 1, "parent": h.id},
                {"factor": "cancel_rate", "hypothesis": f"{self.spec.metric}.cancel_rate", "method": "log",
                 "share": sc, "amount": sc * (self.T1 - self.T0), "depth": 1, "parent": h.id}]
        return kids

    # ================================================================== C: cross-check
    def cross_check(self) -> None:
        pvals = {k: f.p_value for k, f in self.findings.items() if f.p_value is not None and not f.deterministic}
        if pvals:
            adj = benjamini_hochberg(pvals, q=self.cfg.fdr_q) if self.cfg.use_fdr else \
                {k: (p, p <= self.cfg.fdr_q) for k, p in pvals.items()}
            for k, (q, _) in adj.items():
                f = self.findings[k]
                f.q_value = q
                if f.status == HypStatus.SUPPORTED and q > self.cfg.fdr_q:
                    f.status = HypStatus.REJECTED
                    f.notes.append(f"FDR ke baad significant nahi (q={q:.3f} > {self.cfg.fdr_q})")
                    self._step("C", "fdr", ref=k, frm="supported", to="rejected")
        self.reconcile()
        self.simpson_check()

    def reconcile(self) -> None:
        """Same metric do independent paths (orders vs payments) — +-10% agree => CQA = 1."""
        if self.spec.metric != "revenue" or "payments_revenue" not in self.layer.names():
            self.reconciliation = {"paths": 1, "note": "single path (payments path available nahi)"}
            self.cqa = 0.5
            return
        pay = self.layer.get("payments_revenue")
        if not all(k in pay.dimensions for k in self.spec.filters):
            self.reconciliation = {"paths": 1, "note": "payments path par filters apply nahi hote"}
            self.cqa = 0.5
            return
        cur = self.P["current"]
        sql = self.layer.render("payments_revenue", filters=self.spec.filters, start=cur.start, end=cur.end,
                                as_of=self.da.as_of)
        res, rec = self.da.run(sql, "C:reconcile", metric="payments_revenue", table=pay.table,
                               metric_definition=self.da.definition("payments_revenue"),
                               filters=dict(self.spec.filters), time_window=[cur.start, cur.end])
        paid = float(res.all_rows[0][0] or 0.0) if res.all_rows else 0.0
        orders_path = self._tot("revenue", "current")
        self.cqa = cross_query_agreement([orders_path, paid])
        self.reconciliation = {"paths": 2, "orders_path": orders_path, "payments_path": paid,
                               "diff_rel": _safe_div(paid - orders_path, orders_path), "cqa": self.cqa,
                               "query_id": rec.id}

    def simpson_check(self) -> None:
        mix_f = next((f for k, f in self.findings.items() if k.endswith(".category_mix")), None)
        if mix_f is None:
            return
        ms = self._mix_stats(mix_f.data["dimension"])
        moves = [s["a1"] - s["a0"] for s in ms["segments"] if s["s0"] > 0 and s["s1"] > 0]
        agg = ms["dA"]
        paradox = bool(moves) and all(m * agg < 0 for m in moves if abs(m) > 1e-9) and any(abs(m) > 1e-9 for m in moves)
        self.simpson = {"aggregate_change": agg, "segments_up": sum(m > 0 for m in moves),
                        "segments_down": sum(m < 0 for m in moves), "paradox": paradox,
                        "dominant": "mix" if abs(ms["mix"]) >= abs(ms["rate"]) else "rate"}
        if paradox:
            mix_f.notes.append("Simpson: har segment ka AOV ek taraf, total doosri taraf — mix effect dominate")

    # ================================================================== Ch: challenge battery
    def challenge(self) -> None:
        top = sorted([f for f in self.frontier() if f.status in SUPPORTED_LIKE], key=lambda f: -f.share_of_delta)[:2]
        dims = sorted([f for k, f in self.findings.items() if ".dim:" in k and f.status in SUPPORTED_LIKE],
                      key=lambda f: -f.share_of_delta)[:1]
        top += dims     # sabse strong "concentration" finding bhi battery se guzarti hai
        for f in top:
            ctx = self._battery_ctx(f)
            results = run_challenge_battery(ctx)
            if not results:
                continue
            verdict = resolve(results)
            self._step("Ch", "challenge", ref=f.hypothesis_id, frm="supported", to="challenged")
            f.challenges = _jsonable([{**r.to_dict(), "origin": "auto"} for r in results])
            f.status = HypStatus(verdict)
            f.contradiction_penalty = max(f.contradiction_penalty, contradiction_penalty(results))
            self._step("Ch", "challenge", ref=f.hypothesis_id, frm="challenged", to=verdict)

    def _battery_ctx(self, f: Finding) -> dict:
        key = f.hypothesis_id.split(".", 1)[-1]
        if key == "days":
            return {"health": self.health}
        ctx: dict = {"health": self.health, "n": int(f.data.get("n", 0)), "n_required": int(f.data.get("n_req", 1))}
        days_share = self.shares.get(f"{self.spec.metric}.days", 0.0)
        if self.cfg.per_day and days_share < 1:
            ctx["per_day_share"] = f.share_of_delta / (1 - days_share)
        dim = f.data.get("dimension")
        if dim and key.startswith("dim:"):
            ms = self._mix_stats(dim)
            seg = f.data["top_segment"]
            if self.dim_ranking:   # alternative segment: kya doosri dimension zyada "surprising" (JS) hai?
                ctx.update(ep_by_dimension={r["dimension"]: r["js"] for r in self.dim_ranking}, claimed_dimension=dim)
            if ms.get("Ny0"):
                p = ms["s0"].get(seg, 0.0)
                se = math.sqrt(sum(p * (1 - p) / max(n, 1) for n in (ms["N0"], ms["N1"], ms["Ny0"], ms["Ny1"])))
                ctx.update(this_year_delta=ms["s1"][seg] - ms["s0"][seg],
                           last_year_delta=ms["sy1"].get(seg, 0.0) - ms["sy0"].get(seg, 0.0),
                           seasonality_min_excess=1.96 * se)
            ctx["health"] = self.verify_health(extra_filters={dim: seg}, purpose=f"Ch:health:{seg}")
            ctx.pop("per_day_share", None)
        elif dim and key in ("category_mix", "segment_aov"):
            ms = self._mix_stats(dim)
            ctx.update(mix=ms["mix"], rate=ms["rate"], claimed_type="mix" if key == "category_mix" else "rate")
            if key == "category_mix" and getattr(self, "mix_ranking", None):
                # mix claim ke liye "alternative segment" = kya kisi aur dimension ka mix zyada explain karta hai
                ctx.update(ep_by_dimension={r["dimension"]: r["mix_fraction"] for r in self.mix_ranking},
                           claimed_dimension=dim)
            elif self.rank_dims():
                ctx.update(ep_by_dimension={r["dimension"]: r["ep"] for r in self.dim_ranking}, claimed_dimension=dim)
            seg = f.data.get("top_segment")
            if seg is not None and ms.get("Ny0") and key == "category_mix":
                ty = ms["s1"][seg] - ms["s0"][seg]
                ly = ms["sy1"].get(seg, 0.0) - ms["sy0"].get(seg, 0.0)
                p = ms["s0"][seg]
                se = math.sqrt(sum(p * (1 - p) / max(n, 1) for n in (ms["N0"], ms["N1"], ms["Ny0"], ms["Ny1"])))
                ctx.update(this_year_delta=ty, last_year_delta=ly, seasonality_min_excess=1.96 * se)
                ctx["health"] = self.verify_health(extra_filters={dim: seg}, purpose=f"Ch:health:{seg}")
        else:
            fy = self._factor_yoy(key)
            if fy is not None:   # finding-level: kya ISI factor ne pichhle saal bhi itna change kiya tha?
                ctx.update(this_year_delta=fy["ty"], last_year_delta=fy["ly"], seasonality_min_excess=1.96 * fy["se"])
        did = getattr(self, "did", None)
        if did is None and self.controls:
            self._t_concurrent(self.hypotheses.get("tpl.concurrent_event") or
                               Hypothesis(id="tpl.concurrent_event", statement="", metric=self.spec.metric,
                                          source="template", test_type="did"))
            did = getattr(self, "did", None)
        if did is not None:
            ctx["did_ci"] = tuple(did["did_ci"])
        return ctx

    def _factor_yoy(self, key: str) -> dict | None:
        """Factor ka is-saal vs pichhle-saal change (same months) + standard error (seasonality challenge)."""
        if self.yoy is None:
            return None
        labels = ("base", "current", "yoy_base", "yoy_current")
        try:
            if key in ("orders_per_day", "placed_orders", "orders"):
                m = "orders" if key in ("orders_per_day", "orders") else "placed_orders"
                arr = {k: self._arr(m, k) for k in labels}
                if any(a.mean() <= 0 for a in arr.values()):
                    return None
                ty = math.log(arr["current"].mean() / arr["base"].mean())
                ly = math.log(arr["yoy_current"].mean() / arr["yoy_base"].mean())
                se = math.sqrt(sum(rel_se(a) ** 2 for a in arr.values()))
            elif key == "aov":
                val = {k: _safe_div(self._tot("revenue", k), self._tot("orders", k)) for k in labels}
                daily = {}
                for k in labels:
                    r, n = self._arr("revenue", k), self._arr("orders", k)
                    daily[k] = r[n > 0] / n[n > 0]
                if min(val.values()) <= 0:
                    return None
                ty, ly = math.log(val["current"] / val["base"]), math.log(val["yoy_current"] / val["yoy_base"])
                se = math.sqrt(sum(rel_se(a) ** 2 for a in daily.values()))
            elif key == "cancel_rate":
                c = {k: 1 - _safe_div(self._tot("orders", k), self._tot("placed_orders", k)) for k in labels}
                n = {k: self._tot("placed_orders", k) for k in labels}
                ty, ly = c["current"] - c["base"], c["yoy_current"] - c["yoy_base"]
                se = math.sqrt(sum(c[k] * (1 - c[k]) / max(n[k], 1) for k in labels))
            else:
                return {"ty": self.yoy["ty"], "ly": self.yoy["ly"], "se": self.yoy["se_excess"]}
        except (ValueError, ZeroDivisionError):
            return None
        return {"ty": ty, "ly": ly, "se": se}

    # ================================================================== E: score
    def score(self) -> None:
        dc = data_coverage(self.health.days_with_data or 0, self.health.expected_days or 1, self.health.null_rate)
        for f in self.findings.values():
            if f.status in (HypStatus.REJECTED, HypStatus.OVERTURNED, HypStatus.NOT_TESTED):
                f.score, f.label = None, None
                continue
            if f.status == HypStatus.INCONCLUSIVE and f.share_of_delta == 0:
                continue
            sa = 1.0 if f.deterministic else sample_adequacy(f.data.get("n", 0), max(f.data.get("n_req", 1), 1))
            if f.deterministic:
                ss = 1.0
            elif f.ci is None:
                ss = 0.0
            else:
                q = f.q_value if f.q_value is not None else (f.p_value if f.p_value is not None else 1.0)
                ss = statistical_strength(q, f.effect, f.mde or self.cfg.mde_rel, f.ci[0], f.ci[1])
            sc = 1.0 if f.source != "llm" else 0.8
            f.components = {"DC": round(dc, 4), "SA": round(sa, 4), "SS": round(ss, 4), "CQA": round(self.cqa, 4),
                            "SC": sc, "ES": round(explained_share(f.share_of_delta), 4)}
            f.score, f.label = evidence_score(f.components, f.contradiction_penalty)
            if f.label == "Insufficient" and f.status in SUPPORTED_LIKE:
                f.status = HypStatus.INCONCLUSIVE
                f.notes.append("evidence gate fail (DC < 0.7 ya SA < 0.5) — insufficient evidence")

    # ================================================================== X: explain + graph
    def build_graph(self, report: InvestigationReport) -> EvidenceGraph:
        g = EvidenceGraph()
        qmap = {q.id: q for q in self.da.records}
        for q in self.da.records:      # Ch 6.2: evidence node ki poori provenance
            g.add_node(q.id, "query", f"{q.id} {q.purpose}",
                       **build_provenance(q, dataset_version=self.dataset_version, schema_snapshot=self.schema_snapshot))
        g.add_node("N-verify", "verify", "Verify: data health + anomaly gate",
                   health_ok=self.health.ok, gate=self.gate.get("status"), z=self.gate.get("z"))
        if self.gate.get("query_id") in qmap:
            g.add_edge("N-verify", self.gate["query_id"])
        if report.status != "completed":
            return g
        g.add_node("N-total", "fact", "Total change", T0=self.T0, T1=self.T1, rel=self.rel_total)
        for qid in self.core_queries:
            if qid in qmap:
                g.add_edge("N-total", qid)
        g.add_node("I", "insight", "Insight")
        frontier_keys = {f.hypothesis_id for f in self.frontier()}
        for k, f in self.findings.items():
            nid = f"F:{k}"
            g.add_node(nid, "finding", f.statement, share=f.share_of_delta, score=f.score, evidence_label=f.label,
                       status=f.status.value)
            for qid in f.data.get("query_ids", []):
                if qid in qmap:
                    g.add_edge(nid, qid)
            if k in frontier_keys or f.source == "template":
                g.add_edge("I", nid, "supported_by" if f.status in SUPPORTED_LIKE else "contradicted_by")
            if f.parent_id and f"F:{f.parent_id}" in g.nodes:
                g.add_edge(f"F:{f.parent_id}", nid)
            for c in f.challenges:
                cid = f"C:{k}:{c['type']}"
                g.add_node(cid, "challenge", f"{c['type']}: {'pass' if c['passed'] else 'fail'}", detail=c["detail"])
                g.add_edge(nid, cid, "supported_by" if c["passed"] else "contradicted_by")
        return g

    def explain(self, report: InvestigationReport, graph: EvidenceGraph) -> list[Claim]:
        values = evidence_values(report, graph)
        claims = build_claims(report, graph, self.cfg)
        source = "template"
        if self.llm is not None and self.cfg.llm_narrative and report.status == "completed":
            llm_claims = self._llm_claims(report, graph, values)
            if llm_claims:
                claims, source = llm_claims, "llm"
        ok, bad = numeric_grounding_ok(" ".join(c.sentence for c in claims), values)
        if not ok:
            claims = [c.model_copy(update={"sentence": strip_ungrounded(c.sentence, values)}) for c in claims]
        ok_after, bad_after = numeric_grounding_ok(" ".join(c.sentence for c in claims), values)
        report.grounding = {"source": source, "violations_before": len(bad), "violations": len(bad_after),
                            "ungrounded_numbers": bad, "checked_numbers": len(numbers_in(" ".join(c.sentence for c in claims)))}
        return claims

    def _llm_claims(self, report, graph, values) -> list[Claim]:
        node_ids = set(graph.nodes)
        evidence = {
            "question": report.question, "spec": report.spec.model_dump(), "status": report.status,
            "total": {"base": self.T0, "current": self.T1, "rel_change": self.rel_total},
            "findings": [{"node_id": f"F:{f.hypothesis_id}", "statement": f.statement, "share": f.share_of_delta,
                          "effect": f.effect, "status": f.status.value, "label": f.label}
                         for f in self.findings.values()],
            "other_nodes": ["N-total", "N-verify"],
        }

        def ask(prompt: str) -> list[Claim]:
            if not self.budget.left():
                return []
            try:
                resp = self.llm.complete(prompt)
            except LLMError:
                return []
            self.budget.spend_llm()
            self.llm_calls.append(("X:explain", prompt, resp))
            m = re.search(r"\[.*\]", resp.text, re.S)
            if not m:
                return []
            try:
                raw = json.loads(m.group(0))
            except json.JSONDecodeError:
                return []
            out = []
            for c in raw if isinstance(raw, list) else []:
                try:
                    ids = [i for i in c.get("evidence_node_ids", []) if i in node_ids]
                    out.append(Claim(sentence=str(c["sentence"]), claim_type=c["claim_type"], evidence_node_ids=ids))
                except Exception:
                    continue
            return [c for c in out if c.evidence_node_ids]

        base_prompt = explain_prompt(evidence)
        claims = ask(base_prompt)
        if not claims:
            return []
        return regenerate_or_strip(
            claims, values,
            regenerate=lambda cl, bad: ask(base_prompt + f"\nIn numbers ka evidence nahi hai, hata do: {bad}"))

    def _llm_extras(self, spec: QuestionSpec) -> list[Hypothesis]:
        dims = list(self.metric.dimensions)
        prompt = ("Suggest up to 3 extra business hypotheses for the metric change. Return JSON list of "
                  "{\"id\": short_snake_case, \"statement\": str, \"dimensions\": [one of allowed]}.\n"
                  f"Allowed dimensions: <data>{json.dumps(dims)}</data>\n"
                  f"Spec: <data>{json.dumps(spec.model_dump())}</data>")
        try:
            resp = self.llm.complete(prompt)
        except LLMError:
            return []
        self.budget.spend_llm()
        self.llm_calls.append(("T:llm_extras", prompt, resp))
        m = re.search(r"\[.*\]", resp.text, re.S)
        try:
            raw = json.loads(m.group(0)) if m else []
        except json.JSONDecodeError:
            return []
        out = []
        for r in raw[:3] if isinstance(raw, list) else []:
            try:
                slug = re.sub(r"[^a-z0-9_]", "_", str(r["id"]).lower())[:40]
                out.append(Hypothesis(id=f"llm.{slug}", statement=str(r["statement"])[:300], metric=spec.metric,
                                      dimensions=[d for d in r.get("dimensions", []) if isinstance(d, str)],
                                      source="llm", prior=0.3, test_type="corr"))
            except Exception:
                continue
        return out

    # ================================================================== finish
    def _step(self, phase: str, type_: str, ref: str | None = None, frm: str | None = None, to: str | None = None):
        step = {"phase": phase, "type": type_, "ref": ref, "from": frm, "to": to,
                "ts": datetime.now().isoformat(timespec="milliseconds")}
        self.steps.append(step)
        if self.on_step is not None:      # live timeline (Ch 14: GET /timeline = live progress)
            try:
                self.on_step(step)
            except Exception:  # noqa: BLE001 — progress logging kabhi investigation ko fail na kare
                pass

    def _schema_snapshot(self) -> str:
        """Run me use hui tables ke columns ka hash (schema badle to replay me pata chale)."""
        from sqlalchemy import inspect

        try:
            insp = inspect(self.engine)
            tables = sorted({m.table for m in self.layer.metrics()} & set(insp.get_table_names()))
            return schema_snapshot_hash([{"table": t, "columns": insp.get_columns(t)} for t in tables])
        except Exception:  # noqa: BLE001
            return "unknown"

    def _finish(self, report: InvestigationReport, status: str, t0: float) -> InvestigationReport:
        report.status = status
        report.verify = {"health": self.health.to_dict(), "gate": self.gate,
                         "yoy": self.yoy}
        if status == "completed":
            report.core = {"T0": self.T0, "T1": self.T1, "abs_change": self.T1 - self.T0, "rel_change": self.rel_total,
                           "dlnR": self.dlnR, "factors0": self.factors0, "factors1": self.factors1,
                           "days0": self.P["base"].days, "days1": self.P["current"].days,
                           "per_day0": self.T0 / self.P["base"].days, "per_day1": self.T1 / self.P["current"].days,
                           "per_day_change": (self.T1 / self.P["current"].days) / (self.T0 / self.P["base"].days) - 1,
                           "unit": self.metric.unit}
            report.decomposition = self.decomp_rows
            report.hypotheses = list(self.hypotheses.values())
            report.findings = list(self.findings.values())
            report.frontier = [f.hypothesis_id for f in self.frontier()]
            report.stop_reason = self.stop
            report.explained = self.explained_total()
            report.residual_share = 1 - report.explained
            report.core["explained_per_day"] = self.explained()
            report.controls = self.controls
            merged: dict[str, dict] = {r["dimension"]: dict(r) for r in self.dim_ranking}
            for r in getattr(self, "mix_ranking", []):
                merged.setdefault(r["dimension"], {"dimension": r["dimension"]}).update(r)
            report.dimension_ranking = list(merged.values())
            report.reconciliation = self.reconciliation
            report.simpson = self.simpson
            report.core["shapley"] = {k: v for k, v in self.shapley.items()}
        self.dataset_version = f"asof={self.as_of}|data_through={self.data_through or 'unknown'}"
        self.schema_snapshot = self._schema_snapshot()
        report.dataset_version, report.schema_snapshot = self.dataset_version, self.schema_snapshot
        graph = self.build_graph(report)
        report.claims = self.explain(report, graph)
        for i, c in enumerate(report.claims, start=1):     # 6.2: evidence node -> linked claim IDs
            for nid in c.evidence_node_ids:
                if nid in graph.nodes:
                    graph.nodes[nid].data.setdefault("claim_ids", []).append(f"C{i}")
        report.graph = graph.to_react_flow()
        report.queries = self.da.records
        report.llm_calls = self.llm_calls
        report.steps = self.steps
        report.notes = self.notes
        report.budget = {"queries": self.budget.queries, "llm_calls": self.budget.llm_calls,
                         "max_queries": self.budget.max_queries, "max_llm_calls": self.budget.max_llm_calls}
        report.duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        self._step("Rec", "report", to=status)
        report.steps = self.steps
        return report
