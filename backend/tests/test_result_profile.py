"""ANALYZE result profiling: roles, shape aur insights ke numbers result se exactly aane chahiye."""
from app.services.analytics.result_profile import column_roles, fmt_value, profile_result


def test_roles_and_shapes():
    assert column_roles(["city", "revenue"], [["Delhi", 10.0]]) == {"city": "dimension", "revenue": "measure"}
    assert column_roles(["month", "orders"], [["2026-01", 5], ["2026-02", 6]])["month"] == "time"
    assert column_roles(["month", "orders"], [[1, 5], [2, 6]])["month"] == "time"      # integer month = time axis
    assert column_roles(["order_id", "amount"], [[1, 2.0]])["order_id"] == "id"
    assert profile_result(["total"], [[42.0]])["shape"] == "scalar"


def test_breakdown_share_concentration_and_outlier():
    rows = [["Delhi", 500.0], ["Mumbai", 300.0], ["Pune", 100.0], ["Jaipur", 60.0], ["Agra", 40.0]]
    p = profile_result(["city", "revenue"], rows, "city-wise revenue", {"category": ["A", "B"], "city": ["x"]})
    assert p["shape"] == "breakdown" and p["measure"] == "revenue" and p["dimension"] == "city"
    assert p["stats"]["total"] == 1000.0
    top = next(i for i in p["insights"] if i["kind"] == "top")
    assert top["values"]["label"] == "Delhi" and abs(top["values"]["share"] - 0.5) < 1e-9
    conc = next(i for i in p["insights"] if i["kind"] == "concentration")
    assert abs(conc["values"]["top3"] - 0.9) < 1e-9 and conc["values"]["pareto_k"] == 2
    assert p["followups"][0]["question"].endswith("only city = Delhi, broken down by category")


def test_ratio_measure_is_not_summed():
    p = profile_result(["city", "cancel_rate"], [["Delhi", 0.05], ["Pune", 0.08]])
    assert p["stats"]["total"] is None and p["format"] == "pct"
    assert not any(i["kind"] == "concentration" for i in p["insights"])


def test_timeseries_trend_and_biggest_move():
    rows = [["2025-11", 100.0], ["2025-09", 80.0], ["2025-10", 90.0], ["2025-12", 150.0]]   # unsorted on purpose
    p = profile_result(["month", "orders"], rows)
    assert p["shape"] == "timeseries"
    trend = next(i for i in p["insights"] if i["kind"] == "trend")
    assert abs(trend["values"]["change"] - (150 / 80 - 1)) < 1e-9
    move = next(i for i in p["insights"] if i["kind"] == "move")
    assert move["values"]["period"] == "2025-12" and abs(move["values"]["change"] - 0.5) < 1e-9


def test_matrix_pattern():
    rows = [["Delhi", "app", 5.0], ["Delhi", "web", 3.0], ["Pune", "app", 4.0], ["Pune", "web", 1.0]]
    p = profile_result(["city", "channel", "revenue"], rows)
    assert p["shape"] == "matrix"
    assert next(i for i in p["insights"] if i["kind"] == "pattern")["values"]["leader"] == "app"


def test_money_format_uses_lakh_crore():
    assert fmt_value(11838782.85, "revenue") == "₹1.18 Cr"
    assert fmt_value(250000, "amount") == "₹2.50 L"
    assert fmt_value(1200, "orders") == "1,200"


def test_contact_and_one_to_one_columns_are_attributes_not_a_matrix():
    rows = [["Diya", "diya@example.com", 64.0], ["Tara", "tara@example.com", 61.0], ["Arjun", "arjun@example.com", 58.0]]
    p = profile_result(["name", "email", "total_spend"], rows)
    assert p["roles"]["email"] == "attribute" and p["shape"] == "breakdown" and p["dimension"] == "name"
    # asli 2-dimension result (repeat hote values) matrix hi rehta hai
    m = profile_result(["city", "channel", "revenue"], [["Delhi", "app", 5.0], ["Delhi", "web", 3.0], ["Pune", "app", 4.0]])
    assert m["shape"] == "matrix"
