"""The twin: one graph joining the four silos the problem statement names.

    tail --installed--> LRU --instance_of--> part number --stocked_at--> stock location
      |                  (health monitoring)                  (spares)         |
      |                                                                  repaired_by
      +--inspection_due--> depot --has_bay--> bay --returns_to--> sortie plan <--tasked_at-- tail
           (technical records)        (MRO)

Queries over it answer questions no single silo can, e.g. "which one spare,
stocked at which base, unlocks the most sortie-days next quarter?".

Units: sortie-days (a tasked aircraft-day actually flown), aircraft-days.
"""

from __future__ import annotations

import networkx as nx
import numpy as np

from .availability import SimResult, replay
from .data import World

SILOS = {
    "health_monitoring": "lru",
    "technical_records": "inspection_due",
    "spares": "stock_location",
    "mro": "bay",
}


class Twin:
    def __init__(self, world: World, projection: SimResult, intervals: dict | None = None,
                 ages: dict | None = None):
        self.world = world
        self.projection = projection
        self.G = build_graph(world, projection, intervals or {}, ages or {})

    # ---- queries ------------------------------------------------------------
    def criticality(self, tail: str) -> float:
        """Sortie-days at risk over the horizon if this tail went down for good.

        For each day it is projected to be available, count the sortie it would
        no longer cover: delivered(base) - delivered(base without it).
        """
        res = self.projection
        base = self.G.nodes[("tail", tail)]["base"]
        demand = res.demand[base]
        rows = [i for i, t in enumerate(res.tails) if res.tail_base[t] == base]
        up_base = res.up[rows].sum(axis=0)
        mine = res.up[res.tails.index(tail)].astype(int)
        return float(np.sum(np.minimum(demand, up_base) - np.minimum(demand, up_base - mine)))

    def dependents(self, base: str, part: str) -> list[str]:
        """Tails whose installed LRUs draw on the stock of `part` at `base` (graph traversal)."""
        out = []
        for lru in self.G.predecessors(("part", part)):
            tail = self.G.nodes[lru]["tail"]
            if self.G.nodes[("tail", tail)]["base"] == base:
                out.append(tail)
        return sorted(out)

    def spare_unlock(self, base: str, part: str, extra: int = 1, arrival_day: int = 0) -> dict:
        """Sortie-days and aircraft-days gained if `extra` more units of `part` were at `base`.

        arrival_day 0 means on the shelf today; otherwise the day they would land.
        First-order: the projection's failure timeline is held fixed.
        """
        res = self.projection
        base_ad = int(res.up.sum())
        base_sd = int(sum(d.sum() for d in res.delivered.values()))
        r = replay(res, extra_units={(base, part): [arrival_day] * extra})
        return {"sortie_days": r["sortie_days"] - base_sd, "aircraft_days": r["aircraft_days"] - base_ad}

    def spare_unlock_ranking(self) -> list[dict]:
        """For every part number and every base: what one more unit on the shelf today unlocks.

        Sorted by sortie-days unlocked, then aircraft-days. The answer to "which
        single spare, stocked where, unlocks the most sortie-days this horizon?".
        """
        res = self.projection
        rows = []
        for pnode in sorted(n for n, k in self.G.nodes(data="kind") if k == "part_number"):
            part = pnode[1]
            for snode in sorted(self.G.successors(pnode)):
                base = snode[1]
                gain = self.spare_unlock(base, part)
                demands = [e for e in res.episodes.get((base, part), []) if e.need_day < res.horizon]
                stocked_out = [e for e in demands if e.via != "stock"]
                rows.append({
                    "part": part,
                    "part_name": self.G.nodes[pnode]["name"],
                    "base": base,
                    "on_hand": self.G.nodes[snode]["on_hand"],
                    "lead_time_days": self.G.nodes[pnode]["lead_time_days"],
                    "sortie_days_unlocked": gain["sortie_days"],
                    "aircraft_days_unlocked": gain["aircraft_days"],
                    "projected_demands": len(demands),
                    "projected_stockouts": len(stocked_out),
                    "dependent_tails": len(self.dependents(base, part)),
                })
        rows.sort(key=lambda r: (-r["sortie_days_unlocked"], -r["aircraft_days_unlocked"], r["part"], r["base"]))
        return rows

    def summary(self) -> dict:
        """Node and edge counts by kind -- the four silos and the joins between them."""
        kinds: dict[str, int] = {}
        for _, k in self.G.nodes(data="kind"):
            kinds[k] = kinds.get(k, 0) + 1
        rels: dict[str, int] = {}
        for _, _, r in self.G.edges(data="rel"):
            rels[r] = rels.get(r, 0) + 1
        return {"nodes": kinds, "edges": rels, "n_nodes": self.G.number_of_nodes(),
                "n_edges": self.G.number_of_edges()}


def build_graph(world: World, projection: SimResult, intervals: dict, ages: dict) -> nx.DiGraph:
    G = nx.DiGraph()
    for b in world.bases:
        G.add_node(("sorties", b), kind="sortie_plan", base=b, tasked=int(projection.demand[b].sum()))
    for d, (bays, crews) in world.depots.items():
        G.add_node(("depot", d), kind="depot", bays=bays, crews=crews)
        for k in range(bays):
            G.add_node(("bay", d, k), kind="bay", depot=d)
            G.add_edge(("depot", d), ("bay", d, k), rel="has_bay")
            for b in world.bases:
                G.add_edge(("bay", d, k), ("sorties", b), rel="returns_to")
    for p, part in world.parts.items():
        G.add_node(("part", p), kind="part_number", name=part.name, lead_time_days=part.lead_time_days,
                   repair_hours=part.repair_hours)
        for b in world.bases:
            G.add_node(("stock", b, p), kind="stock_location", base=b, part=p, on_hand=world.stock[(b, p)])
            G.add_edge(("part", p), ("stock", b, p), rel="stocked_at")
            for d in world.depots:
                G.add_edge(("stock", b, p), ("depot", d), rel="repaired_by")
    for tail in world.tails:
        base = world.tail_base[tail]
        G.add_node(("tail", tail), kind="tail", base=base)
        G.add_edge(("tail", tail), ("sorties", base), rel="tasked_at")
        for p in world.parts:
            lru = world.lrus[(tail, p)]
            iv = intervals.get((tail, p))
            G.add_node(("lru", tail, p), kind="lru", tail=tail, part=p, age_cycles=ages.get((tail, p), lru.age_cycles),
                       failed=lru.failed, rul_cycles=(iv.point, iv.lo, iv.hi) if iv else None)
            G.add_edge(("tail", tail), ("lru", tail, p), rel="installed")
            G.add_edge(("lru", tail, p), ("part", p), rel="instance_of")
        insp = world.inspections.get(tail)
        if insp is not None:
            ind = projection.inductions.get(tail)
            G.add_edge(("tail", tail), ("depot", ind["depot"] if ind else sorted(world.depots)[0]),
                       rel="inspection_due", due_day=insp.due_day, duration_days=insp.duration_days)
    return G
