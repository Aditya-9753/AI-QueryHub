from app.services.challenge.battery import run_challenge_battery
from app.services.challenge.resolver import contradiction_penalty, resolve
from app.services.verify.anomaly_gate import gate_from_band
from app.services.verify.data_health import run_data_health


def test_worked_example_battery_upheld():
    health = run_data_health({"days_with_data": 28, "expected_days": 28, "null_rate": 0.002, "duplicate_count": 0})
    results = run_challenge_battery({
        "this_year_delta": -0.101, "last_year_delta": -0.015,
        "n": 2160, "n_required": 800, "health": health,
        "mix": -440, "rate": -48, "claimed_type": "mix",
    })
    assert {r.type for r in results} == {"seasonality", "small_sample", "data_quality", "simpson"}
    assert resolve(results) == "upheld"
    assert contradiction_penalty(results) == 0.0


def test_seasonal_drop_overturned():
    results = run_challenge_battery({"this_year_delta": -0.10, "last_year_delta": -0.095})
    assert resolve(results) == "overturned"


def test_wrong_claim_type_revised():
    assert resolve(run_challenge_battery({"mix": -48, "rate": -440, "claimed_type": "mix"})) == "revised"


def test_data_health_gate():
    assert not run_data_health({"days_with_data": 20, "expected_days": 28}).ok
    assert not run_data_health({"duplicate_count": 3}).ok


def test_anomaly_gate_worked_example():
    g = gate_from_band(14.5, 15.9, 0.45)
    assert g["status"] == "anomaly" and round(g["z"], 2) == -3.11
    assert gate_from_band(15.5, 15.9, 0.45)["status"] == "within_normal"
