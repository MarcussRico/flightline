import time

from flightline import engine
from flightline.availability import Scenario


def test_same_seed_same_numbers(ctx):
    sc = Scenario(("TAIL-05",), 7, 30)
    a = engine._compute(ctx, sc)
    b = engine._compute(ctx, sc)
    assert a.baseline.summary() == b.baseline.summary()
    assert a.plan.summary() == b.plan.summary()
    assert a.cp["inductions"] == b.cp["inductions"]
    assert a.cp["expedite_keys"] == b.cp["expedite_keys"]
    strip = lambda acts: [(x["id"], x["aircraft_days_gained"], x["sortie_days_gained"]) for x in acts]
    assert strip(a.actions) == strip(b.actions)


def test_scenario_resolves_in_under_two_seconds(ctx):
    sc = Scenario(("TAIL-09", "TAIL-10"), 15, 50)
    t0 = time.perf_counter()
    engine._compute(ctx, sc)
    assert time.perf_counter() - t0 < 2.0


def test_every_action_is_scored_and_explained(state):
    assert state.actions
    for a in state.actions:
        assert isinstance(a["aircraft_days_gained"], float)
        assert a["reason"] and a["trace"]
    gains = [a["aircraft_days_gained"] for a in state.actions]
    assert gains == sorted(gains, reverse=True)


def test_provenance_badge_says_synthetic(ctx):
    assert ctx.provenance["badge"] == "SYNTHETIC SCENARIO"
