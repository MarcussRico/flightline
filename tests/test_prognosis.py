import numpy as np

from flightline.prognosis import Interval, assess


def test_conformal_intervals_cover_about_90_percent(ctx):
    ev = ctx.model.evaluate(ctx.deg)
    assert ev["n_test_points"] >= 500
    assert 0.86 <= ev["coverage"] <= 0.96, ev


def test_coverage_holds_near_failure_not_just_on_average(ctx):
    X, y, _ = ctx.model.eval_rows(ctx.deg.split("test"), tag=13)
    _, lo, hi = ctx.model.predict_rows(X)
    near = y <= 40
    assert near.sum() > 50
    assert np.mean((y[near] >= lo[near]) & (y[near] <= hi[near])) >= 0.85


def test_abstains_only_when_interval_is_wider_than_window_and_reaches_it():
    wide_in_window = assess(Interval(point=20, lo=2, hi=60), cycles_per_day=1.0, window_days=30)
    assert wide_in_window["abstain"] and wide_in_window["status"] == "inspect"
    narrow_in_window = assess(Interval(point=20, lo=12, hi=28), cycles_per_day=1.0, window_days=30)
    assert not narrow_in_window["abstain"] and narrow_in_window["status"] == "order_now"
    wide_far_away = assess(Interval(point=200, lo=120, hi=300), cycles_per_day=1.0, window_days=30)
    assert not wide_far_away["abstain"] and wide_far_away["status"] == "monitor"


def test_days_are_cycles_divided_by_utilisation():
    a = assess(Interval(point=30, lo=15, hi=45), cycles_per_day=0.5, window_days=100)
    assert (a["rul_point"], a["rul_lo"], a["rul_hi"]) == (60, 30, 90)
