"""Scenario engine: everything the API serves, computed from one scenario.

For a scenario (groundings, spares delay, sortie surge) it runs

  1. current practice   -- greedy FIFO inductions, first-come expedites,
                           reactive cannibalisation;
  2. the FLIGHTLINE plan -- CP-SAT inductions and expedites, priced
                           cannibalisation;

through the same simulator on the model's predicted failure times, then
derives the actions, the twin queries and the cannibalisation prices from
those projections. Every number on screen comes out of here.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field, replace

import numpy as np

from . import config, metrics as metrics_mod
from .availability import (CATEGORIES, LABELS, UP, Plan, Scenario, SimResult, expedite_lead, fresh_life_mean,
                           label_matrix, non_depot_down, replay, simulate, utilisation)
from .cannibalise import INF_DAYS, price_core, refailure_delta, verdict
from .data import DegradationSet, World, connect, load_degradation, load_world
from .prognosis import Interval, Prognosis, assess, decision_window, load_or_train
from .scheduler import HAVE_ORTOOLS, bay_violations, optimise, schedule_greedy
from .twin import Twin


# ---- shared, scenario-independent context ----------------------------------------

@dataclass
class Context:
    world: World
    deg: DegradationSet
    model: Prognosis
    intervals: dict[tuple[str, str], Interval]
    evaluation: dict
    metrics: dict | None
    load_seconds: float
    model_cached: bool

    @property
    def provenance(self) -> dict:
        real = self.deg.source != "SYNTHETIC SCENARIO"
        return {
            "badge": f"{self.deg.source} DEGRADATION · SYNTHETIC LOGISTICS" if real else "SYNTHETIC SCENARIO",
            "degradation": self.deg.source,
            "logistics": "SYNTHETIC SCENARIO",
            "seed": self.world.seed,
            "real_data": real,
        }



_ctx: Context | None = None
_lock = threading.Lock()


def context() -> Context:
    global _ctx
    with _lock:
        if _ctx is None:
            t0 = time.perf_counter()
            con = connect()
            world = load_world(con)
            deg = load_degradation(con)
            con.close()
            from .ncmapss import load_if_present

            deg = load_if_present(deg) or deg
            model, cached = load_or_train(deg, list(world.parts))
            failed = {k for k, l in world.lrus.items() if l.failed}
            intervals = model.predict_installed(deg, failed)
            evaluation = model.evaluate(deg)
            mets = metrics_mod.load_cached(deg)
            _ctx = Context(world, deg, model, intervals, evaluation, mets, time.perf_counter() - t0, cached)
        return _ctx


def reset() -> None:
    """Forget the loaded context and cached scenarios (after re-seeding)."""
    global _ctx
    with _lock:
        _ctx = None
        _cache.clear()


# ---- one scenario ----------------------------------------------------------------

@dataclass
class ScenarioState:
    ctx: Context
    scenario: Scenario
    baseline: SimResult
    plan: SimResult
    nocann: SimResult
    cp: dict
    util: dict[str, float]
    assessments: dict[tuple[str, str], dict]
    twin: Twin
    actions: list[dict] = field(default_factory=list)
    cann_candidates: list[dict] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)

    # -- prognosis --------------------------------------------------------------
    def window(self, part: str) -> float:
        p = self.ctx.world.parts[part]
        return decision_window(p.lead_time_days, self.scenario.spares_delay_days,
                               self.plan.mean_depot_queue(), p.repair_days)

    def predict(self, tail: str, part: str) -> dict:
        """{rul_point, rul_lo, rul_hi (days), abstain, ...} for one installed LRU."""
        if (tail, part) not in self.assessments:
            return {"error": f"{tail} {part} is not a serviceable installed LRU"}
        return self.assessments[(tail, part)]

    # -- cannibalisation ----------------------------------------------------------
    def price_cannibalisation(self, donor: str, recipient: str, part: str) -> dict:
        """Price moving `part` from donor to recipient today, against the no-cannibalisation projection."""
        w = self.ctx.world
        R = self.nocann
        if part not in w.parts:
            return {"error": f"unknown part {part}"}
        if donor not in w.tail_base or recipient not in w.tail_base:
            return {"error": "unknown tail"}
        if donor == recipient:
            return {"error": "donor and recipient must differ"}
        base = w.tail_base[recipient]
        if w.tail_base[donor] != base:
            return {"error": f"{donor} is at {w.tail_base[donor]}, {recipient} at {base}: same-base swaps only"}
        ep = next((e for e in R.episodes.get((base, part), [])
                   if e.tail == recipient and e.need_day <= 0 and e.kind == "wait"), None)
        if ep is None:
            return {"error": f"{recipient} is not waiting for {part} today"}
        if w.lrus[(donor, part)].failed or (donor, part) not in self.ctx.intervals:
            return {"error": f"{donor} has no serviceable {part} to give"}
        p = w.parts[part]
        spare_ready = float(ep.served_day + ep.repair_days) if ep.served_day is not None else INF_DAYS
        own = {ep.wait_hold, ep.repair_hold}
        others = [h for h in R.holds if h.tail == recipient and h.hid not in own]
        row = label_matrix(others, [recipient], R.horizon)[0]
        free_idx = np.flatnonzero(row == UP)
        rec_other = float(free_idx[0]) if len(free_idx) else INF_DAYS
        donor_free = R.first_up_day(donor)
        iv = self.ctx.intervals[(donor, part)]
        u = self.util[base]
        delta = refailure_delta(iv.point, iv.lo, iv.hi, u, config.CANN_LOOKAHEAD_DAYS)
        downtime = p.lead_time_days + self.scenario.spares_delay_days + p.repair_days
        priced = price_core(spare_ready_days=spare_ready, donor_free_days=donor_free, swap_days=p.cann_days,
                            repair_hours=p.repair_hours, refail_delta=delta, refail_downtime_days=downtime,
                            recipient_other_down_days=rec_other)
        priced.update({
            "donor": donor, "recipient": recipient, "part": part, "part_name": p.name, "base": base,
            "verdict": verdict(priced, donor, recipient, donor_free, spare_ready),
            "inputs": {
                "spare_ready_days": None if spare_ready >= INF_DAYS else spare_ready,
                "donor_free_days": None if donor_free >= INF_DAYS else donor_free,
                "recipient_other_down_days": None if rec_other >= INF_DAYS else rec_other,
                "repair_hours": p.repair_hours,
                "swap_days": p.cann_days,
                "moved_part_rul_days": [iv.lo / u, iv.point / u, iv.hi / u],
                "handling_life_penalty": config.HANDLING_LIFE_PENALTY,
                "refail_downtime_days": downtime,
            },
            "assumptions": [
                f"Swap labour = {config.CANN_LABOUR_MULTIPLIER:g}x a normal repair (GAO-01-587).",
                f"Moved part loses {config.HANDLING_LIFE_PENALTY:.0%} of remaining life (modelled assumption).",
                "Donor takes the recipient's place in the spares queue.",
            ],
        })
        return priced

    # -- serialisation -------------------------------------------------------------
    def state_json(self) -> dict:
        w, ctx = self.ctx.world, self.ctx
        b, p = self.baseline.summary(), self.plan.summary()
        days = list(range(w.horizon))
        demand = sum(self.plan.demand[x] for x in w.bases)
        fleet = []
        for i, tail in enumerate(w.tails):
            lab_plan = self.plan.label[i]
            lab_base = self.baseline.label[i]
            fleet.append({
                "tail": tail,
                "base": w.tail_base[tail],
                "today": _label_name(int(lab_plan[0])),
                "criticality_sortie_days": self.twin.criticality(tail),
                "plan": lab_plan.tolist(),
                "baseline": lab_base.tolist(),
                "inspection": _insp(self, tail),
                "grounded": tail in self.scenario.ground_tails,
            })
        lrus = []
        for (tail, part), a in self.assessments.items():
            lrus.append({"tail": tail, "part": part, "part_name": w.parts[part].name,
                         "base": w.tail_base[tail], **_round(a)})
        lrus.sort(key=lambda r: (r["status"] == "monitor", r["rul_lo"]))
        counts = {s: sum(1 for r in lrus if r["status"] == s) for s in ("order_now", "inspect", "monitor")}
        return {
            "provenance": ctx.provenance,
            "scenario": _scenario_json(self.scenario),
            "horizon_days": w.horizon,
            "timings_ms": {k: round(v * 1000, 1) for k, v in self.timings.items()},
            "labels": [*LABELS, "up"],
            "categories": list(CATEGORIES),
            "baseline": _round(b),
            "plan": _round(p),
            "delta": {
                "aircraft_days": p["aircraft_days_available"] - b["aircraft_days_available"],
                "sortie_days": p["sortie_days_delivered"] - b["sortie_days_delivered"],
                "ao_points": round(100 * (p["ao"] - b["ao"]), 2),
            },
            "optimiser": {
                "engine": "CP-SAT" if HAVE_ORTOOLS else "greedy (OR-Tools unavailable)",
                "status": self.cp["status"],
                "solve_seconds": round(self.cp["solve_seconds"], 3),
                "expedites": self.cp["expedite_keys"],
                "bay_violations": bay_violations(w, self.cp["inductions"]),
            },
            "daily": {
                "day": days,
                "tasked": demand.tolist(),
                "available_baseline": self.baseline.up.sum(axis=0).tolist(),
                "available_plan": self.plan.up.sum(axis=0).tolist(),
                "flown_baseline": sum(self.baseline.delivered[x] for x in w.bases).tolist(),
                "flown_plan": sum(self.plan.delivered[x] for x in w.bases).tolist(),
            },
            "fleet": fleet,
            "prognosis": {"evaluation": _round(ctx.evaluation), "counts": counts, "lrus": lrus,
                          "utilisation": {k: round(v, 3) for k, v in self.util.items()}},
            "cannibalisation": {"candidates": self.cann_candidates[:12],
                                "lookahead_days": config.CANN_LOOKAHEAD_DAYS},
            "spares": self.twin.spare_unlock_ranking(),
            "twin": self.twin.summary(),
            "depot": _depot(self),
            "metrics": ctx.metrics,
            "parts": {k: {"name": v.name, "lead_time_days": v.lead_time_days, "repair_hours": v.repair_hours}
                      for k, v in w.parts.items()},
        }


def _label_name(i: int) -> str:
    return "up" if i == UP else LABELS[i]


def _round(d):
    if isinstance(d, dict):
        return {k: _round(v) for k, v in d.items()}
    if isinstance(d, (list, tuple)):
        return [_round(v) for v in d]
    if isinstance(d, float):
        return round(d, 4)
    if isinstance(d, (np.floating,)):
        return round(float(d), 4)
    if isinstance(d, (np.integer,)):
        return int(d)
    return d


def _scenario_json(s: Scenario) -> dict:
    return {"ground_tails": list(s.ground_tails), "spares_delay_days": s.spares_delay_days,
            "sortie_surge": s.sortie_surge_pct}


def _insp(st: ScenarioState, tail: str) -> dict | None:
    b, p = st.baseline.inductions.get(tail), st.plan.inductions.get(tail)
    if not b and not p:
        return None
    ref = p or b
    return {"due": ref["due"], "duration": ref["duration"],
            "baseline": {"start": b["start"], "depot": b["depot"]} if b else None,
            "plan": {"start": p["start"], "depot": p["depot"]} if p else None}


def _depot(st: ScenarioState) -> dict:
    rows = []
    for tail in sorted(set(st.baseline.inductions) | set(st.plan.inductions)):
        r = _insp(st, tail)
        rows.append({"tail": tail, **r})
    rows.sort(key=lambda r: (r["due"], r["tail"]))
    return {
        "depots": {d: {"bays": b, "crews": c} for d, (b, c) in st.ctx.world.depots.items()},
        "inductions": rows,
        "occupancy_plan": {d: a.tolist() for d, a in st.plan.bay_occupancy().items()},
        "occupancy_baseline": {d: a.tolist() for d, a in st.baseline.bay_occupancy().items()},
        "mean_queue_days": {"baseline": round(st.baseline.mean_depot_queue(), 2),
                            "plan": round(st.plan.mean_depot_queue(), 2)},
    }


# ---- running a scenario ---------------------------------------------------------

_cache: "OrderedDict[Scenario, ScenarioState]" = OrderedDict()
_current: Scenario = Scenario()


def normalise(ground_tails=(), spares_delay_days=0, sortie_surge=0) -> Scenario:
    ctx = context()
    tails = tuple(sorted({str(t) for t in ground_tails if str(t) in ctx.world.tail_base}))
    return Scenario(tails, int(np.clip(int(spares_delay_days), 0, 60)), int(np.clip(int(sortie_surge), 0, 100)))


def run(scenario: Scenario) -> ScenarioState:
    """Compute (or fetch) the full state for a scenario and make it current."""
    global _current
    with _lock:
        hit = _cache.get(scenario)
        if hit is not None:
            _cache.move_to_end(scenario)
            _current = scenario
            return hit
    st = _compute(context(), scenario)
    with _lock:
        _cache[scenario] = st
        while len(_cache) > 48:
            _cache.popitem(last=False)
        _current = scenario
    return st


def current() -> ScenarioState:
    return run(_current)


def _compute(ctx: Context, sc: Scenario) -> ScenarioState:
    w = ctx.world
    t0 = time.perf_counter()
    timings = {}
    remaining = {k: iv.point for k, iv in ctx.intervals.items()}
    fresh = fresh_life_mean(w)

    def sim(plan: Plan) -> SimResult:
        return simulate(w, sc, plan, remaining, fresh, ctx.intervals)

    greedy = schedule_greedy(w, sc)
    baseline = sim(Plan("Current practice", greedy, "reactive"))
    reference = sim(Plan("Reference", greedy, "priced", expedite_keys=frozenset()))
    options = expedite_options(w, reference)
    timings["simulate"] = time.perf_counter() - t0

    t1 = time.perf_counter()
    cp = optimise(w, sc, reference.demand, non_depot_down(reference), options, hint=greedy)
    timings["optimise"] = time.perf_counter() - t1

    t2 = time.perf_counter()
    plan_def = Plan("FLIGHTLINE plan", cp["inductions"], "priced", expedite_keys=frozenset(cp["expedite_keys"]))
    plan = sim(plan_def)
    nocann = sim(replace(plan_def, name="Plan without cannibalisation", cann_policy="off"))
    util = utilisation(w, sc)
    st = ScenarioState(ctx, sc, baseline, plan, nocann, cp, util, {}, Twin(w, plan, ctx.intervals, ctx.deg.installed_age))
    for (tail, part), iv in ctx.intervals.items():
        base = w.tail_base[tail]
        st.assessments[(tail, part)] = assess(iv, util[base], st.window(part))
    st.cann_candidates = cann_candidates(st)
    st.actions = build_actions(st, greedy, plan_def, sim)
    timings["actions"] = time.perf_counter() - t2
    timings["total"] = time.perf_counter() - t0
    st.timings = timings
    return st


def expedite_options(w: World, reference: SimResult) -> list[dict]:
    """For each order the plan could expedite: the tail-days it would return to the line (first-order)."""
    nd = non_depot_down(reference)
    out = []
    for (base, part), sup in sorted(reference.supply.items()):
        lead = w.parts[part].lead_time_days
        for arrival, key, placed in sup["arrivals"]:
            if key.startswith("X:"):
                continue
            new = min(arrival, expedite_lead(lead)) if not key.startswith("F:") else min(arrival, placed + expedite_lead(lead))
            if new >= arrival or new >= w.horizon:
                continue
            r = replay(reference, expedite={key: new})
            gained = nd & ~r["non_depot_down"]
            if gained.any():
                out.append({"key": key, "base": base, "part": part, "arrival": arrival, "expedited_arrival": new,
                            "days": [(int(i), int(t)) for i, t in np.argwhere(gained)]})
    return out


def cann_candidates(st: ScenarioState) -> list[dict]:
    """Every same-base swap that could fly a tail waiting for a part today, priced and ranked."""
    w = st.ctx.world
    out = []
    for (base, part), eps in sorted(st.nocann.episodes.items()):
        for ep in eps:
            if ep.need_day > 0 or ep.kind != "wait":
                continue
            for donor in w.tails_at(base):
                if donor == ep.tail or (donor, part) not in st.ctx.intervals:
                    continue
                pr = st.price_cannibalisation(donor, ep.tail, part)
                if "error" not in pr:
                    out.append(pr)
    out.sort(key=lambda r: (-r["net_aircraft_days"], r["recipient"], r["donor"]))
    return out


# ---- actions -----------------------------------------------------------------------

def _gain(a: SimResult, b: SimResult) -> tuple[int, int]:
    """(aircraft-days, sortie-days) of a over b."""
    return (int(a.up.sum() - b.up.sum()),
            int(sum(a.delivered[x].sum() for x in a.delivered) - sum(b.delivered[x].sum() for x in b.delivered)))


def build_actions(st: ScenarioState, greedy: dict, plan_def: Plan, sim) -> list[dict]:
    """Ranked recommendations, each scored in aircraft-days with a causal trace.

    Plan components are valued leave-one-out (the plan with vs without that
    piece, both simulated); orders and inspections by first-order replay on
    top of the plan; cannibalisations by the price model.
    """
    w, ctx, sc = st.ctx.world, st.ctx, st.scenario
    plan = st.plan
    actions: list[dict] = []

    # 1. Depot re-sequencing.
    changed = [t for t in plan.inductions
               if (plan.inductions[t]["start"], plan.inductions[t]["depot"]) != greedy.get(t)]
    if changed:
        without = sim(replace(plan_def, inductions=greedy))
        ad, sd = _gain(plan, without)
        lines = []
        for t in sorted(changed, key=lambda x: plan.inductions[x]["start"]):
            pi, g = plan.inductions[t], greedy.get(t)
            when = "after the horizon" if pi["start"] >= w.horizon else f"day {pi['start']}"
            overlap = int(np.sum(non_depot_down(plan)[w.tails.index(t), pi["start"]:pi["start"] + pi["duration"]]))
            note = f"; overlaps {overlap} day(s) it is already down" if overlap else ""
            lines.append(f"{t}: {pi['depot']} {when} (due day {pi['due']}; current practice day {g[0]}){note}")
        actions.append(_action(
            "depot-plan", "depot", f"Re-sequence {len(changed)} depot induction(s)", ad, sd, "simulated",
            f"Induct early or alongside existing downtime instead of first-come at the due date; mean bay queue "
            f"{st.baseline.mean_depot_queue():.1f} -> {plan.mean_depot_queue():.1f} days.",
            [{"silo": "technical records", "text": l} for l in lines] + [
                {"silo": "MRO", "text": f"Bays: " + ", ".join(f"{d} x{b}" for d, (b, _) in sorted(w.depots.items()))
                 + "; one induction crew per depot per day. Capacity violations: "
                 + str(len(bay_violations(w, st.cp["inductions"])))},
                {"silo": "simulator", "text": f"Plan with these inductions vs plan with current-practice inductions: "
                 f"{ad:+d} aircraft-days, {sd:+d} sortie-days."},
            ]))

    # 2. Expedites.
    exp_info = {e["key"]: e for e in plan.expedited}
    for key in st.cp["expedite_keys"]:
        e = exp_info.get(key)
        if e is None:
            continue
        without = sim(replace(plan_def, expedite_keys=plan_def.expedite_keys - {key}))
        ad, sd = _gain(plan, without)
        part = w.parts[e["part"]]
        who = _order_for(key, w)
        actions.append(_action(
            f"expedite-{key}", "expedite", f"Expedite {e['part']} to {e['base']}", ad, sd, "simulated",
            f"{who}: lands day {e['expedited_arrival']} instead of day {e['normal_arrival']} "
            f"({part.name}, AOG priority).",
            [
                {"silo": "spares", "text": f"Order {key}: {part.name}, placed day {e['placed_day']}, "
                 f"lead {part.lead_time_days} d + scenario delay {sc.spares_delay_days} d -> day {e['normal_arrival']}."},
                {"silo": "spares", "text": f"AOG priority lead max({config.EXPEDITE_MIN_DAYS}, "
                 f"{config.EXPEDITE_FRACTION:.0%} x {part.lead_time_days}) = {expedite_lead(part.lead_time_days)} d, "
                 f"not held by the convoy -> day {e['expedited_arrival']}."},
                {"silo": "optimiser", "text": f"Chosen by CP-SAT within a budget of {config.EXPEDITE_BUDGET} expedites."},
                {"silo": "simulator", "text": f"Plan with vs without this expedite: {ad:+d} aircraft-days, {sd:+d} sortie-days."},
            ]))

    # 3. Cannibalisation policy and today's swaps.
    reactive = sim(replace(plan_def, cann_policy="reactive"))
    ad, sd = _gain(plan, reactive)
    n_priced = sum(1 for e in plan.events if e["type"] == "cannibalisation")
    n_react = sum(1 for e in reactive.events if e["type"] == "cannibalisation")
    if ad > 0 or sd > 0:
        actions.append(_action(
            "cann-policy", "policy", "Authorise cannibalisation only when its price is positive", ad, sd, "simulated",
            f"{n_priced} priced swaps instead of {n_react} reactive ones over the horizon: rob aircraft that are "
            f"staying down anyway, never one that is about to fly.",
            [{"silo": "simulator", "text": f"Priced policy vs reactive policy, rest of plan unchanged: "
              f"{ad:+d} aircraft-days, {sd:+d} sortie-days."},
             {"silo": "assumption", "text": f"Swap labour {config.CANN_LABOUR_MULTIPLIER:g}x a normal repair; moved part "
              f"loses {config.HANDLING_LIFE_PENALTY:.0%} of remaining life (modelled)."}]))
    for c in st.cann_candidates:
        if c["net_aircraft_days"] <= 0:
            continue
        if any(a["type"] == "cannibalise" and a["meta"]["recipient"] == c["recipient"] for a in actions):
            continue
        actions.append(_action(
            f"cann-{c['donor']}-{c['recipient']}-{c['part']}", "cannibalise",
            f"Cannibalise {c['part']} from {c['donor']} to {c['recipient']}", c["net_aircraft_days"], None, "priced",
            c["verdict"],
            [{"silo": "spares", "text": f"{c['recipient']} waits {_d(c['inputs']['spare_ready_days'])} for its spare."},
             {"silo": "technical records", "text": f"{c['donor']} would fly again in {_d(c['inputs']['donor_free_days'])}."},
             {"silo": "MRO", "text": f"Swap takes {c['swap_days']} day(s), +{c['extra_manhours']:g} man-hours."},
             {"silo": "health monitoring", "text": f"Re-failure risk on the moved part +{c['refailure_risk_delta']:.1%} "
              f"(expected {c['refailure_expected_days']:.1f} aircraft-days)."},
             {"silo": "price", "text": f"Net {c['net_aircraft_days']:+.1f} aircraft-days over {c['lookahead_days']} days."}],
            meta={"recipient": c["recipient"], "donor": c["donor"], "part": c["part"]}))

    # 4. Orders and inspections from the prognosis.
    plan_ad = int(plan.up.sum())
    plan_sd = int(sum(plan.delivered[x].sum() for x in w.bases))
    for (tail, part), a in sorted(st.assessments.items(), key=lambda kv: kv[1]["rul_lo"]):
        if a["status"] == "monitor":
            continue
        base = w.tail_base[tail]
        p = w.parts[part]
        lands = p.lead_time_days + sc.spares_delay_days
        r = replay(plan, extra_units={(base, part): [lands]})
        ad, sd = r["aircraft_days"] - plan_ad, r["sortie_days"] - plan_sd
        on_hand = w.stock[(base, part)]
        iv_txt = f"{a['rul_lo']:.0f}-{a['rul_hi']:.0f} days (90%)"
        trace = [
            {"silo": "health monitoring", "text": f"{tail} {p.name}: {ctx.deg.installed_age[(tail, part)]} cycles since "
             f"install; RUL {a['rul_lo_cycles']:.0f}-{a['rul_hi_cycles']:.0f} cycles at "
             f"{st.util[base]:.2f} sorties/day = {iv_txt}."},
            {"silo": "decision window", "text": f"lead {p.lead_time_days} + delay {sc.spares_delay_days} + depot queue "
             f"{plan.mean_depot_queue():.1f} + fit {p.repair_days} = {a['decision_window_days']:.1f} days."},
            {"silo": "spares", "text": f"{base} holds {on_hand} on the shelf; an order placed today lands day {lands}."},
            {"silo": "replay", "text": f"One more unit landing day {lands}: {ad:+d} aircraft-days, {sd:+d} sortie-days "
             f"(failure timeline held fixed)."},
        ]
        if a["status"] == "order_now":
            if ad <= 0 and sd <= 0:
                continue
            actions.append(_action(
                f"order-{tail}-{part}", "order", f"Order {part} for {base} today", ad, sd, "replay",
                f"{tail}'s {p.name} is predicted to fail in {iv_txt}, inside its {a['decision_window_days']:.0f}-day "
                f"decision window, and {base}'s shelf will not cover it.",
                trace, meta={"tail": tail, "part": part}))
        else:
            trace.insert(2, {"silo": "abstention", "text": f"Interval width {a['interval_width_days']:.0f} d > window "
                             f"{a['decision_window_days']:.0f} d and its lower edge is inside the window: "
                             f"the model cannot tell 'order today' from 'not yet'."})
            actions.append(_action(
                f"inspect-{tail}-{part}", "inspect", f"Inspect {tail} {part}", ad, sd, "replay, if confirmed",
                f"Model abstains: {iv_txt} is wider than the {a['decision_window_days']:.0f}-day decision window. "
                + (f"If inspection confirms wear, ordering today recovers up to {ad} aircraft-days."
                   if ad > 0 else f"Stock at {base} would cover a failure, so no aircraft-days ride on it."),
                trace, meta={"tail": tail, "part": part}))

    actions.sort(key=lambda a: (-a["aircraft_days_gained"], -(a["sortie_days_gained"] or 0), a["id"]))
    for i, a in enumerate(actions, 1):
        a["rank"] = i
    return actions


def _action(aid, kind, title, ad, sd, method, reason, trace, meta=None) -> dict:
    return {"id": aid, "type": kind, "title": title, "aircraft_days_gained": round(float(ad), 2),
            "sortie_days_gained": None if sd is None else int(sd), "method": method, "reason": reason,
            "trace": trace, "meta": meta or {}}


def _order_for(key: str, w: World) -> str:
    if key.startswith("F:"):
        _, tail, part, n = key.split(":")
        return f"Replacement for {tail}'s failure #{n}"
    o = next((o for o in w.orders if o.order_id == key), None)
    if o and o.for_tail:
        return f"Order {key} for grounded {o.for_tail}"
    return f"Replenishment order {key}"


def _d(v) -> str:
    return "beyond the horizon" if v is None else f"{v:.0f} days"
