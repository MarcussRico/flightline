"""Depot inductions and spares expediting.

`schedule_greedy` is current practice: induct each aircraft on the day its
inspection falls due, first-come first-served into the first free bay, and
expedite orders for grounded aircraft in the order they come up.

`optimise` is a CP-SAT model over the same decisions -- which tail enters
which depot bay on which day, and which orders are expedited -- maximising
sortie-days delivered (aircraft-days as tie-break), subject to bay capacity,
one induction crew per depot per day, inspection windows from the technical
records and the expedite budget. It sees the rest of the fleet's downtime
(failures, spares waits) from a reference projection, so it can, for example,
put an aircraft into the bay while it is already waiting for a part.

Whatever the model returns is re-evaluated by the full simulator; the
headline delta is simulator-vs-simulator, never the model's own objective.
"""

from __future__ import annotations

import time
from collections import defaultdict

import numpy as np

from . import config
from .availability import Scenario
from .data import World

MAX_DEFERRAL_DAYS = 30

try:
    from ortools.sat.python import cp_model

    HAVE_ORTOOLS = True
except ImportError:  # pragma: no cover - exercised only on a broken install
    cp_model = None
    HAVE_ORTOOLS = False


def _due_inspections(world: World, scenario: Scenario):
    return sorted(
        (i for i in world.inspections.values()
         if i.tail not in scenario.ground_tails and i.due_day < world.horizon),
        key=lambda i: (i.due_day, i.tail),
    )


def schedule_greedy(world: World, scenario: Scenario) -> dict[str, tuple[int, str]]:
    """Current practice: induct at the due day, or the first day after it with a free bay and crew.

    Returns {tail: (start_day, depot_id)}.
    """
    pad = world.horizon + 400
    occ = {d: np.zeros(pad, dtype=int) for d in world.depots}
    crew = {d: np.zeros(pad, dtype=int) for d in world.depots}
    out = {}
    for insp in _due_inspections(world, scenario):
        best = None
        for d, (bays, crews) in sorted(world.depots.items()):
            s = max(insp.due_day, 0)
            while not (crew[d][s] < crews and np.all(occ[d][s:s + insp.duration_days] < bays)):
                s += 1
            if best is None or s < best[0]:
                best = (s, d)
        s, d = best
        occ[d][s:s + insp.duration_days] += 1
        crew[d][s] += 1
        out[insp.tail] = (int(s), d)
    return out


def bay_violations(world: World, inductions: dict[str, tuple[int, str]]) -> list[str]:
    """Every (depot, day) where bays or induction crews are oversubscribed. Empty means feasible."""
    pad = world.horizon + 400
    occ = {d: np.zeros(pad, dtype=int) for d in world.depots}
    crew = {d: np.zeros(pad, dtype=int) for d in world.depots}
    for tail, (s, d) in inductions.items():
        dur = world.inspections[tail].duration_days
        occ[d][s:s + dur] += 1
        crew[d][s] += 1
    out = []
    for d, (bays, crews) in world.depots.items():
        for t in np.flatnonzero(occ[d] > bays):
            out.append(f"{d} day {t}: {occ[d][t]} aircraft in {bays} bays")
        for t in np.flatnonzero(crew[d] > crews):
            out.append(f"{d} day {t}: {crew[d][t]} inductions with {crews} crew(s)")
    return out


def optimise(world: World, scenario: Scenario, demand: dict[str, np.ndarray], non_depot_down: np.ndarray,
             expedite_options: list[dict], budget: int = config.EXPEDITE_BUDGET,
             hint: dict[str, tuple[int, str]] | None = None) -> dict:
    """CP-SAT schedule of inductions and expedites.

    non_depot_down: (tails, days) mask of downtime the schedule cannot move
        (failures, spares waits, groundings) from the reference projection.
    expedite_options: [{key, days: [(tail_index, day), ...]}] -- the tail-days
        each expedite would return to the line.
    Returns {inductions, expedite_keys, status, objective, solve_seconds}.
    """
    if not HAVE_ORTOOLS:
        return {"status": "UNAVAILABLE", "inductions": schedule_greedy(world, scenario), "expedite_keys": [],
                "objective": None, "solve_seconds": 0.0}
    t0 = time.perf_counter()
    T = world.horizon
    tails = world.tails
    m = cp_model.CpModel()

    z = {o["key"]: m.new_bool_var(f"x_{o['key']}") for o in expedite_options}
    if z:
        m.add(sum(z.values()) <= budget)
    cover: dict[tuple[int, int], list] = defaultdict(list)
    for o in expedite_options:
        for i, t in o["days"]:
            cover[(i, t)].append(z[o["key"]])

    depots = sorted(world.depots)
    inspections = _due_inspections(world, scenario)
    y: dict[tuple[str, int, str], cp_model.IntVar] = {}
    bay_terms: dict[tuple[int, int], list] = defaultdict(list)  # (tail index, day) -> vars putting it in a bay
    overdue_terms: dict[tuple[int, int], list] = defaultdict(list)
    depot_terms: dict[tuple[str, int], list] = defaultdict(list)
    crew_terms: dict[tuple[str, int], list] = defaultdict(list)
    for insp in inspections:
        i = tails.index(insp.tail)
        # Induct up to EARLY_INDUCTION_DAYS early or MAX_DEFERRAL_DAYS late,
        # or defer past the horizon (start = T).
        latest = min(T - 1, insp.due_day + MAX_DEFERRAL_DAYS)
        starts = [*range(max(0, insp.due_day - config.EARLY_INDUCTION_DAYS), latest + 1), T]
        choice = []
        for s in starts:
            for d in (depots if s < T else depots[:1]):
                v = m.new_bool_var(f"y_{insp.tail}_{s}_{d}")
                y[(insp.tail, s, d)] = v
                choice.append(v)
                if s < T:
                    crew_terms[(d, s)].append(v)
                for t in range(s, min(s + insp.duration_days, T)):
                    bay_terms[(i, t)].append(v)
                    depot_terms[(d, t)].append(v)
                for t in range(insp.due_day, min(s, T)):
                    overdue_terms[(i, t)].append(v)
        m.add_exactly_one(choice)
    for (d, t), vs in depot_terms.items():
        m.add(sum(vs) <= world.depots[d][0])
    for (d, t), vs in crew_terms.items():
        m.add(sum(vs) <= world.depots[d][1])

    up: dict[tuple[int, int], object] = {}  # a BoolVar, or the constant 1 where no decision can touch it
    for i, tail in enumerate(tails):
        for t in range(T):
            fixed_down = bool(non_depot_down[i, t]) and (i, t) not in cover
            if fixed_down:
                continue
            if not non_depot_down[i, t] and not bay_terms.get((i, t)) and not overdue_terms.get((i, t)):
                up[(i, t)] = 1
                continue
            v = m.new_bool_var(f"u_{i}_{t}")
            if bay_terms.get((i, t)):
                m.add(v + sum(bay_terms[(i, t)]) <= 1)
            if overdue_terms.get((i, t)):
                m.add(v + sum(overdue_terms[(i, t)]) <= 1)
            if non_depot_down[i, t]:
                m.add(v <= sum(cover[(i, t)]))
            up[(i, t)] = v

    flown = []
    for b in world.bases:
        rows = [i for i, tail in enumerate(tails) if world.tail_base[tail] == b]
        for t in range(T):
            cap = int(demand[b][t])
            avail = [up[(i, t)] for i in rows if (i, t) in up]
            f = m.new_int_var(0, cap, f"f_{b}_{t}")
            m.add(f <= sum(avail)) if avail else m.add(f == 0)
            flown.append(f)
    # Sortie-days first; aircraft-days only break ties.
    m.maximize(len(tails) * T * sum(flown) + sum(v for v in up.values() if not isinstance(v, int)))

    # Warm start from current practice, so the search begins from a feasible plan.
    hint = hint if hint is not None else schedule_greedy(world, scenario)
    for (tail, s, d), v in y.items():
        if tail in hint:
            hs, hd = hint[tail]
            m.add_hint(v, int(min(hs, T) == s and (hd == d or s == T)))
    for v in z.values():
        m.add_hint(v, 0)

    # Interleaved workers run in one thread in a fixed order: portfolio search,
    # but the same answer on every run and every machine. The budget is in
    # deterministic work units; a larger one is tried only if the first finds
    # no solution at all.
    for budget_units in (config.CP_DETERMINISTIC_TIME, 4 * config.CP_DETERMINISTIC_TIME):
        solver = cp_model.CpSolver()
        solver.parameters.num_workers = 8
        solver.parameters.interleave_search = True
        solver.parameters.random_seed = 0
        solver.parameters.max_deterministic_time = budget_units
        status = solver.solve(m)
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            break
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {"status": solver.status_name(status), "inductions": schedule_greedy(world, scenario),
                "expedite_keys": [], "objective": None, "solve_seconds": time.perf_counter() - t0}
    inductions = {}
    for (tail, s, d), v in y.items():
        if solver.value(v):
            inductions[tail] = (s, d)
    keys = sorted(k for k, v in z.items() if solver.value(v))
    return {
        "status": solver.status_name(status),
        "inductions": inductions,
        "expedite_keys": keys,
        "objective": solver.objective_value,
        "bound": solver.best_objective_bound,
        "solve_seconds": time.perf_counter() - t0,
    }
