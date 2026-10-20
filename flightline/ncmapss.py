"""Optional loader for real NASA turbofan data dropped into data/raw/.

  N-CMAPSS  N-CMAPSS_DS*.h5      (needs `pip install h5py`; per-second flight
                                  data, averaged to one row per unit-cycle)
  C-MAPSS   train_FD00*.txt      (run-to-failure training trajectories)

When either is present the degradation model trains, calibrates and is
tested on the real units, and each installed LRU's sensor history becomes a
held-out real unit cut at the same fraction of life as its synthetic
counterpart. Logistics (fleet, stock, depots, sorties) stay synthetic, and
the provenance badge says exactly that.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from . import config
from .data import DegradationSet, Unit

SPLITS = (("train", 0.5), ("calibration", 0.25), ("test", 0.25))


def _cmapss(paths: list[Path]) -> tuple[list[tuple[str, np.ndarray, np.ndarray]], list[str]]:
    raw = []
    for path in paths:
        arr = np.loadtxt(path)
        if arr.ndim != 2 or arr.shape[1] < 26:
            raise ValueError(f"{path.name}: expected 26 columns (unit, cycle, 3 settings, 21 sensors)")
        for unit in np.unique(arr[:, 0]).astype(int):
            rows = arr[arr[:, 0] == unit]
            rows = rows[np.argsort(rows[:, 1])]
            raw.append((f"{path.stem}-{unit:03d}", rows[:, 2:5], rows[:, 5:26]))
    sens = np.vstack([s for _, _, s in raw])
    keep = np.flatnonzero(sens.std(axis=0) > 1e-6)  # constant channels carry no information
    names = [f"s{i + 1}" for i in keep]
    return [(uid, ops, s[:, keep]) for uid, ops, s in raw], names


def _ncmapss(paths: list[Path]) -> tuple[list[tuple[str, np.ndarray, np.ndarray]], list[str]]:
    import h5py  # optional dependency

    raw = []
    names: list[str] = []
    for path in paths:
        with h5py.File(path, "r") as f:
            if not names:
                names = [n.decode() if isinstance(n, bytes) else str(n) for n in f["X_s_var"][()]]
            for part in ("dev", "test"):
                W = np.asarray(f[f"W_{part}"], dtype=float)
                X = np.asarray(f[f"X_s_{part}"], dtype=float)
                A = np.asarray(f[f"A_{part}"], dtype=float)  # unit, cycle, Fc, hs
                for unit in np.unique(A[:, 0]).astype(int):
                    sel = A[:, 0] == unit
                    cycles = A[sel, 1].astype(int)
                    order = np.unique(cycles)
                    ops = np.vstack([W[sel][cycles == c].mean(axis=0) for c in order])
                    sens = np.vstack([X[sel][cycles == c].mean(axis=0) for c in order])
                    raw.append((f"{path.stem}-{part}-{unit:02d}", ops, sens))
    return raw, names


def load_if_present(synthetic: DegradationSet, raw_dir: Path = config.RAW_DIR) -> DegradationSet | None:
    """A DegradationSet built on real data if any is in raw_dir, else None."""
    if not raw_dir.exists():
        return None
    h5 = sorted(raw_dir.glob("N-CMAPSS_*.h5"))
    txt = sorted(raw_dir.glob("train_FD00*.txt"))
    if h5:
        try:
            raw, names = _ncmapss(h5)
            source = "N-CMAPSS"
        except ImportError:
            print("flightline: N-CMAPSS files found but h5py is not installed; staying on synthetic data.")
            return None
    elif txt:
        raw, names = _cmapss(txt)
        source = "C-MAPSS"
    else:
        return None
    return assemble(raw, names, synthetic, source)


def assemble(raw: list[tuple[str, np.ndarray, np.ndarray]], names: list[str], synthetic: DegradationSet,
             source: str) -> DegradationSet:
    """Map real run-to-failure units onto the synthetic fleet's part types and installed positions."""
    parts = sorted({u.part_number for u in synthetic.units.values()})
    raw = sorted(raw, key=lambda r: r[0])
    rng = np.random.default_rng([config.SEED, 5])
    order = rng.permutation(len(raw))
    n = len(raw)
    cut1, cut2 = int(n * SPLITS[0][1]), int(n * (SPLITS[0][1] + SPLITS[1][1]))
    units: dict[str, Unit] = {}
    for rank, idx in enumerate(order):
        uid, ops, sens = raw[idx]
        split = "train" if rank < cut1 else "calibration" if rank < cut2 else "test"
        units[uid] = Unit(uid, parts[idx % len(parts)], split, len(sens), ops, sens)
    test_by_part = {p: [u for u in units.values() if u.split == "test" and u.part_number == p] for p in parts}
    installed, truth, full, ages = {}, {}, {}, {}
    used: dict[str, int] = {p: 0 for p in parts}
    for key in sorted(synthetic.installed):
        tail, part = key
        pool = test_by_part[part] or [u for u in units.values() if u.split == "test"]
        src = pool[used[part] % len(pool)]
        used[part] += 1
        syn_age = synthetic.installed_age[key]
        frac = syn_age / max(syn_age + synthetic.installed_truth_remaining[key], 1)
        L = src.life_cycles
        cut = L if frac >= 1 else int(np.clip(round(frac * L), 1, L - 1))
        iid = f"{src.unit_id}@{tail}"
        units[iid] = Unit(iid, part, "installed", L, src.ops[:cut], src.sensors[:cut])
        installed[key] = iid
        truth[key] = float(L - cut)
        ages[key] = cut
        full[key] = Unit(iid, part, "installed", L, src.ops, src.sensors)
    return DegradationSet(source, names, units, installed, truth, full, ages)
