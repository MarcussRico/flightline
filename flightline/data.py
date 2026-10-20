"""Load the scenario from SQLite into plain Python structures.

`World` is the logistics side (fleet, stock, depots, plan, records).
`DegradationSet` is the sensor side (run-to-failure units + installed LRUs);
`ncmapss.load_if_present` can replace it with real NASA data.
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import config


@dataclass(frozen=True)
class Part:
    part_number: str
    name: str
    lead_time_days: int
    mean_life_cycles: float
    repair_hours: float

    @property
    def repair_days(self) -> int:
        """Elapsed days for a normal remove-and-replace (whole days, minimum 1)."""
        return max(1, math.ceil(self.repair_hours / config.CREW_HOURS_PER_DAY))

    @property
    def cann_days(self) -> int:
        """Elapsed days for a cannibalisation swap: twice the labour of a normal repair."""
        return max(1, math.ceil(config.CANN_LABOUR_MULTIPLIER * self.repair_hours / config.CREW_HOURS_PER_DAY))


@dataclass(frozen=True)
class Lru:
    lru_id: str
    tail: str
    part_number: str
    unit_id: str
    age_cycles: int
    failed: bool
    truth_remaining_cycles: float  # ground truth; only the backtest may read it


@dataclass(frozen=True)
class Order:
    order_id: str
    base: str
    part_number: str
    placed_day: int
    eta_day: int
    for_tail: str | None


@dataclass(frozen=True)
class Defect:
    tail: str
    part_number: str
    since_day: int
    order_id: str


@dataclass(frozen=True)
class Inspection:
    record_id: str
    tail: str
    due_day: int
    duration_days: int


@dataclass
class World:
    seed: int
    horizon: int
    tails: list[str]
    bases: list[str]
    tail_base: dict[str, str]
    parts: dict[str, Part]
    lrus: dict[tuple[str, str], Lru]
    stock: dict[tuple[str, str], int]
    orders: list[Order]
    defects: list[Defect]
    depots: dict[str, tuple[int, int]]  # depot_id -> (bays, induction crews)
    demand: dict[str, np.ndarray]  # base -> aircraft tasked per day
    inspections: dict[str, Inspection]
    meta: dict[str, str] = field(default_factory=dict)

    def tails_at(self, base: str) -> list[str]:
        return [t for t in self.tails if self.tail_base[t] == base]


@dataclass
class Unit:
    unit_id: str
    part_number: str
    split: str  # train | calibration | test | installed
    life_cycles: int | None  # true failure cycle (run-to-failure units and ground truth)
    ops: np.ndarray  # (cycles, n_ops)
    sensors: np.ndarray  # (cycles, n_sensors)


@dataclass
class DegradationSet:
    source: str  # provenance label shown in the UI
    sensor_names: list[str]
    units: dict[str, Unit]
    installed: dict[tuple[str, str], str]  # (tail, part_number) -> unit_id
    installed_truth_remaining: dict[tuple[str, str], float]
    # Ground truth for the backtest only: each installed unit's full trace, history + future.
    installed_full: dict[tuple[str, str], Unit] = field(default_factory=dict)
    installed_age: dict[tuple[str, str], int] = field(default_factory=dict)  # cycles since install

    def split(self, name: str) -> list[Unit]:
        return [u for u in self.units.values() if u.split == name]


def connect(db_path: Path = config.DB_PATH) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(f"{db_path} not found. Run `python -m flightline.seed` first.")
    return sqlite3.connect(db_path)


def load_world(con: sqlite3.Connection) -> World:
    meta = dict(con.execute("SELECT key, value FROM meta"))
    horizon = int(meta["horizon_days"])
    aircraft = con.execute("SELECT tail, base FROM aircraft ORDER BY tail").fetchall()
    tails = [t for t, _ in aircraft]
    tail_base = dict(aircraft)
    bases = sorted(set(tail_base.values()))
    parts = {
        r[0]: Part(r[0], r[1], int(r[2]), float(r[3]), float(r[4]))
        for r in con.execute("SELECT * FROM part ORDER BY part_number")
    }
    lrus = {}
    for lru_id, tail, pn, uid, age, status, truth in con.execute("SELECT * FROM lru"):
        lrus[(tail, pn)] = Lru(lru_id, tail, pn, uid, int(age), status == "failed", float(truth))
    stock = {(b, pn): int(n) for b, pn, n in con.execute("SELECT * FROM spares")}
    orders = [Order(*r) for r in con.execute("SELECT * FROM spare_order ORDER BY eta_day, order_id")]
    defects = [Defect(*r) for r in con.execute("SELECT * FROM defect ORDER BY since_day, tail")]
    depots = {d: (int(b), int(c)) for d, b, c in con.execute("SELECT * FROM depot ORDER BY depot_id")}
    demand = {b: np.zeros(horizon, dtype=int) for b in bases}
    for day, base, n in con.execute("SELECT * FROM sortie_plan"):
        if day < horizon:
            demand[base][day] = int(n)
    inspections = {
        r[1]: Inspection(r[0], r[1], int(r[2]), int(r[3]))
        for r in con.execute(
            "SELECT record_id, tail, due_day, duration_days FROM tech_records "
            "WHERE record_type = 'phase_inspection' ORDER BY due_day, tail"
        )
    }
    return World(
        seed=int(meta["seed"]), horizon=horizon, tails=tails, bases=bases, tail_base=tail_base,
        parts=parts, lrus=lrus, stock=stock, orders=orders, defects=defects, depots=depots,
        demand=demand, inspections=inspections, meta=meta,
    )


def load_degradation(con: sqlite3.Connection) -> DegradationSet:
    meta = dict(con.execute("SELECT key, value FROM meta"))
    sensor_names = meta["sensor_names"].split(",")
    cols = ", ".join(["op1", "op2", "op3", *sensor_names])
    unit_meta = {r[0]: r[1:] for r in con.execute("SELECT unit_id, part_number, split, life_cycles FROM unit")}
    rows = con.execute(f"SELECT unit_id, {cols} FROM sensor_history ORDER BY unit_id, cycle").fetchall()
    grouped: dict[str, list] = {}
    for r in rows:
        grouped.setdefault(r[0], []).append(r[1:])
    units = {}
    for uid, (pn, split, life) in unit_meta.items():
        arr = np.asarray(grouped.get(uid, []), dtype=float).reshape(-1, 3 + len(sensor_names))
        units[uid] = Unit(uid, pn, split, int(life), arr[:, :3], arr[:, 3:])
    installed, truth = {}, {}
    for tail, pn, uid, rem in con.execute("SELECT tail, part_number, unit_id, truth_remaining_cycles FROM lru"):
        installed[(tail, pn)] = uid
        truth[(tail, pn)] = float(rem)
    future: dict[str, list] = {}
    for r in con.execute(f"SELECT unit_id, {cols} FROM sensor_future ORDER BY unit_id, cycle"):
        future.setdefault(r[0], []).append(r[1:])
    full = {}
    for key, uid in installed.items():
        u = units[uid]
        fut = np.asarray(future.get(uid, []), dtype=float).reshape(-1, 3 + len(sensor_names))
        full[key] = Unit(uid, u.part_number, "installed", u.life_cycles,
                         np.vstack([u.ops, fut[:, :3]]), np.vstack([u.sensors, fut[:, 3:]]))
    ages = {key: len(units[uid].sensors) for key, uid in installed.items()}
    return DegradationSet(meta["provenance"], sensor_names, units, installed, truth, full, ages)
