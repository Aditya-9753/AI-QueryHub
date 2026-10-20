"""Synthetic planted-cause benchmark (Ch 18.2).

    python -m tests.eval_suite.generator --scenarios 50

2 saal ka daily e-commerce data (cities x categories, yearly seasonality, weekly pattern, Poisson noise),
har scenario me 0-1 known cause plant hota hai, ground truth JSON alag save hota hai.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

CITIES = {"Delhi": 330, "Mumbai": 360, "Pune": 180}                     # base orders/day
CATEGORIES = {"Electronics": (0.30, 10_000), "Fashion": (0.30, 4_000), "Grocery": (0.40, 2_000)}
BASE_CANCEL = 0.05
HERE = Path(__file__).parent


def base_daily(start: str, end: str, rng: np.random.Generator, cities: dict[str, int] | None = None) -> pd.DataFrame:
    days = pd.date_range(start, end, freq="D")
    doy = days.dayofyear.to_numpy()
    season = 1 + 0.10 * np.sin(2 * np.pi * (doy - 80) / 365.25)
    weekly = np.where(days.dayofweek >= 5, 1.15, 0.95)
    frames = []
    for city, base in (cities or CITIES).items():
        for cat, (share, aov) in CATEGORIES.items():
            orders = rng.poisson(base * share * season * weekly)
            cancelled = rng.binomial(orders, BASE_CANCEL)
            avg = aov * rng.normal(1.0, 0.03, len(days))
            frames.append(pd.DataFrame({
                "date": days, "city": city, "category": cat, "orders": orders, "cancelled": cancelled,
                "revenue": np.round((orders - cancelled) * avg, 2),
            }))
    return pd.concat(frames, ignore_index=True)


def plant(df: pd.DataFrame, s: dict, rng: np.random.Generator) -> pd.DataFrame:
    """kinds: mix_shift | cancel_spike | missing_days | noise_only."""
    df = df.copy()
    win = (df["date"] >= s.get("start", "1900-01-01")) & (df["date"] <= s.get("end", "2999-12-31"))
    city = df["city"] == s.get("city")
    if s["kind"] == "mix_shift":
        m = win & city & (df["category"] == s["category"])
        aov = df.loc[m, "revenue"] / (df.loc[m, "orders"] - df.loc[m, "cancelled"]).clip(lower=1)
        new_orders = rng.binomial(df.loc[m, "orders"], s["factor"])
        new_cancel = rng.binomial(new_orders, BASE_CANCEL)
        df.loc[m, "orders"], df.loc[m, "cancelled"] = new_orders, new_cancel
        df.loc[m, "revenue"] = np.round((new_orders - new_cancel) * aov, 2)
    elif s["kind"] == "cancel_spike":
        m = win & city
        aov = df.loc[m, "revenue"] / (df.loc[m, "orders"] - df.loc[m, "cancelled"]).clip(lower=1)
        new_cancel = rng.binomial(df.loc[m, "orders"], s["rate"])
        df.loc[m, "cancelled"] = new_cancel
        df.loc[m, "revenue"] = np.round((df.loc[m, "orders"] - new_cancel) * aov, 2)
    elif s["kind"] == "missing_days":
        dates = pd.date_range(s["start"], periods=s["n_days"], freq="D")
        df = df[~(city & df["date"].isin(dates))]
    return df.reset_index(drop=True)


def expand_to_orders(daily: pd.DataFrame, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Daily aggregates -> ek row per order (orders table) + payments (0.5% placed orders ka payment missing)."""
    reps = daily["orders"].to_numpy()
    idx = np.repeat(np.arange(len(daily)), reps)
    d = daily.iloc[idx].reset_index(drop=True)
    aov = (d["revenue"] / (d["orders"] - d["cancelled"]).clip(lower=1)).to_numpy()
    amount = np.round(aov * rng.lognormal(0, 0.15, len(d)), 2)
    pos = d.groupby(["date", "city", "category"]).cumcount().to_numpy()
    status = np.where(pos < d["cancelled"].to_numpy(), "cancelled", "placed")
    created = d["date"] + pd.to_timedelta(rng.integers(0, 86400, len(d)), unit="s")
    orders = pd.DataFrame({
        "order_id": np.arange(1, len(d) + 1),
        "customer_id": rng.integers(1, 5000, len(d)),
        "city": d["city"], "category": d["category"],
        "channel": np.where(rng.random(len(d)) < 0.6, "app", "web"),
        "amount": amount, "status": status,
        "created_at": created.dt.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": created.dt.strftime("%Y-%m-%d %H:%M:%S"),
    })
    paid = orders[orders["status"] == "placed"].sample(frac=0.995, random_state=1)
    payments = pd.DataFrame({
        "id": np.arange(1, len(paid) + 1), "order_id": paid["order_id"].to_numpy(), "city": paid["city"].to_numpy(),
        "method": rng.choice(["upi", "card", "cod"], len(paid), p=[0.6, 0.25, 0.15]),
        "amount": paid["amount"].to_numpy(), "paid_at": paid["created_at"].to_numpy(),
    })
    return orders, payments


def make_scenarios(n: int, rng: np.random.Generator) -> list[dict]:
    kinds = ["mix_shift", "cancel_spike", "missing_days", "noise_only"]
    out = []
    for i in range(n):
        kind = kinds[i % len(kinds)]
        city = str(rng.choice(list(CITIES)))
        s = {"id": f"S{i:04d}", "kind": kind, "city": city, "period_base": "2026-01", "period_current": "2026-02"}
        if kind == "mix_shift":
            s |= {"category": str(rng.choice(list(CATEGORIES))), "start": "2026-02-10", "end": "2026-02-28",
                  "factor": float(np.round(rng.uniform(0.55, 0.8), 2)),
                  "expected_cause": "revenue.category_mix", "expected_label": "Strong"}
        elif kind == "cancel_spike":
            s |= {"start": "2026-02-01", "end": "2026-02-28", "rate": float(np.round(rng.uniform(0.08, 0.12), 3)),
                  "expected_cause": "revenue.cancel_rate", "expected_label": "Strong"}
        elif kind == "missing_days":
            s |= {"start": "2026-02-12", "n_days": 3, "expected_cause": "tpl.data_issue",
                  "expected_label": "data_issue"}
        else:
            s |= {"expected_cause": None, "expected_label": "within_normal"}
        out.append(s)
    return out


def expected_share(base: pd.DataFrame, planted: pd.DataFrame, s: dict) -> float | None:
    """ln(R1 / R1_counterfactual) / ln(R1 / R0) — planted cause ne revenue ke total log-change ka kitna hissa banaya."""
    if s["kind"] not in ("mix_shift", "cancel_spike"):
        return None

    def tot(df, period):
        start = pd.Timestamp(f"{period}-01")
        m = (df["city"] == s["city"]) & (df["date"] >= start) & (df["date"] < start + pd.offsets.MonthBegin(1))
        return float(df.loc[m, "revenue"].sum())

    r0, r1, r1cf = tot(planted, s["period_base"]), tot(planted, s["period_current"]), tot(base, s["period_current"])
    return round(float(np.log(r1 / r1cf) / np.log(r1 / r0)), 6)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", type=int, default=50)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, default=HERE)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    (args.out / "scenarios").mkdir(parents=True, exist_ok=True)
    (args.out / "ground_truth").mkdir(parents=True, exist_ok=True)
    for s in make_scenarios(args.scenarios, rng):
        base = base_daily("2024-01-01", "2026-02-28", rng)
        df = plant(base, s, rng)
        s["expected_share"] = expected_share(base, df, s)     # 18.2: cause ka expected share of Delta
        df.to_csv(args.out / "scenarios" / f"{s['id']}.csv.gz", index=False)
        (args.out / "ground_truth" / f"{s['id']}.json").write_text(json.dumps(s, indent=2))
    print(f"wrote {args.scenarios} scenarios to {args.out}")


if __name__ == "__main__":
    main()
