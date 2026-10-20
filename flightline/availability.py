"""Discrete-time fleet simulator and lost-availability attribution.

The fleet is stepped one day at a time over the horizon. Every reason an
aircraft is on the ground is a *hold* with a kind, a start day and an end day:

    grounded        directed grounding (scenario)            -> directed_grounding
    bay             in a depot bay for its phase inspection  -> planned
    overdue         inspection due, no bay yet               -> depot_contention
    wait            failed LRU, no spare on the shelf        -> spares_lead_time
    repair          remove-and-replace labour                -> unscheduled_removal
    cann_wait       donor waiting for the part robbed from it   \
    cann_extra      the swap's extra labour                      | -> cannibalisation_cascade
    refail_wait     a moved part failed again, no spare          |
    cascade_repair  labour after a cann_wait / refail_wait      /

Each tail-day takes the label of its highest-priority active hold, so every
down day is counted exactly once. The availability ceiling is what the fleet
would achieve if only planned maintenance took aircraft down; the gap between
ceiling and achieved Ao is therefore *exactly* the sum of the other labels.

Spares follow a base-stock (S-1, S) policy: every failure orders one
replacement, and arrivals serve waiting aircraft first-come first-served.

Units: days, aircraft-days (one aircraft available for one day), sortie-days
(one tasked aircraft-day actually flown), cycles (sorties, for wear).
"""

from __future__ import annotations

import hashlib
import heapq
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from . import config
from .cannibalise import INF_DAYS, price_core, refailure_delta
from .data import World
from .prognosis import Interval

CATEGORIES = (
    "spares_lead_time",
    "depot_contention",
    "unscheduled_removal",
    "cannibalisation_cascade",
    "directed_grounding",
)
LABELS = ("directed_grounding", "planned", "depot_contention", "spares_lead_time",
          "cannibalisation_cascade", "unscheduled_removal")  # priority order
UP = len(LABELS)
KIND_LABEL = {
    "grounded": 0, "bay": 1, "overdue": 2, "wait": 3,
    "cann_wait": 4, "cann_extra": 4, "refail_wait": 4, "cascade_repair": 4,
    "repair": 5,
}
WAIT_KINDS = ("wait", "cann_wait", "refail_wait")
DEPOT_KINDS = ("bay", "overdue")
OPEN = 10**9
# Current practice does not rob an aircraft that is about to fly again.
REACTIVE_MIN_DONOR_DOWN_DAYS = 3


@dataclass(frozen=True)
class Scenario:
    ground_tails: tuple[str, ...] = ()
    spares_delay_days: int = 0
    sortie_surge_pct: int = 0

    def demand(self, world: World) -> dict[str, np.ndarray]:
        """Aircraft tasked per base per day, with the surge applied to the first SURGE_WINDOW_DAYS."""
        out = {}
        w = min(config.SURGE_WINDOW_DAYS, world.horizon)
        for b in world.bases:
            d = world.demand[b].astype(float).copy()
            d[:w] = np.round(d[:w] * (1 + self.sortie_surge_pct / 100.0))
            out[b] = np.minimum(d, len(world.tails_at(b))).astype(int)
        return out


def utilisation(world: World, scenario: Scenario) -> dict[str, float]:
    """Planned cycles (sorties) per day for each flying tail, by base, averaged over the horizon."""
    demand = scenario.demand(world)
    out = {}
    for b in world.bases:
        flying = [t for t in world.tails_at(b) if t not in scenario.ground_tails]
        out[b] = float(demand[b].mean() / max(len(flying), 1))
    return out


def expedite_lead(lead_days: int) -> int:
    """Lead time in days when an order is expedited at AOG priority."""
    return max(config.EXPEDITE_MIN_DAYS, math.ceil(config.EXPEDITE_FRACTION * lead_days))


@dataclass
class Plan:
    name: str
    inductions: dict[str, tuple[int, str]]  # tail -> (start day, depot); start >= horizon = deferred
    cann_policy: str = "reactive"  # reactive | priced | off
    expedite_keys: frozenset[str] | None = None  # None -> first-come policy within budget
    expedite_budget: int = config.EXPEDITE_BUDGET
    extra_units: dict[tuple[str, str], tuple[int, ...]] = field(default_factory=dict)
    # Prognosis-driven ordering (backtests): order the replacement for (tail, part)
    # once the LRU has consumed this many cycles, instead of when it fails.
    preorder_at_cycles: dict[tuple[str, str], float] = field(default_factory=dict)


class Hold:
    __slots__ = ("hid", "tail", "kind", "part", "start", "end", "eid")

    def __init__(self, hid, tail, kind, part, start, end, eid):
        self.hid, self.tail, self.kind, self.part = hid, tail, kind, part
        self.start, self.end, self.eid = start, end, eid


@dataclass
class Episode:
    """One demand for a part at a stock location: a failure, or a donor robbed by a cannibalisation."""
    eid: int
    base: str
    part: str
    tail: str
    need_day: int
    rank: tuple  # FIFO position in the spares queue
    kind: str  # wait | cann_wait | refail_wait
    repair_kind: str  # repair | cascade_repair
    repair_days: int
    order_key: str | None
    via: str = "pending"  # stock | arrival | cann | pending
    served_day: int | None = None
    wait_hold: int | None = None
    repair_hold: int | None = None


@dataclass
class SimResult:
    plan: Plan
    scenario: Scenario
    horizon: int
    tails: list[str]
    tail_base: dict[str, str]
    holds: list[Hold]
    episodes: dict[tuple[str, str], list[Episode]]
    supply: dict[tuple[str, str], dict]
    demand: dict[str, np.ndarray]
    inductions: dict[str, dict]
    events: list[dict]
    expedited: list[dict]
    label: np.ndarray = None  # (tails, days) label index; UP = available
    up: np.ndarray = None
    delivered: dict[str, np.ndarray] = None

    def finalise(self) -> "SimResult":
        self.label = label_matrix(self.holds, self.tails, self.horizon)
        self.up = self.label == UP
        self.delivered = delivered(self.up, self.tails, self.tail_base, self.demand)
        return self

    # ---- headline numbers -------------------------------------------------
    @property
    def total_aircraft_days(self) -> int:
        return len(self.tails) * self.horizon

    def label_days(self) -> dict[str, int]:
        counts = np.bincount(self.label.ravel(), minlength=UP + 1)
        out = {name: int(counts[i]) for i, name in enumerate(LABELS)}
        out["up"] = int(counts[UP])
        return out

    def summary(self) -> dict:
        """Ao, ceiling, gap and its attribution. Fractions of total aircraft-days; *_days in aircraft-days."""
        total = self.total_aircraft_days
        days = self.label_days()
        ao = days["up"] / total
        ceiling = 1 - days["planned"] / total
        attribution_days = {c: days[c] for c in CATEGORIES}
        tasked = int(sum(d.sum() for d in self.demand.values()))
        flown = int(sum(d.sum() for d in self.delivered.values()))
        return {
            "plan": self.plan.name,
            "ao": ao,
            "ceiling": ceiling,
            "gap": ceiling - ao,
            "attribution": {c: v / total for c, v in attribution_days.items()},
            "attribution_days": attribution_days,
            "aircraft_days_available": days["up"],
            "aircraft_days_total": total,
            "planned_maintenance_days": days["planned"],
            "sortie_days_tasked": tasked,
            "sortie_days_delivered": flown,
            "sortie_days_lost": tasked - flown,
            "mean_depot_queue_days": self.mean_depot_queue(),
            "cannibalisations": sum(1 for e in self.events if e["type"] == "cannibalisation"),
            "failures": sum(1 for e in self.events if e["type"] == "failure"),
        }

    def mean_depot_queue(self) -> float:
        """Mean days an inspection waited past its due date for a bay."""
        waits = [max(0, i["start"] - i["due"]) for i in self.inductions.values()]
        return float(np.mean(waits)) if waits else 0.0

    def bay_occupancy(self) -> dict[str, np.ndarray]:
        occ = {}
        for ind in self.inductions.values():
            arr = occ.setdefault(ind["depot"], np.zeros(self.horizon, dtype=int))
            s, e = max(ind["start"], 0), min(ind["start"] + ind["duration"], self.horizon)
            if s < e:
                arr[s:e] += 1
        return occ

    def first_up_day(self, tail: str) -> float:
        """Days from day 0 until the tail is next available (0 if available today; INF if not in horizon)."""
        row = self.up[self.tails.index(tail)]
        idx = np.flatnonzero(row)
        return float(idx[0]) if len(idx) else INF_DAYS


def label_matrix(holds, tails: list[str], horizon: int, exclude_kinds: tuple[str, ...] = ()) -> np.ndarray:
    """(tails, days) matrix of the highest-priority active hold label; UP where none."""
    idx = {t: i for i, t in enumerate(tails)}
    lab = np.full((len(tails), horizon), UP, dtype=np.int8)
    for h in holds:
        if h.kind in exclude_kinds:
            continue
        s, e = max(h.start, 0), min(h.end, horizon)
        if s < e:
            row = lab[idx[h.tail]]
            row[s:e] = np.minimum(row[s:e], KIND_LABEL[h.kind])
    return lab


def delivered(up: np.ndarray, tails, tail_base, demand) -> dict[str, np.ndarray]:
    """Sortie-days flown per base per day: min(tasked, available)."""
    out = {}
    for b, d in demand.items():
        rows = [i for i, t in enumerate(tails) if tail_base[t] == b]
        out[b] = np.minimum(d, up[rows].sum(axis=0))
    return out


class _Sim:
    def __init__(self, world: World, scenario: Scenario, plan: Plan, remaining: dict, fresh_life: Callable,
                 intervals: dict[tuple[str, str], Interval] | None, util: dict[str, float]):
        self.w, self.sc, self.plan = world, scenario, plan
        self.T = world.horizon
        self.delay = scenario.spares_delay_days
        self.demand = scenario.demand(world)
        self.grounded = set(scenario.ground_tails)
        self.fresh_life = fresh_life
        self.util = util
        self.holds: list[Hold] = []
        self.tail_holds: dict[str, list[Hold]] = {t: [] for t in world.tails}
        self.episodes: dict[int, Episode] = {}
        self.ep_by_loc: dict[tuple[str, str], list[Episode]] = defaultdict(list)
        self.queue: dict[tuple[str, str], list[int]] = defaultdict(list)
        self.pipeline: dict[tuple[str, str], list] = defaultdict(list)  # heap of (day, seq, key)
        self.supply: dict[tuple[str, str], dict] = {}
        self.stock = {}
        self.seq = 0
        self.fail_count = defaultdict(int)
        self.budget = plan.expedite_budget
        self.expedited: list[dict] = []
        self.events: list[dict] = []
        self.inductions: dict[str, dict] = {}
        self.rem: dict[tuple[str, str], float | None] = {}
        self.belief: dict[tuple[str, str], tuple[float, float, float]] = {}  # (point, lo, hi) cycles at install
        self.consumed: dict[tuple[str, str], float] = defaultdict(float)
        self.moved: set[tuple[str, str]] = set()
        self.preordered: set[tuple[str, str]] = set()
        for key, lru in world.lrus.items():
            if lru.failed:
                self.rem[key] = None
            else:
                self.rem[key] = float(remaining[key])
                iv = intervals.get(key) if intervals else None
                self.belief[key] = (iv.point, iv.lo, iv.hi) if iv else (self.rem[key],) * 3
        for b in world.bases:
            for p in world.parts:
                self.stock[(b, p)] = world.stock[(b, p)]
                self.supply[(b, p)] = {"initial": world.stock[(b, p)], "arrivals": []}

    # ---- bookkeeping --------------------------------------------------------
    def _next(self) -> int:
        self.seq += 1
        return self.seq

    def add_hold(self, tail, kind, part, start, end, eid=None) -> Hold:
        h = Hold(len(self.holds), tail, kind, part, start, end, eid)
        self.holds.append(h)
        self.tail_holds[tail].append(h)
        return h

    def down(self, tail: str, t: int) -> bool:
        return any(h.start <= t < h.end for h in self.tail_holds[tail])

    def in_bay(self, tail: str, t: int) -> bool:
        return any(h.kind == "bay" and h.start <= t < h.end for h in self.tail_holds[tail])

    def place_order(self, base, part, placed_day, key, *, waiting: bool, normal_arrival: int,
                    expedited_arrival: int | None = None):
        explicit = self.plan.expedite_keys
        lead = self.w.parts[part].lead_time_days
        exp_arrival = expedited_arrival if expedited_arrival is not None else placed_day + expedite_lead(lead)
        want = (key in explicit) if explicit is not None else (waiting and self.budget > 0)
        arrival = normal_arrival
        # Expedited orders travel at AOG priority and are not held up by a
        # delayed surface convoy, so the scenario delay does not apply to them.
        if want and exp_arrival < normal_arrival and (explicit is not None or self.budget > 0):
            arrival = exp_arrival
            if explicit is None:
                self.budget -= 1
            self.expedited.append({"key": key, "base": base, "part": part, "placed_day": placed_day,
                                   "normal_arrival": normal_arrival, "expedited_arrival": arrival})
        heapq.heappush(self.pipeline[(base, part)], (arrival, self._next(), key))
        self.supply[(base, part)]["arrivals"].append([arrival, key, placed_day])
        return arrival

    def new_episode(self, base, part, tail, need_day, rank, kind, order_key) -> Episode:
        repair_kind = "repair" if kind == "wait" else "cascade_repair"
        ep = Episode(self._next(), base, part, tail, need_day, rank, kind, repair_kind,
                     self.w.parts[part].repair_days, order_key)
        self.episodes[ep.eid] = ep
        self.ep_by_loc[(base, part)].append(ep)
        return ep

    def install(self, ep: Episode, t: int, via: str):
        ep.via, ep.served_day = via, t
        if ep.wait_hold is not None:
            self.holds[ep.wait_hold].end = t
        key = (ep.tail, ep.part)
        self.fail_count[("install",) + key] += 1
        life = float(self.fresh_life(ep.tail, ep.part, self.fail_count[("install",) + key]))
        self.rem[key] = life
        mean = self.w.parts[ep.part].mean_life_cycles
        self.belief[key] = (mean, mean, mean)
        self.consumed[key] = 0.0
        self.moved.discard(key)
        ep.repair_hold = self.add_hold(ep.tail, ep.repair_kind, ep.part, t, t + ep.repair_days, ep.eid).hid

    # ---- set-up ---------------------------------------------------------------
    def setup(self):
        for tail in sorted(self.grounded):
            self.add_hold(tail, "grounded", None, 0, OPEN)
        for tail, insp in self.w.inspections.items():
            if tail in self.grounded or insp.due_day >= self.T:
                continue
            start, depot = self.plan.inductions[tail]
            if start > insp.due_day:
                self.add_hold(tail, "overdue", None, insp.due_day, start)
            self.add_hold(tail, "bay", None, start, start + insp.duration_days)
            self.inductions[tail] = {"tail": tail, "depot": depot, "start": start, "due": insp.due_day,
                                     "duration": insp.duration_days, "record_id": insp.record_id}
        for o in self.w.orders:
            lead = self.w.parts[o.part_number].lead_time_days
            normal = max(0, o.eta_day) + self.delay
            # Expediting an order already in the pipeline re-sources it at AOG
            # priority from today, so it arrives expedite_lead days from day 0.
            exp = min(o.eta_day, expedite_lead(lead))
            waiting = o.for_tail is not None and o.for_tail not in self.grounded
            self.place_order(o.base, o.part_number, o.placed_day, o.order_id, waiting=waiting,
                             normal_arrival=normal, expedited_arrival=exp)
        for d in self.w.defects:
            if d.tail in self.grounded:
                continue
            b = self.w.tail_base[d.tail]
            ep = self.new_episode(b, d.part_number, d.tail, 0, (d.since_day, self.seq), "wait", d.order_id)
            ep.wait_hold = self.add_hold(d.tail, "wait", d.part_number, 0, OPEN, ep.eid).hid
            self.queue[(b, d.part_number)].append(ep.eid)
        for (b, p), days in sorted(self.plan.extra_units.items()):
            for k, a in enumerate(days):
                key = f"X:{b}:{p}:{k}"
                heapq.heappush(self.pipeline[(b, p)], (a, self._next(), key))
                self.supply[(b, p)]["arrivals"].append([a, key, 0])

    # ---- daily steps ------------------------------------------------------------
    def arrivals(self, t: int):
        for loc, heap in self.pipeline.items():
            while heap and heap[0][0] <= t:
                heapq.heappop(heap)
                self.stock[loc] += 1
            q = self.queue[loc]
            while self.stock[loc] > 0 and q:
                self.stock[loc] -= 1
                self.install(self.episodes[q.pop(0)], t, "arrival")

    def eta(self, ep: Episode) -> float:
        """Day the spare for a queued episode is expected (its queue position's arrival)."""
        loc = (ep.base, ep.part)
        pos = self.queue[loc].index(ep.eid)
        pending = sorted(a for a, _, _ in self.pipeline[loc])
        return float(pending[pos]) if pos < len(pending) else INF_DAYS

    def free_in(self, tail: str, t: int, ignore_eid: int | None = None) -> float:
        """Days from t until the tail would next be available, on current knowledge.

        ignore_eid: leave out the holds of one spares episode (to ask "what else keeps it down?").
        """
        if tail in self.grounded:
            return INF_DAYS
        day = float(t)
        for _ in range(64):
            active = [h for h in self.tail_holds[tail]
                      if h.start <= day < h.end and (ignore_eid is None or h.eid != ignore_eid)]
            if not active:
                return day - t
            ends = []
            for h in active:
                if h.end >= OPEN:
                    ep = self.episodes[h.eid]
                    ends.append(self.eta(ep) + ep.repair_days)
                else:
                    ends.append(float(h.end))
            day = max(ends)
            if day >= INF_DAYS:
                return INF_DAYS
        return day - t

    def refail(self, donor: str, part: str, recipient_base: str) -> tuple[float, float]:
        point, lo, hi = self.belief[(donor, part)]
        c = self.consumed[(donor, part)]
        u = self.util[recipient_base]
        delta = refailure_delta(max(point - c, 0), max(lo - c, 0), max(hi - c, 0), u, config.CANN_LOOKAHEAD_DAYS)
        downtime = self.w.parts[part].lead_time_days + self.delay + self.w.parts[part].repair_days
        return delta, downtime

    def cannibalise(self, t: int):
        policy = self.plan.cann_policy
        if policy == "off":
            return
        for loc in sorted(self.queue):
            b, p = loc
            for eid in list(self.queue[loc]):
                ep = self.episodes[eid]
                if ep.kind not in ("wait", "refail_wait"):
                    continue
                rec = ep.tail
                rec_other = self.free_in(rec, t, ignore_eid=ep.eid)
                if policy == "reactive":
                    up_now = sum(1 for x in self.w.tails_at(b) if not self.down(x, t))
                    if up_now >= self.demand[b][t] or rec_other > 0:
                        continue
                donors = [j for j in self.w.tails_at(b)
                          if j != rec and self.rem[(j, p)] is not None and self.down(j, t) and not self.in_bay(j, t)]
                if not donors:
                    continue
                part = self.w.parts[p]
                spare_ready = self.eta(ep) - t + ep.repair_days
                best, best_score = None, None
                for j in donors:
                    free = self.free_in(j, t)
                    if policy == "priced":
                        delta, downtime = self.refail(j, p, b)
                        priced = price_core(spare_ready_days=spare_ready, donor_free_days=free,
                                            swap_days=part.cann_days, repair_hours=part.repair_hours,
                                            refail_delta=delta, refail_downtime_days=downtime,
                                            recipient_other_down_days=rec_other)
                        score = priced["net_aircraft_days"]
                    else:
                        if free < REACTIVE_MIN_DONOR_DOWN_DAYS:
                            continue
                        score = free
                    if best_score is None or score > best_score:
                        best, best_score = j, score
                if best is None or (policy == "priced" and best_score <= 0):
                    continue
                self.execute_cann(ep, best, t)

    def execute_cann(self, ep: Episode, donor: str, t: int):
        loc = (ep.base, ep.part)
        pos = self.queue[loc].index(ep.eid)
        self.queue[loc].pop(pos)
        ep.via, ep.served_day = "cann", t
        self.holds[ep.wait_hold].end = t
        rec_key, don_key = (ep.tail, ep.part), (donor, ep.part)
        part = self.w.parts[ep.part]
        self.rem[rec_key] = self.rem[don_key] * (1 - config.HANDLING_LIFE_PENALTY)
        point, lo, hi = self.belief[don_key]
        c = self.consumed[don_key]
        pen = 1 - config.HANDLING_LIFE_PENALTY
        self.belief[rec_key] = (max(point - c, 0) * pen, max(lo - c, 0) * pen, max(hi - c, 0) * pen)
        self.consumed[rec_key] = 0.0
        self.moved.add(rec_key)
        self.add_hold(ep.tail, "repair", ep.part, t, t + part.repair_days, ep.eid)
        if part.cann_days > part.repair_days:
            self.add_hold(ep.tail, "cann_extra", ep.part, t + part.repair_days, t + part.cann_days, ep.eid)
        self.rem[don_key] = None
        dep = self.new_episode(ep.base, ep.part, donor, t, ep.rank, "cann_wait", None)
        dep.wait_hold = self.add_hold(donor, "cann_wait", ep.part, t, OPEN, dep.eid).hid
        self.queue[loc].insert(pos, dep.eid)
        self.events.append({"day": t, "type": "cannibalisation", "tail": ep.tail, "donor": donor, "part": ep.part})

    def fail(self, tail: str, p: str, t: int):
        key = (tail, p)
        self.rem[key] = None
        was_moved = key in self.moved
        self.moved.discard(key)
        self.fail_count[key] += 1
        b = self.w.tail_base[tail]
        need = t + 1
        okey = f"F:{tail}:{p}:{self.fail_count[key]}"
        lead = self.w.parts[p].lead_time_days
        waiting = self.stock[(b, p)] == 0
        if key in self.preordered:
            self.preordered.discard(key)  # its replacement is already on order
        else:
            self.place_order(b, p, need, okey, waiting=waiting, normal_arrival=need + lead + self.delay)
        ep = self.new_episode(b, p, tail, need, (need, self.seq), "refail_wait" if was_moved else "wait", okey)
        self.events.append({"day": t, "type": "failure", "tail": tail, "part": p, "moved_part": was_moved,
                            "from_stock": not waiting})
        if not waiting:
            self.stock[(b, p)] -= 1
            self.install(ep, need, "stock")
        else:
            kind = ep.kind
            ep.wait_hold = self.add_hold(tail, kind, p, need, OPEN, ep.eid).hid
            self.queue[(b, p)].append(ep.eid)

    def preorder(self, tail: str, p: str, t: int):
        b = self.w.tail_base[tail]
        lead = self.w.parts[p].lead_time_days
        self.preordered.add((tail, p))
        self.place_order(b, p, t + 1, f"P:{tail}:{p}", waiting=False, normal_arrival=t + 1 + lead + self.delay)
        self.events.append({"day": t, "type": "preorder", "tail": tail, "part": p})

    def run(self) -> SimResult:
        self.setup()
        for key, at in sorted(self.plan.preorder_at_cycles.items()):
            if at <= 0 and self.rem.get(key) is not None:
                self.preorder(key[0], key[1], -1)
        parts = list(self.w.parts)
        for t in range(self.T):
            self.arrivals(t)
            self.cannibalise(t)
            for b in self.w.bases:
                ups = [x for x in self.w.tails_at(b) if not self.down(x, t)]
                if not ups:
                    continue
                u = min(self.demand[b][t], len(ups)) / len(ups)
                for x in ups:
                    for p in parts:
                        key = (x, p)
                        if self.rem[key] is None:
                            continue
                        self.rem[key] -= u
                        self.consumed[key] += u
                        if self.rem[key] <= 1e-9:
                            self.fail(x, p, t)
                        elif (key in self.plan.preorder_at_cycles and key not in self.preordered
                              and self.fail_count[key] == 0
                              and self.consumed[key] >= self.plan.preorder_at_cycles[key]):
                            self.preorder(x, p, t)
        by_loc = {loc: list(eps) for loc, eps in self.ep_by_loc.items()}
        return SimResult(
            plan=self.plan, scenario=self.sc, horizon=self.T, tails=list(self.w.tails),
            tail_base=dict(self.w.tail_base), holds=self.holds, episodes=by_loc, supply=self.supply,
            demand=self.demand, inductions=self.inductions, events=self.events, expedited=self.expedited,
        ).finalise()


def fresh_life_mean(world: World) -> Callable[[str, str, int], float]:
    """Projection: a newly fitted spare is expected to last the part's mean life (cycles)."""
    return lambda tail, part, n: world.parts[part].mean_life_cycles


def fresh_life_truth(world: World) -> Callable[[str, str, int], float]:
    """Backtest only: the true life (cycles) of the n-th spare fitted to (tail, part), a seeded draw."""
    def life(tail: str, part: str, n: int) -> float:
        h = int(hashlib.md5(f"{tail}|{part}|{n}".encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng([world.seed, 99, h])
        return float(world.parts[part].mean_life_cycles * np.exp(rng.normal(-0.25**2 / 2, 0.25)))
    return life


def simulate(world: World, scenario: Scenario, plan: Plan, remaining: dict[tuple[str, str], float],
             fresh_life: Callable[[str, str, int], float],
             intervals: dict[tuple[str, str], Interval] | None = None) -> SimResult:
    """Run the fleet day by day over the horizon.

    remaining: cycles to failure for every serviceable installed LRU -- the
        model's point estimate for a projection, ground truth for a backtest.
    fresh_life: cycles of life for a newly installed spare (tail, part, nth install).
    intervals: the model's intervals, used only by the priced cannibalisation
        policy to estimate re-failure risk (decisions never see ground truth).
    """
    return _Sim(world, scenario, plan, remaining, fresh_life, intervals, utilisation(world, scenario)).run()


# ---- first-order counterfactuals ------------------------------------------------

class _H:
    __slots__ = ("tail", "kind", "start", "end")

    def __init__(self, tail, kind, start, end):
        self.tail, self.kind, self.start, self.end = tail, kind, start, end


def replay(res: SimResult, extra_units: dict[tuple[str, str], list[int]] | None = None,
           expedite: dict[str, int] | None = None) -> dict:
    """Re-serve the spares queues with extra units and/or earlier arrivals, holding failures fixed.

    The failure timeline from `res` is kept (no wear feedback), and each
    affected stock location's demands are re-matched first-come first-served:
    the j-th demand is served at max(its need day, the j-th earliest unit).
    Adding a unit or bringing one forward can only lower each order statistic,
    so the result is monotone by construction.

    extra_units: {(base, part): [arrival days]}; day 0 means on the shelf today.
    expedite: {order_key: new arrival day}.
    Returns up mask, aircraft-days available and sortie-days flown.
    """
    extra_units = extra_units or {}
    expedite = expedite or {}
    affected = set(extra_units)
    for loc, sup in res.supply.items():
        if any(k in expedite for _, k, _ in sup["arrivals"]):
            affected.add(loc)
    redo: set[int] = set()
    new_holds: list = []
    for loc in sorted(affected):
        sup = res.supply[loc]
        times = [-1] * sup["initial"]
        times += [expedite.get(k, a) for a, k, _ in sup["arrivals"]]
        times += list(extra_units.get(loc, []))
        times.sort()
        eps = sorted((e for e in res.episodes.get(loc, []) if e.via != "cann"), key=lambda e: e.rank)
        for j, e in enumerate(eps):
            redo.update(h for h in (e.wait_hold, e.repair_hold) if h is not None)
            serve = max(e.need_day, times[j]) if j < len(times) else OPEN
            if serve > e.need_day:
                new_holds.append(_H(e.tail, e.kind, e.need_day, serve))
            if serve < OPEN:
                new_holds.append(_H(e.tail, e.repair_kind, serve, serve + e.repair_days))
    holds = [h for h in res.holds if h.hid not in redo] + new_holds
    lab = label_matrix(holds, res.tails, res.horizon)
    up = lab == UP
    dl = delivered(up, res.tails, res.tail_base, res.demand)
    non_depot = label_matrix(holds, res.tails, res.horizon, exclude_kinds=DEPOT_KINDS) != UP
    return {
        "up": up,
        "non_depot_down": non_depot,
        "aircraft_days": int(up.sum()),
        "sortie_days": int(sum(d.sum() for d in dl.values())),
        "delivered": dl,
    }


def non_depot_down(res: SimResult) -> np.ndarray:
    """Tail-days down for reasons other than depot bay or depot queue."""
    return label_matrix(res.holds, res.tails, res.horizon, exclude_kinds=DEPOT_KINDS) != UP


def attribution(res: SimResult) -> dict:
    """Decompose the availability gap (ceiling - Ao) into its causes.

    Returns fractions of total aircraft-days per cause; they sum to the gap exactly.
    """
    s = res.summary()
    return {"ceiling": s["ceiling"], "ao": s["ao"], "gap": s["gap"], "components": s["attribution"]}
