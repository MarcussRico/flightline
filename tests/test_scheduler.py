import numpy as np

from flightline.scheduler import bay_violations, schedule_greedy


def test_optimiser_never_violates_bay_capacity(state):
    w = state.ctx.world
    assert state.cp["status"] in ("OPTIMAL", "FEASIBLE")
    assert bay_violations(w, state.cp["inductions"]) == []
    for res in (state.plan, state.baseline):
        for depot, occ in res.bay_occupancy().items():
            assert np.all(occ <= w.depots[depot][0]), depot


def test_greedy_baseline_is_feasible(state):
    w = state.ctx.world
    assert bay_violations(w, schedule_greedy(w, state.scenario)) == []


def test_every_due_inspection_is_scheduled_once(state):
    due = {t for t, i in state.ctx.world.inspections.items()
           if i.due_day < state.ctx.world.horizon and t not in state.scenario.ground_tails}
    assert set(state.cp["inductions"]) == due


def test_plan_beats_current_practice_in_the_simulator(state):
    b, p = state.baseline.summary(), state.plan.summary()
    assert p["sortie_days_delivered"] >= b["sortie_days_delivered"]
    assert p["aircraft_days_available"] > b["aircraft_days_available"]
