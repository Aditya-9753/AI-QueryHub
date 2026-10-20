"""Worked example (Ch 10) — numbers Ch 13.8 se match hone chahiye."""
import math

import pytest

from app.services.analytics.baseline import per_day, per_day_delta, z_score
from app.services.analytics.decomposition import log_decomposition, mix_rate, segment_contribution, shapley
from app.services.analytics.did import diff_in_diff, select_controls

JAN = {"days": 31, "opd": 10_000 / 31, "aov": 5000}
FEB = {"days": 28, "opd": 9_000 / 28, "aov": 4512}
LAKH = 1e5


def test_log_decomposition_shares():
    d = log_decomposition(JAN, FEB)
    assert d["days"]["share"] == pytest.approx(0.489, abs=1e-3)
    assert d["opd"]["share"] == pytest.approx(0.017, abs=1e-3)
    assert d["aov"]["share"] == pytest.approx(0.494, abs=1e-3)
    assert sum(v["share"] for v in d.values()) == pytest.approx(1.0)
    assert d["days"]["amount"] / LAKH == pytest.approx(-45.95, abs=0.01)
    assert d["opd"]["amount"] / LAKH == pytest.approx(-1.62, abs=0.01)
    assert d["aov"]["amount"] / LAKH == pytest.approx(-46.36, abs=0.01)


def test_mix_rate():
    s0 = {"E": 0.30, "F": 0.30, "G": 0.40}
    s1 = {"E": 0.24, "F": 0.32, "G": 0.44}
    a0 = {"E": 10_000, "F": 4_000, "G": 2_000}
    a1 = {"E": 9_800, "F": 4_000, "G": 2_000}
    r = mix_rate(s0, s1, a0, a1)
    assert r["mix"] == pytest.approx(-440)
    assert r["rate"] == pytest.approx(-48)
    assert r["total"] == pytest.approx(4512 - 5000)


def test_shapley_sums_to_total():
    f = lambda x: x["days"] * x["opd"] * x["aov"]  # noqa: E731
    phi = shapley(f, JAN, FEB)
    assert sum(phi.values()) == pytest.approx(f(FEB) - f(JAN))
    assert phi["days"] / LAKH == pytest.approx(-45.95, abs=0.5)
    assert phi["aov"] / LAKH == pytest.approx(-46.36, abs=0.5)


def test_segment_contribution():
    c = segment_contribution({"E": 300, "F": 120, "G": 80}, {"E": 212, "F": 118, "G": 80})
    assert sum(c.values()) == pytest.approx(1.0)
    assert c["E"] == pytest.approx(88 / 90)


def test_per_day_and_z():
    assert per_day(5.00e7, 31) / LAKH == pytest.approx(16.13, abs=0.01)
    assert per_day_delta(5.00e7, 31, 4.0608e7, 28) == pytest.approx(-0.101, abs=1e-3)
    assert z_score(14.5, 15.9, 0.45) == pytest.approx(-3.11, abs=0.01)


def test_did():
    assert diff_in_diff(1.0, 0.899, 1.0, 0.980) == pytest.approx(math.log(0.899 / 0.980))
    assert diff_in_diff(1.0, 0.899, 1.0, 0.980) == pytest.approx(-0.086, abs=1e-3)


def test_select_controls():
    target = [100, 110, 120, 130, 125, 140]
    picked = select_controls(target, {
        "Mumbai": [120, 131, 140, 155, 150, 166],     # correlated, similar size
        "Tiny": [10, 11, 12, 13, 12, 14],              # correlated but too small
        "Random": [100, 80, 130, 90, 140, 70],         # uncorrelated
    })
    assert picked == ["Mumbai"]
