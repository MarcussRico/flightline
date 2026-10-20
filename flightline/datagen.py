"""Synthetic fleet generator.

Produces a run-to-failure population with the same *shape* as NASA N-CMAPSS /
C-MAPSS (several units per part type, multivariate sensors, monotonic
degradation plus noise, six operating regimes, a true failure cycle per unit)
and a 24-tail fleet around it: bases, stock, depots, a sortie plan and
technical records. Everything is a pure function of the seed.

Time units: sensor histories are in *cycles* (one cycle = one sortie flown).
Logistics are in *days*. Day 0 is "today".
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np

from . import config

BASES = ["BASE-A", "BASE-B", "BASE-C"]
N_TAILS = 24
N_SENSORS = 8
UNITS_PER_PART = 72  # historical run-to-failure units per part type
SPLIT_FRACTIONS = (("train", 0.5), ("calibration", 0.25), ("test", 0.25))

# part_number, name, lead_time_days, mean_life_cycles, repair_hours
PARTS = [
    ("PN-4410-HP", "Engine-driven hydraulic pump", 21, 300.0, 6.0),
    ("PN-2275-FCU", "Fuel control unit", 45, 360.0, 9.0),
    ("PN-3108-GEN", "AC generator", 14, 260.0, 5.0),
    ("PN-5520-ADC", "Air data computer", 7, 320.0, 3.0),
    ("PN-6731-RTX", "Radar transmitter", 60, 400.0, 11.0),
    ("PN-1904-MLA", "Main landing-gear actuator", 30, 300.0, 14.0),
]

# Six operating regimes (altitude kft, Mach, throttle %), as in C-MAPSS FD002.
REGIMES = np.array(
    [
        [0.0, 0.00, 100.0],
        [10.0, 0.25, 100.0],
        [20.0, 0.70, 100.0],
        [25.0, 0.62, 60.0],
        [35.0, 0.84, 100.0],
        [42.0, 0.84, 100.0],
    ]
)
REGIME_P = np.array([0.15, 0.15, 0.2, 0.15, 0.2, 0.15])

DEPOTS = [("DEPOT-1", 2, 1), ("DEPOT-2", 1, 1)]  # depot_id, bays, induction crews

SCHEMA = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE aircraft(tail TEXT PRIMARY KEY, base TEXT NOT NULL, airframe_hours REAL NOT NULL);
CREATE TABLE part(
    part_number TEXT PRIMARY KEY, name TEXT NOT NULL, lead_time_days INTEGER NOT NULL,
    mean_life_cycles REAL NOT NULL, repair_hours REAL NOT NULL);
CREATE TABLE unit(
    unit_id TEXT PRIMARY KEY, part_number TEXT NOT NULL,
    split TEXT NOT NULL CHECK (split IN ('train','calibration','test','installed')),
    life_cycles INTEGER NOT NULL);
CREATE TABLE lru(
    lru_id TEXT PRIMARY KEY, tail TEXT NOT NULL, part_number TEXT NOT NULL, unit_id TEXT NOT NULL,
    age_cycles INTEGER NOT NULL, status TEXT NOT NULL CHECK (status IN ('serviceable','failed')),
    truth_remaining_cycles REAL NOT NULL);
CREATE TABLE sensor_history(
    unit_id TEXT NOT NULL, cycle INTEGER NOT NULL, op1 REAL, op2 REAL, op3 REAL,
    s1 REAL, s2 REAL, s3 REAL, s4 REAL, s5 REAL, s6 REAL, s7 REAL, s8 REAL,
    PRIMARY KEY (unit_id, cycle));
CREATE TABLE sensor_future(
    unit_id TEXT NOT NULL, cycle INTEGER NOT NULL, op1 REAL, op2 REAL, op3 REAL,
    s1 REAL, s2 REAL, s3 REAL, s4 REAL, s5 REAL, s6 REAL, s7 REAL, s8 REAL,
    PRIMARY KEY (unit_id, cycle));
CREATE TABLE spares(base TEXT NOT NULL, part_number TEXT NOT NULL, on_hand INTEGER NOT NULL,
    PRIMARY KEY (base, part_number));
CREATE TABLE spare_order(order_id TEXT PRIMARY KEY, base TEXT NOT NULL, part_number TEXT NOT NULL,
    placed_day INTEGER NOT NULL, eta_day INTEGER NOT NULL, for_tail TEXT);
CREATE TABLE depot(depot_id TEXT PRIMARY KEY, bays INTEGER NOT NULL, induction_crews INTEGER NOT NULL);
CREATE TABLE sortie_plan(day INTEGER NOT NULL, base TEXT NOT NULL, sorties_tasked INTEGER NOT NULL,
    PRIMARY KEY (day, base));
CREATE TABLE tech_records(record_id TEXT PRIMARY KEY, tail TEXT NOT NULL, record_type TEXT NOT NULL,
    part_number TEXT, due_day INTEGER, duration_days INTEGER, last_done_day INTEGER, note TEXT);
CREATE TABLE defect(tail TEXT NOT NULL, part_number TEXT NOT NULL, since_day INTEGER NOT NULL,
    order_id TEXT NOT NULL);
"""


def _sensitivity(rng: np.random.Generator) -> np.ndarray:
    """Per-part sensor gains: five channels respond to wear, three are nuisance."""
    gains = np.zeros(N_SENSORS)
    informative = rng.choice(N_SENSORS, size=5, replace=False)
    gains[informative] = rng.uniform(0.8, 2.0, size=5) * rng.choice([-1.0, 1.0], size=5)
    return gains


def _trace(rng: np.random.Generator, life: int, gains: np.ndarray, base: np.ndarray, coupling: np.ndarray):
    """One run-to-failure sensor trace of `life` cycles.

    Degradation d(t) rises convexly from a small initial wear to 1.0 at the
    failure cycle; each sensor is regime baseline + gain * d + noise.
    """
    t = np.arange(1, life + 1, dtype=float)
    w0 = rng.uniform(0.0, 0.08)
    a = rng.uniform(2.5, 4.5)
    d = w0 + (1.0 - w0) * (np.exp(a * t / life) - 1.0) / (np.exp(a) - 1.0)
    unit_gain = gains * rng.uniform(0.85, 1.15, size=N_SENSORS)
    reg = rng.choice(len(REGIMES), size=life, p=REGIME_P)
    ops = REGIMES[reg] + rng.normal(0.0, [0.05, 0.002, 0.0], size=(life, 3))
    ops_scaled = ops / np.array([42.0, 0.84, 100.0])
    mu = base + ops_scaled @ coupling
    noise = rng.normal(0.0, 0.10, size=(life, N_SENSORS))
    sensors = mu + d[:, None] * unit_gain[None, :] + noise
    return ops, sensors


def _life(rng: np.random.Generator, mean_life: float) -> int:
    """True life in cycles: lognormal around the part's mean, CV ~0.25."""
    sigma = 0.25
    return int(max(0.45 * mean_life, mean_life * np.exp(rng.normal(-sigma**2 / 2, sigma))))


def generate(db_path: Path = config.DB_PATH, seed: int = config.SEED) -> dict:
    """Write the full synthetic scenario to SQLite. Returns row counts per table."""
    rng = np.random.default_rng(seed)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)

    base_level = rng.uniform(-1.0, 1.0, size=N_SENSORS)
    coupling = rng.uniform(-3.0, 3.0, size=(3, N_SENSORS))
    gains = {pn: _sensitivity(rng) for pn, *_ in PARTS}

    con.executemany(
        "INSERT INTO part VALUES (?,?,?,?,?)", [(pn, nm, lt, ml, rh) for pn, nm, lt, ml, rh in PARTS]
    )

    sensor_rows: list[tuple] = []
    future_rows: list[tuple] = []
    unit_rows: list[tuple] = []

    def add_trace(unit_id: str, life: int, upto: int, unit_rng: np.random.Generator, pn: str):
        # Cycles after `upto` are the installed part's future: ground truth that
        # only the backtest in metrics.py reads. The model never trains on it.
        ops, sens = _trace(unit_rng, life, gains[pn], base_level, coupling)
        for c in range(life):
            row = (unit_id, c + 1, *map(float, ops[c]), *map(float, np.round(sens[c], 5)))
            (sensor_rows if c < upto else future_rows).append(row)

    # Historical run-to-failure population, split by unit (never by row).
    for p_idx, (pn, _, _, mean_life, _) in enumerate(PARTS):
        order = rng.permutation(UNITS_PER_PART)
        cut1 = int(UNITS_PER_PART * SPLIT_FRACTIONS[0][1])
        cut2 = cut1 + int(UNITS_PER_PART * SPLIT_FRACTIONS[1][1])
        for k in range(UNITS_PER_PART):
            split = "train" if order[k] < cut1 else "calibration" if order[k] < cut2 else "test"
            uid = f"H-{pn[3:7]}-{k:03d}"
            unit_rng = np.random.default_rng([seed, 1, p_idx, k])
            life = _life(unit_rng, mean_life)
            unit_rows.append((uid, pn, split, life))
            add_trace(uid, life, life, unit_rng, pn)

    # Fleet.
    tails = [f"TAIL-{i:02d}" for i in range(1, N_TAILS + 1)]
    tail_base = {t: BASES[i // (N_TAILS // len(BASES))] for i, t in enumerate(tails)}
    con.executemany(
        "INSERT INTO aircraft VALUES (?,?,?)",
        [(t, tail_base[t], float(round(rng.uniform(1800, 5200)))) for t in tails],
    )

    # Three tails start the horizon on the ground, waiting on long-lead parts.
    long_lead = [p for p in PARTS if p[2] >= 30]
    defect_tails = [str(t) for t in rng.choice(tails, size=3, replace=False)]
    defect_parts = [long_lead[i] for i in rng.permutation(len(long_lead))[:3]]

    lru_rows = []
    defects = []
    orders = []
    for t_idx, tail in enumerate(tails):
        for p_idx, (pn, _, lead, mean_life, _) in enumerate(PARTS):
            uid = f"I-{tail[5:]}-{pn[3:7]}"
            unit_rng = np.random.default_rng([seed, 2, t_idx, p_idx])
            life = _life(unit_rng, mean_life)
            failed = tail in defect_tails and pn == defect_parts[defect_tails.index(tail)][0]
            if failed:
                age = life
                since = -int(rng.integers(8, 20))
                oid = f"ORD-{tail[5:]}-{pn[3:7]}"
                orders.append((oid, tail_base[tail], pn, since + 1, since + 1 + lead, tail))
                defects.append((tail, pn, since, oid))
            else:
                age = int(round(life * unit_rng.uniform(0.25, 0.95)))
                age = max(1, min(age, life - 1))
            unit_rows.append((uid, pn, "installed", life))
            add_trace(uid, life, age, unit_rng, pn)
            lru_rows.append(
                (f"{tail}/{pn}", tail, pn, uid, age, "failed" if failed else "serviceable", float(life - age))
            )

    con.executemany("INSERT INTO unit VALUES (?,?,?,?)", unit_rows)
    con.executemany("INSERT INTO lru VALUES (?,?,?,?,?,?,?)", lru_rows)
    con.executemany(f"INSERT INTO sensor_history VALUES ({','.join('?' * (5 + N_SENSORS))})", sensor_rows)
    con.executemany(f"INSERT INTO sensor_future VALUES ({','.join('?' * (5 + N_SENSORS))})", future_rows)

    # Stock and in-transit replenishment (base-stock policy: every consumption
    # in the past triggered an order, some of which have not yet arrived).
    spare_rows = []
    for b in BASES:
        for pn, _, lead, _, _ in PARTS:
            on_hand = int(rng.choice([0, 0, 1, 1]) if lead >= 30 else rng.choice([0, 1, 1, 2]))
            spare_rows.append((b, pn, on_hand))
            if rng.random() < 0.3:
                placed = -int(rng.integers(1, lead))
                orders.append((f"ORD-{b[-1]}-{pn[3:7]}-R", b, pn, placed, placed + lead, None))
    con.executemany("INSERT INTO spares VALUES (?,?,?)", spare_rows)
    con.executemany("INSERT INTO spare_order VALUES (?,?,?,?,?,?)", orders)
    con.executemany("INSERT INTO defect VALUES (?,?,?,?)", defects)
    con.executemany("INSERT INTO depot VALUES (?,?,?)", DEPOTS)

    # Sortie plan: aircraft tasked per base per day. Day 0 is a Monday.
    base_tasking = {"BASE-A": 6, "BASE-B": 5, "BASE-C": 6}
    plan_rows = []
    for day in range(config.HORIZON_DAYS):
        dow = day % 7
        for b in BASES:
            n = base_tasking[b]
            if dow == 5:
                n -= 2
            elif dow == 6:
                n -= 3
            if b == "BASE-B" and 28 <= day <= 41 and dow < 5:
                n += 2  # two-week exercise detachment
            plan_rows.append((day, b, int(n)))
    con.executemany("INSERT INTO sortie_plan VALUES (?,?,?)", plan_rows)

    # Phase inspections fall due in batches: tails that were inducted together
    # last cycle come due together this cycle, which is what creates bay queues.
    healthy = [t for t in tails if t not in defect_tails]
    inspect_tails = [str(t) for t in rng.choice(healthy, size=14, replace=False)]
    centres = [9, 41, 72]
    tech_rows = []
    for k, tail in enumerate(sorted(inspect_tails)):
        centre = centres[k % len(centres)]
        due = int(centre + rng.integers(-3, 4))
        dur = int(rng.integers(7, 13))
        tech_rows.append(
            (f"TR-{tail[5:]}-PH", tail, "phase_inspection", None, due, dur, due - 365, "Phase inspection, depot level")
        )
    con.executemany("INSERT INTO tech_records VALUES (?,?,?,?,?,?,?,?)", tech_rows)

    meta = {
        "seed": str(seed),
        "provenance": "SYNTHETIC SCENARIO",
        "horizon_days": str(config.HORIZON_DAYS),
        "generator": "flightline.datagen v1",
        "sensor_names": ",".join(f"s{i}" for i in range(1, N_SENSORS + 1)),
    }
    con.executemany("INSERT INTO meta VALUES (?,?)", list(meta.items()))
    con.commit()

    counts = {
        tbl: con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        for tbl in [
            "aircraft", "part", "unit", "lru", "sensor_history", "sensor_future", "spares",
            "spare_order", "depot", "sortie_plan", "tech_records", "defect",
        ]
    }
    con.close()
    return counts
