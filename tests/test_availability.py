import numpy as np

from flightline.availability import CATEGORIES, replay


def test_attribution_components_sum_to_the_availability_gap(state):
    for res in (state.baseline, state.plan, state.nocann):
        s = res.summary()
        assert abs(sum(s["attribution"].values()) - s["gap"]) < 1e-12
        total = s["aircraft_days_total"]
        assert sum(s["attribution_days"].values()) == total - s["planned_maintenance_days"] - s["aircraft_days_available"]
        assert set(s["attribution"]) == set(CATEGORIES)


def test_grounded_tails_are_attributed_to_directed_grounding(state):
    s = state.baseline.summary()
    expected = len(state.scenario.ground_tails) * state.baseline.horizon
    assert s["attribution_days"]["directed_grounding"] == expected


def test_replay_without_changes_reproduces_the_simulation(state):
    res = state.baseline
    for loc in res.supply:
        r = replay(res, extra_units={loc: []})
        assert np.array_equal(r["up"], res.up), loc


def test_sortie_days_never_exceed_tasking_or_availability(state):
    res = state.plan
    for b, d in res.demand.items():
        rows = [i for i, t in enumerate(res.tails) if res.tail_base[t] == b]
        assert np.all(res.delivered[b] <= d)
        assert np.all(res.delivered[b] <= res.up[rows].sum(axis=0))
