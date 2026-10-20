import sqlite3

import numpy as np

from flightline import datagen
from flightline.ncmapss import load_if_present


def _digest(path):
    con = sqlite3.connect(path)
    rows = con.execute("SELECT SUM(s1), SUM(s5), COUNT(*) FROM sensor_history").fetchone()
    lru = con.execute("SELECT GROUP_CONCAT(age_cycles) FROM lru").fetchone()
    con.close()
    return rows, lru


def test_generator_is_deterministic(tmp_path):
    a, b = tmp_path / "a.sqlite", tmp_path / "b.sqlite"
    assert datagen.generate(a) == datagen.generate(b)
    assert _digest(a) == _digest(b)


def test_fleet_shape_matches_the_brief(ctx):
    w = ctx.world
    assert len(w.tails) == 24 and len(w.bases) == 3 and len(w.parts) == 6 and w.horizon == 90
    assert len(w.depots) == 2
    leads = [p.lead_time_days for p in w.parts.values()]
    assert min(leads) >= 7 and max(leads) <= 60
    assert all(t.startswith("TAIL-") for t in w.tails) and all(b.startswith("BASE-") for b in w.bases)


def test_cmapss_files_switch_provenance(ctx, tmp_path):
    rng = np.random.default_rng(0)
    rows = []
    for unit in range(1, 41):
        life = int(rng.integers(120, 260))
        for cyc in range(1, life + 1):
            settings = rng.normal(0, 0.002, 3)
            sensors = 500 + rng.normal(0, 0.5, 21) + (cyc / life) ** 2 * np.linspace(-3, 3, 21)
            sensors[[0, 4]] = 100.0  # constant channels, as in the real files
            rows.append([unit, cyc, *settings, *sensors])
    np.savetxt(tmp_path / "train_FD001.txt", np.array(rows), fmt="%.4f")
    real = load_if_present(ctx.deg, tmp_path)
    assert real is not None and real.source == "C-MAPSS"
    assert set(real.installed) == set(ctx.deg.installed)
    assert {u.split for u in real.units.values()} == {"train", "calibration", "test", "installed"}
    assert len(real.sensor_names) == 19
    for key, uid in real.installed.items():
        u = real.units[uid]
        assert real.installed_age[key] == len(u.sensors)
        assert real.installed_age[key] + real.installed_truth_remaining[key] == u.life_cycles


def test_no_real_data_means_no_switch(ctx, tmp_path):
    assert load_if_present(ctx.deg, tmp_path) is None
